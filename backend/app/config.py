"""
Central configuration for the VASP Attribution Engine.

WHY this file exists:
API keys are secrets. They live in `backend/.env` (gitignored) and are read
here, once, at import time. Nothing else in the codebase touches os.environ,
and the frontend never sees a key at all — it only ever talks to our own
FastAPI backend. This is the single choke point for credentials.

It also holds the tracing guard-rails. A single busy Ethereum wallet can have
tens of thousands of transactions, so an uncapped forward trace explodes
combinatorially. The depth cap and the dust threshold are what keep a trace
finishing in seconds instead of never.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Resolve paths relative to this file so the app runs from any working directory.
# app/config.py → app/ → backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"

# Load backend/.env (no error if it is missing — /health must still come up).
load_dotenv(BACKEND_DIR / ".env")

# --- Secrets (never expose these over the API) --------------------------------

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY", "")

# --- Data sources -------------------------------------------------------------

# Etherscan API V2. The old V1 endpoint (api.etherscan.io/api) is retired and
# now answers every request with a "deprecated V1 endpoint" error, so V2 plus an
# explicit chainid is the only thing that works.
ETHERSCAN_BASE_URL = "https://api.etherscan.io/v2/api"

# --- Per-chain explorer API overrides -----------------------------------------
#
# WHY THIS EXISTS. Etherscan V2 is genuinely multichain - one endpoint, one key,
# a `chainid` parameter - but the FREE plan does not cover every chain it lists.
# Verified 2026-10 with a free key: Ethereum (1), Polygon (137) and Arbitrum
# (42161) answer normally, while BNB Chain (56) is refused with "Free API access
# is not supported for this chain". The code path works; the key does not reach it.
#
# So BNB is served by its own explorer instead. BscScan is an Etherscan clone -
# identical request parameters, identical response shape - and issues its own free
# key, so the fix is one endpoint and one key rather than a paid plan. A chain
# listed here is fetched from its own API, and the `chainid` parameter is dropped
# because the endpoint already identifies the chain.
#
# WHY IT IS AN OVERRIDE AND NOT A REWRITE. Nothing about the tracer, the label
# lookup, the taint replay or the report changes: they ask for a chain, and this
# decides which door the request goes through. A chain with no override and no
# plan coverage fails loudly at the API instead of quietly returning less.
CHAIN_API_OVERRIDES: dict[int, dict] = {}

_BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY", "")
if _BSCSCAN_API_KEY:
    CHAIN_API_OVERRIDES[56] = {
        "base_url": os.getenv("BSCSCAN_BASE_URL", "https://api.bscscan.com/api"),
        "api_key": _BSCSCAN_API_KEY,
        # BscScan serves only BNB Chain, so the V2 chainid selector is meaningless
        # here and is omitted rather than sent and ignored.
        "send_chainid": False,
        "label": "BscScan",
    }


def chain_api(chain_id: int) -> tuple[str, str, bool]:
    """
    Which explorer API, key and chainid-flag to use for one chain.

    Returns (base_url, api_key, send_chainid). Chains with no override go to
    Etherscan V2 with the main key and `chainid` set, which is correct for
    every chain the free plan covers.

    This is the single place that decides the door, so the tracer, the
    identifier and the label importer can never disagree about which API a
    chain is read from.
    """
    override = CHAIN_API_OVERRIDES.get(int(chain_id))
    if override:
        return override["base_url"], override["api_key"], override.get("send_chainid", False)
    return ETHERSCAN_BASE_URL, ETHERSCAN_API_KEY, True


def chain_readable(chain_id: int) -> bool:
    """
    Whether we can actually fetch this chain right now.

    A chain we cannot read has to be reported as unreadable rather than
    traced into an empty result: "we found no exchange there" and "we could
    not look" are different statements, and only one of them is true.
    """
    if (CHAINS.get(int(chain_id)) or {}).get("family") == "tron":
        return True  # TronGrid is read keyless (throttled); see services/tron.py
    override = CHAIN_API_OVERRIDES.get(int(chain_id))
    if override:
        return bool(override["api_key"])
    # Etherscan V2 with a key: readable unless this chain is a known paid-plan
    # chain AND no override has been supplied to bypass it.
    if not ETHERSCAN_API_KEY:
        return False
    meta = CHAINS.get(int(chain_id)) or {}
    return not (meta.get("requires_paid_plan") and int(chain_id) not in CHAIN_API_OVERRIDES)

# --- Chains -------------------------------------------------------------------
#
# V2 is multichain: ONE key and ONE endpoint serve every chain, selected per
# request by `chainid`. That is why the chain is a request parameter here and not
# a deployment setting - the same running instance can trace any of these.
#
# `native` is the gas token, used only for display; `explorer` is where a wallet
# link should point. Adding a chain means adding a row, nothing else - but read
# the "still assumes Ethereum" notes before trusting a new one, because the
# LABELS are what make a trace useful and they are curated per chain.
CHAINS: dict[int, dict] = {
    1: {
        "slug": "ethereum",
        "name": "Ethereum",
        "native": "ETH",
        "explorer": "https://etherscan.io",
    },
    137: {
        "slug": "polygon",
        "name": "Polygon",
        "native": "POL",  # renamed from MATIC in 2024
        "explorer": "https://polygonscan.com",
    },
    56: {
        "slug": "bnb",
        "name": "BNB Chain",
        "native": "BNB",
        "explorer": "https://bscscan.com",
        # Verified 2026-09: Etherscan's FREE tier refuses chainid=56 with
        # "Free API access is not supported for this chain". The code path works;
        # the key does not cover it. Flagged rather than hidden so the UI can say
        # so instead of returning a 502 that looks like our bug.
        "requires_paid_plan": True,
    },
    42161: {
        "slug": "arbitrum",
        "name": "Arbitrum One",
        "native": "ETH",
        "explorer": "https://arbiscan.io",
    },
    # Tron mainnet. Its chain id (0x2b6653dc) is what TronGrid reports; it is
    # used here only as this registry's key. Not an EVM chain: addresses are
    # base58 (core/addresses.py), and it is read through TronGrid by
    # services/tron.py, never through Etherscan.
    728126428: {
        "slug": "tron",
        "name": "Tron",
        "native": "TRX",
        "explorer": "https://tronscan.org",
        "family": "tron",
        "data_source": "TronGrid (keyless)",
    },
}

# Ethereum stays the default so every existing caller, recording and script
# behaves exactly as before.
DEFAULT_CHAIN_ID = 1

# Kept as an alias: older code and scripts referred to a single chain id.
ETHERSCAN_CHAIN_ID = DEFAULT_CHAIN_ID


def chain(chain_id: int | None = None) -> dict:
    """
    The chain descriptor, with its id included, or the default chain's.

    Raises ValueError on an unsupported id so callers can turn that into a 422
    rather than silently tracing the wrong network.
    """
    resolved = DEFAULT_CHAIN_ID if chain_id is None else int(chain_id)
    if resolved not in CHAINS:
        raise ValueError(
            f"Unsupported chain id {resolved}. Supported: "
            + ", ".join(f"{cid} ({meta['name']})" for cid, meta in CHAINS.items())
        )
    return {"chain_id": resolved, **CHAINS[resolved]}


def supported_chains() -> list[dict]:
    """Every chain this build can trace, for /health and the frontend selector."""
    return [{"chain_id": cid, **meta} for cid, meta in CHAINS.items()]


# Chain slug <-> id, so callers that have a name ("arbitrum") and callers that
# have an id (42161, as Etherscan V2 wants it) can meet without each hand-rolling
# the lookup. A bridge route is written as a slug because that is how a human
# reads it; the API needs the id.
CHAIN_BY_SLUG: dict[str, dict] = {meta["slug"]: {"chain_id": cid, **meta} for cid, meta in CHAINS.items()}


def chain_by_slug(slug: str) -> dict | None:
    """The chain descriptor for a slug, or None if we cannot read that chain."""
    return CHAIN_BY_SLUG.get((slug or "").strip().lower())

# address -> entity mapping (exchanges, mixers, bridges). Method (a) of
# exchange identification — the known-label lookup — reads from here.
LABELS_PATH = DATA_DIR / "labels.json"
# Labels we may NOT redistribute (our own copy of an explorer name tag, say).
# Gitignored; merged by the loader when present. See core/provenance.py.
LABELS_LOCAL_PATH = DATA_DIR / "labels.local.json"

# --- Graph store (optional) ---------------------------------------------------

# Neo4j holds the money-flow graph and answers the traversal queries (shortest
# path, fan-in). It is deliberately OPTIONAL: when it cannot be reached the
# tracer uses its in-memory NetworkX engine instead and returns the same answer.
# A graph database is a good story for scale and cross-case link analysis, but it
# must never be something that can take a live demo down.
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "vasptrace2026")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# Seconds to wait for a Neo4j connection before giving up and using memory.
# Short on purpose: a slow database must not become a slow trace.
NEO4J_CONNECT_TIMEOUT = 4.0

# Set NEO4J_DISABLED=1 to force the in-memory engine (useful for tests and for
# proving on stage that the tool still works with the database switched off).
NEO4J_DISABLED = os.getenv("NEO4J_DISABLED", "").strip() not in ("", "0", "false", "False")


# --- Tracing guard-rails ------------------------------------------------------

# How many hops forward from the suspect address we follow. 4 is the sweet spot:
# deep enough to pass through a few laundering hops, shallow enough to stay fast.
MAX_TRACE_DEPTH = 4

# Transfers below this (in native token) are ignored. Criminals and bots spray
# tiny "dust" amounts around; following them adds noise, not signal.
DUST_THRESHOLD_ETH = 0.01

# --- Tokens -------------------------------------------------------------------
#
# WHICH TOKENS WE FOLLOW, PINNED TO CONTRACT ADDRESSES, PER CHAIN.
#
# Following every ERC-20 would bury the graph in airdrop spam: worthless tokens
# are mass-sent to active wallets precisely because people look at them, and each
# one would add wallets and edges to expand. So we follow a short list - the
# dollar stablecoins plus wrapped ETH and BTC, which is what laundering actually
# uses. Everything else is counted and reported, never followed.
#
# WHY THE LIST IS CONTRACT ADDRESSES AND NOT SYMBOLS. A token's symbol is just a
# string its author chose, and nothing stops anyone deploying a contract that
# calls itself "USDT". An earlier version of this allowlist matched on the symbol,
# so such a token would have been followed, aggregated, and printed in a police
# report as "40,000 USDT" of laundered money. The contract address is the token's
# actual identity and cannot be forged; the symbol here is a DISPLAY LABEL that
# we assign, never a matching key.
#
# WHY PER CHAIN. The same asset has a different contract on every chain - USDT on
# Polygon is not USDT's Ethereum address - so one flat list would either reject
# real transfers or, worse, accept an Ethereum address on a chain where something
# else lives at it. Decimals differ per chain too: USDT has 6 decimals on
# Ethereum and 18 on BNB Chain, and getting that wrong misstates an amount by
# twelve orders of magnitude.
#
# HOW THESE WERE OBTAINED. Every address below was checked against the chain
# itself before being added - eth_getCode to confirm a contract exists there,
# then symbol() and decimals() called on it - not from memory. Ethereum, Polygon
# and Arbitrum were verified through the Etherscan V2 explorer API; BNB Chain,
# which the free API tier refuses, was verified against three independent public
# BSC nodes that agreed. Where a contract's own symbol() no longer matches the
# name we display, that is noted on the entry.
#
# Keys are lowercased contract addresses; values are (display symbol, decimals).
TOKEN_CONTRACTS: dict[int, dict[str, tuple[str, int]]] = {
    728126428: {  # Tron
        # Tether's TRC-20 USDT, pinned by contract address and 6 decimals. A
        # token calling itself "USDT" from any other contract is not followed.
        "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t": ("USDT", 6),
    },
    1: {  # Ethereum
        "0xdac17f958d2ee523a2206206994597c13d831ec7": ("USDT", 6),
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": ("USDC", 6),
        "0x6b175474e89094c44da98b954eedeac495271d0f": ("DAI", 18),
        "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": ("WETH", 18),
        "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": ("WBTC", 8),
    },
    137: {  # Polygon
        # Tether's Polygon contract now self-reports symbol "USDT0" after its
        # migration to the OFT standard. Same contract, same asset; we keep
        # calling it USDT so totals stay comparable across chains.
        "0xc2132d05d31c914a87c6611c10748aeb04b58e8f": ("USDT", 6),
        "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359": ("USDC", 6),
        # Bridged USDC. Its symbol() also returns "USDC", which is exactly why
        # the two cannot be told apart by symbol - only by contract. Labelled
        # USDC.e, as the explorers do, so the two are not silently added up.
        "0x2791bca1f2de4661ed88a30c99a7a9449aa84174": ("USDC.e", 6),
        "0x8f3cf7ad23cd3cadbd9735aff958023239c6a063": ("DAI", 18),
        "0x7ceb23fd6bc0add59e62ac25578270cff1b9f619": ("WETH", 18),
        "0x1bfd67037b42cf73acf2047067bd4f2c47d9bfd6": ("WBTC", 8),
    },
    56: {  # BNB Chain - Binance-Peg tokens, all 18 decimals here, not 6.
        "0x55d398326f99059ff775485246999027b3197955": ("USDT", 18),
        "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d": ("USDC", 18),
        "0x1af3f329e8be154074d8769d1ffa4ee058b1dbc3": ("DAI", 18),
        # The pegged ETH and BTC call themselves ETH and BTCB on chain, and we
        # keep those names: on BNB Chain they are tokens, not the gas token.
        "0x2170ed0880ac9a755fd29b2688956bd959f933f8": ("ETH", 18),
        "0x7130d2a12b9bcbfae4f2634d864a1ee1ce3ead9c": ("BTCB", 18),
    },
    42161: {  # Arbitrum One
        # symbol() returns "USD₮0" (with the Tether glyph) after the same
        # migration as Polygon. Displayed as USDT.
        "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9": ("USDT", 6),
        "0xaf88d065e77c8cc2239327c5edb3a432268e5831": ("USDC", 6),
        "0xff970a61a04b1ca14834a43f5de4533ebddb5cc8": ("USDC.e", 6),  # symbol() says USDC
        "0xda10009cbd5d07dd0cecc66161fc93d7c9000da1": ("DAI", 18),
        "0x82af49447d8a07e3bd95bd0d56f35241523fbab1": ("WETH", 18),
        "0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f": ("WBTC", 8),
    },
}

# Optional narrowing, as a comma-separated list of DISPLAY SYMBOLS, e.g.
# TOKEN_ALLOWLIST=USDT,USDC. Set it empty to trace native transfers only.
#
# It can only remove assets from the verified map above, never add one. That is
# deliberate: an operator must not be able to make the tracer follow an
# unverified contract by setting an environment variable, which is precisely the
# hole that matching on symbols left open.
_allowlist_env = os.getenv("TOKEN_ALLOWLIST")
TOKEN_SYMBOL_FILTER: set[str] | None = (
    {s.strip().upper() for s in _allowlist_env.split(",") if s.strip()}
    if _allowlist_env is not None
    else None
)


def token_asset(chain_id: int, contract: str | None) -> tuple[str, int] | None:
    """
    (display symbol, decimals) for an allowlisted token contract, else None.

    The single gate for "do we follow this token?". None means skip - either the
    contract is not on this chain's verified list, or an operator narrowed the
    list with TOKEN_ALLOWLIST. The token's own claimed symbol is never consulted.

    Decimals come from here, not from the API row: for a contract we have
    verified ourselves, our own figure is the authority.
    """
    if not contract:
        return None
    # Keyed by the chain's own address rule: lowercasing would break a Tron
    # (base58, case-sensitive) contract address.
    from core import addresses

    slug = (CHAINS.get(int(chain_id)) or {}).get("slug")
    table = {
        (addresses.try_normalize(k, slug) or k.lower()): v
        for k, v in TOKEN_CONTRACTS.get(chain_id, {}).items()
    }
    entry = table.get(addresses.try_normalize(contract, slug) or contract.strip().lower())
    if entry is None:
        return None
    if TOKEN_SYMBOL_FILTER is not None and entry[0].upper() not in TOKEN_SYMBOL_FILTER:
        return None
    return entry


def followed_assets(chain_id: int) -> list[str]:
    """Display symbols we follow on this chain, for the "not followed" note."""
    followed = set()
    for contract in TOKEN_CONTRACTS.get(chain_id, {}):
        entry = token_asset(chain_id, contract)
        if entry is not None:
            followed.add(entry[0])
    return sorted(followed)


def impersonates_followed_asset(chain_id: int, claimed_symbol: str) -> bool:
    """
    Does a skipped token claim the symbol of an asset we follow on this chain?

    A "USDT" we refused to follow is not a gap in coverage - it is a token
    pretending to be USDT, caught by the contract check. Worth saying out loud,
    because otherwise the skipped list looks like the tracer missing real money.
    """
    return (claimed_symbol or "").strip().upper() in {
        s.upper() for s in followed_assets(chain_id)
    }


# PER-ASSET DUST THRESHOLDS, in whole units of each asset.
#
# One number cannot serve every asset: 0.001 ETH is a few dollars, 0.001 USDT is
# a tenth of a cent, so the native threshold applied to a stablecoin filters
# nothing and the graph explodes. These are set to roughly the same real-world
# value - about one to four dollars - so "dust" means the same thing whatever the
# asset. Adjust freely; they are judgement calls, not measurements.
DUST_THRESHOLDS: dict[str, float] = {
    "ETH": DUST_THRESHOLD_ETH,   # ~$2-4
    "WETH": DUST_THRESHOLD_ETH,
    "POL": 1.0,                  # Polygon gas token, worth cents
    "TRX": 10.0,                 # ~$2-3. The request's dust parameter is in ETH and
                                 # does not apply to TRX; see dust_threshold_for.
    "BNB": 0.002,
    "USDT": 1.0,                 # $1
    "USDC": 1.0,
    "USDC.E": 1.0,               # bridged USDC; looked up upper-cased
    "DAI": 1.0,
    "WBTC": 0.00002,             # ~$1-2
    "BTCB": 0.00002,             # BNB Chain's pegged BTC
}

# Fallback for an allowlisted asset with no explicit threshold above. One whole
# unit is deliberately conservative: better to miss a sub-dollar transfer than to
# follow thousands of them.
DUST_THRESHOLD_TOKEN_DEFAULT = float(os.getenv("DUST_THRESHOLD_TOKEN", "1.0"))


def dust_threshold_for(asset: str, native_override: float | None = None) -> float:
    """
    The minimum transfer size worth following, for this asset.

    `native_override` lets a caller pass the per-request dust_threshold, which
    applies to the native token only - a request asking for 0.01 ETH precision
    is not asking to change what counts as dust in USDT.
    """
    symbol = (asset or "").upper()
    if symbol in ("ETH", "POL", "BNB") and native_override is not None:
        return native_override
    return DUST_THRESHOLDS.get(symbol, DUST_THRESHOLD_TOKEN_DEFAULT)

# --- Laundering typologies ----------------------------------------------------
#
# Pattern rules over the graph we already built. No new data sources, no new API
# calls: every threshold below is applied to transfers already fetched.
#
# WHY EVERY DEFAULT HERE IS DELIBERATELY STRICT. A typology is an accusation
# dressed as an observation. "This is a peel chain" in a police report, wrong,
# discredits the whole document and the investigator carrying it - while a missed
# pattern costs only that one lead. So each rule is set where a pattern has to be
# quite unambiguous before it fires, and each detection ships with the numbers
# that made it fire so a reader can disagree with our thresholds rather than
# having to take our word.
#
# Every value is overridable by environment variable, named after the setting.

def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw not in (None, "") else default


# PEEL CHAIN. A wallet forwards most of its balance to a fresh wallet while
# peeling a small slice off towards a cash-out, repeated down a chain.
#
# 0.80 dominant share: below about 0.7 you stop describing a peel and start
# describing an ordinary split, which is far too common to flag. 3 links: two
# consecutive forwards happen constantly by accident (a wallet paying a fee and
# forwarding the rest), three with a peel at every step much less so. Note that
# the trace depth cap bounds what is visible at all - at max_depth=3 a 3-link
# chain is the longest detectable one, so raising depth finds longer chains.
PEEL_MIN_LINKS = _env_int("PEEL_MIN_LINKS", 3)
PEEL_DOMINANT_SHARE = _env_float("PEEL_DOMINANT_SHARE", 0.80)
PEEL_MAX_SIDE_SHARE = _env_float("PEEL_MAX_SIDE_SHARE", 0.20)
PEEL_MIN_SIDE_OUTPUTS = _env_int("PEEL_MIN_SIDE_OUTPUTS", 1)

# THE PRINCIPAL MUST NOT GROW down the chain. A peel chain peels a slice off at
# each step, so what continues is less than what arrived. Without this, the walk
# just follows the biggest recipient and strings together unrelated large wallets
# that each happen to have a dominant forward - searching real addresses for a
# demo case produced "chains" of 3.4 -> 517 -> 5,894 ETH and 10.7M -> 11.9M ->
# 35.9M DAI, neither of which is one chain of money. 1.05 allows a wallet to add a
# little of its own balance to the principal before forwarding; anything more ends
# the chain.
PEEL_MAX_GROWTH = _env_float("PEEL_MAX_GROWTH", 1.05)

# LAYERING. Rapid multi-hop movement with no apparent economic purpose: each
# wallet holds the funds briefly and forwards nearly all of them.
#
# 0.95 forward ratio distinguishes layering from peeling - a layering hop keeps
# essentially nothing, where a peel deliberately keeps a slice. 1 hour dwell:
# laundering scripts move in seconds to minutes, while a wallet with a genuine
# purpose holds value for longer. Both have to hold across 3 consecutive hops.
LAYERING_MIN_LINKS = _env_int("LAYERING_MIN_LINKS", 3)
LAYERING_MAX_DWELL_SEC = _env_int("LAYERING_MAX_DWELL_SEC", 3600)
LAYERING_MIN_FORWARD_RATIO = _env_float("LAYERING_MIN_FORWARD_RATIO", 0.95)
LAYERING_MAX_FORWARD_RATIO = _env_float("LAYERING_MAX_FORWARD_RATIO", 1.25)

# STRUCTURING / SMURFING. One source split into many similar-sized outputs, or
# many similar-sized inputs converging on one destination.
#
# 6 outputs and a 0.10 coefficient of variation are both strict. Five similar
# payments is a payroll run; the similarity bar matters more than the count,
# because "many outputs" alone describes any active wallet. Labelled exchanges,
# mixers and bridges are excluded entirely: fanning value out to thousands of
# similar-sized withdrawals is precisely what an exchange hot wallet does all
# day, and flagging that as structuring would be the single biggest source of
# false positives in this whole module.
STRUCTURING_MIN_OUTPUTS = _env_int("STRUCTURING_MIN_OUTPUTS", 6)
STRUCTURING_MIN_INPUTS = _env_int("STRUCTURING_MIN_INPUTS", 6)
STRUCTURING_MAX_CV = _env_float("STRUCTURING_MAX_CV", 0.10)

# RAPID PASS-THROUGH. One wallet, funds in and straight out again. Distinct from
# layering, which is a property of a chain; this is a property of a single wallet
# and fires even where the next hop was never expanded.
#
# 1 hour and 0.90: a wallet that received and forwarded 90% of the value within
# the hour was a conduit, not a destination.
PASS_THROUGH_MAX_WINDOW_SEC = _env_int("PASS_THROUGH_MAX_WINDOW_SEC", 3600)
PASS_THROUGH_MIN_FORWARD = _env_float("PASS_THROUGH_MIN_FORWARD", 0.90)

# AND AN UPPER BOUND, which turned out to matter as much as the lower one. We see
# only a window of each wallet's history, so a wallet funded before that window
# appears to send far more than it received - on the live demo one reported a
# "forward ratio" of 31,809%. Such a wallet is not demonstrably a conduit for the
# value WE traced, because the bulk of its outflow came from inflows we never saw.
# 1.25 allows for ordinary slop (a small prior balance, gas) and rejects the rest.
PASS_THROUGH_MAX_FORWARD = _env_float("PASS_THROUGH_MAX_FORWARD", 1.25)

# A pattern has to involve an amount worth an investigator's time. Expressed as a
# multiple of the asset's own dust threshold so one rule scales across assets:
# 100x gives roughly 0.1 ETH and 100 USDT. Without it the detectors spent their
# output on sub-cent airdrop residue - the live demo reported a 0.0008 WETH
# "pass-through".
TYPOLOGY_MIN_VALUE_MULTIPLE = _env_float("TYPOLOGY_MIN_VALUE_MULTIPLE", 100.0)

# Only describe movement carrying the SUSPECT's money. A trace fetches each
# wallet's whole recent history, so most of what it sees is unrelated traffic;
# describing that traffic buried the relevant findings 120 deep on the live demo.
# When the FIFO taint pass has run, the wallet-level detectors consider only
# wallets it attributed value to. Set to 0 to describe the whole fetched graph.
TYPOLOGY_TAINTED_ONLY = os.getenv("TYPOLOGY_TAINTED_ONLY", "1").strip() not in (
    "0", "false", "False",
)

# Last-resort ceiling on how many detections a payload carries, strongest first.
# The relevance filter above should keep the real number far below this; the cap
# exists so that a pathological graph cannot produce a hundred-page report. The
# payload always states how many were held back.
TYPOLOGY_MAX_REPORTED = _env_int("TYPOLOGY_MAX_REPORTED", 15)

# ROUND AMOUNTS. Weak on its own and treated as such: this detector CANNOT fire
# by itself. A round number is only reported where another typology already
# matched the same wallets, as corroboration, because round transfers are
# completely ordinary - people send 1 ETH and 1,000 USDT constantly.
#
# 2 significant digits, at least 3 such transfers, and only above a floor worth
# noticing at all.
ROUND_AMOUNT_MAX_SIG_DIGITS = _env_int("ROUND_AMOUNT_MAX_SIG_DIGITS", 2)
ROUND_AMOUNT_MIN_COUNT = _env_int("ROUND_AMOUNT_MIN_COUNT", 3)
ROUND_AMOUNT_MIN_SHARE = _env_float("ROUND_AMOUNT_MIN_SHARE", 0.60)

# No typology is ever reported as certain, for the same reason confidence scores
# are capped: a pattern rule cannot know intent.
TYPOLOGY_STRENGTH_CAP = _env_int("TYPOLOGY_STRENGTH_CAP", 90)

# Entity types whose normal business produces these patterns. Excluded from the
# wallet-level detectors so the module reports suspicious behaviour by unknown
# wallets, not the ordinary operation of a regulated business.
TYPOLOGY_EXEMPT_ENTITY_TYPES = frozenset(
    {"exchange", "suspected_exchange", "mixer", "bridge"}
)

# --- Cross-chain bridge handoff (Phase 9) ------------------------------------
#
# WHY THIS SECTION EXISTS. A bridge used to be a wall: the tracer tagged it, the
# walk stopped, and the report said the funds left Ethereum. Multi-chain
# ingestion means that is no longer the end of the road - we can look on the
# destination chain for the value arriving and carry the trace across.
#
# WHY IT IS SCORED SEPARATELY. Everything else this tool reports is OBSERVED: a
# transfer on a chain we can read. A cross-chain handoff is an INFERENCE - we see
# value that looks like the same money, arriving at about the right time, from a
# contract that looks like a bridge. Two unrelated transfers of a similar amount
# can look identical from outside. So a handoff never merges into the on-chain
# confidence score, never prints an exchange name on the strength of itself, and
# is reported with its own evidence and its own (visibly lower) score.
#
# WHY EVERY DEFAULT IS DELIBERATELY TIGHT. A wrong chain handoff corrupts a police
# report far more than a stopped trace does. A stopped trace says "we could not
# follow this"; a wrong one says "the money went to Binance on Arbitrum" and that
# is not true. Where the settings err, they err towards stopping.

# Bridges charge a fee, so the amount that lands is smaller than the amount sent.
# Expressed as a FRACTION of the deposit: 0.02 accepts a credit worth between
# 98% and 100% of the deposit. Wider than that and an ordinary rounding
# difference or a second bridge in the path starts producing false matches.
BRIDGE_FEE_TOLERANCE = _env_float("BRIDGE_FEE_TOLERANCE", 0.02)

# How long after a deposit the matching credit may appear. This is the DEFAULT;
# each registry entry may set its own, because the honest answer differs by
# bridge: a deposit to an L2 is credited in minutes, while a withdrawal back to
# Ethereum only settles after a ~7 day fraud-proof challenge period.
BRIDGE_TIME_WINDOW_SEC = _env_int("BRIDGE_TIME_WINDOW_SEC", 3600)

# Cross-chain hops allowed in one trace. The depth cap bounds the walk WITHIN a
# chain; this bounds the walk ACROSS chains, so a trace cannot wander bridge ->
# chain -> bridge -> chain indefinitely, spending API calls and producing a graph
# nobody can read. One is usually enough to reach an exchange.
MAX_CROSS_CHAIN_HOPS = _env_int("MAX_CROSS_CHAIN_HOPS", 2)

# A candidate match below this score is not a match. The score is built from
# value closeness, time proximity and whether the credit came from a contract the
# registry knows to be part of the bridge - see core/bridges.py for the split.
BRIDGE_MATCH_MIN_SCORE = _env_int("BRIDGE_MATCH_MIN_SCORE", 60)

# AMBIGUITY has no tunable margin. Any second credit inside the fee tolerance and
# the time window makes a handoff ambiguous, whatever the scores - see
# core/bridges.resolve. An earlier score-margin rule let a credit 100 seconds
# after the deposit "beat" an identical one 1,700 seconds after, which is not
# evidence about which one is the same money.

# Smallest deposit worth attempting to match. Bridge test transactions of a few
# wei are everywhere; matching them would turn every bridge visit into a false
# handoff.
BRIDGE_MIN_DEPOSIT = _env_float("BRIDGE_MIN_DEPOSIT", 0.05)

# How many distinct bridge deposits on one chain we will try to carry across,
# largest first. A wallet that bridged out eight times in a day is possible, but
# following all eight means eight destination-chain walks - eight times the API
# calls, and a graph where the interesting path is buried. The cap is reported
# when it bites, so a capped trace is never read as a complete one.
BRIDGE_MAX_DEPOSITS_PER_CHAIN = _env_int("BRIDGE_MAX_DEPOSITS_PER_CHAIN", 2)

# Ceiling on a handoff's own score. It is never allowed near 100 for the same
# reason the on-chain score never is: this is an inference, not an observation.
BRIDGE_MATCH_MAX_SCORE = _env_int("BRIDGE_MATCH_MAX_SCORE", 85)

# ---------------------------------------------------------------------------
# THE BRIDGE REGISTRY
# ---------------------------------------------------------------------------
# Keyed by (source chain slug, bridge address on that chain). One entry per
# DIRECTION, because a bridge is not symmetric: what you deposit and what you
# receive are different contracts on different chains with different timings.
#
# FIELDS
#   entity           - how the report names the bridge.
#   from_chain       - slug of the chain the address above lives on.
#   to_chain         - slug of the destination chain.
#   credit_sources   - contracts on the DESTINATION chain whose transfers are the
#                      bridge paying out. Used to strengthen a match, never to
#                      require one: a credit arriving from some other contract is
#                      still reported, just with less confidence, because we do
#                      not claim to know every path a bridge can take.
#   asset_map        - source symbol -> destination symbol. Present because the
#                      same money changes its ticker across some bridges: ETH
#                      deposited to Polygon's bridge credits native POL.
#   window_sec       - this direction's time window, overriding the default.
#   min_amount       - smallest deposit worth matching, per asset.
#   how_it_appears   - plain description of both legs, for the report.
#   verified_from    - where the addresses below were checked, so a reviewer can
#                      re-check them rather than trust this file.
#
# ONLY VERIFIED ADDRESSES BELONG HERE. An address that is merely plausible turns a
# false "no match" into a false "matched" - the tool would claim the money crossed
# a bridge that does not exist at that address. While building this, the address
# 0x794a61358D6845594F94dc1DB02A252b5b4814aD was rejected as an Arbitrum bridge
# address: on the explorer it is Aave: Pool V3. Every entry below was then taken
# from the bridge's own published documentation.
#
# HOW TO ADD ONE: find the deposit contract on the source chain in the project's
# docs, add the entry, then confirm by hand on BOTH explorers that a deposit and
# its matching credit are visible as ordinary address history on each side.
BRIDGE_REGISTRY: dict[tuple[str, str], dict] = {
    # --- Polygon PoS ------------------------------------------------------
    (
        "ethereum",
        "0xa0c68c638235ee32657e8f720a23cec1bfc77c77",
    ): {
        "entity": "Polygon Bridge",
        "from_chain": "ethereum",
        "to_chain": "polygon",
        # The credit is a MINT of Polygon's WETH token to the depositing address,
        # so it appears in tokentx as a transfer FROM the zero address. That is
        # the payout path observed on every deposit checked (see verified_pairs).
        "credit_sources": (
            "0x0000000000000000000000000000000000000000",  # WETH mint on Polygon
        ),
        # Native ETH deposited through the RootChainManager is credited on Polygon
        # as WETH (contract 0x7ceb23fd6bc0add59e62ac25578270cff1b9f619), NOT as
        # native POL. An earlier version of this entry mapped ETH -> POL, which no
        # real credit can ever satisfy: two recorded deposits returned no_match with
        # zero candidates examined because of it.
        "asset_map": {"ETH": "WETH", "WETH": "WETH"},
        # The PoS bridge charges no fee on this route: every credit checked was the
        # exact deposited amount, to the wei. So the tolerance is exact rather than
        # the 2% default. This matters for honesty, not just precision: the same
        # wallet often makes several deposits of similar size, and a 2% band
        # would let one deposit's credit look like a rival candidate for another.
        "fee_tolerance": 0.0,
        # Observed lag on the verified pairs: 1,020 - 1,260 seconds.
        "window_sec": 3600,
        "min_amount": 0.05,
        "how_it_appears": (
            "The deposit is an ordinary ETH transfer from the user's address to the "
            "RootChainManager on Ethereum. About 17-21 minutes later the same amount "
            "is minted as WETH to the same address on Polygon (a token transfer from "
            "the zero address)."
        ),
        "verified_from": "https://docs.polygon.technology/pos/how-to/bridging/ethereum-polygon/ethereum-to-matic/",
        # Real deposit/credit pairs checked through Etherscan V2 on both chains
        # (2026-10-04). Each is the exact amount, minted from the zero address.
        "verified_pairs": (
            {
                "deposit_tx": "0xf5ff3b2e1553a2224d981450a0b8f2b6fe651b56e92caccd717ae03c448b36c4",
                "credit_tx": "0xc933adb6d22753ce392f4a3cbd8bfe857b03dafc1b7e47adc4ffc79c6a509378",
                "wallet": "0x02d2050481f6baa6396e629f791504f52af93817",
                "value": 10.0,
                "lag_sec": 1249,
            },
            {
                "deposit_tx": "0x978f29f9d3c61ea3767f9f1a2cbe871461a0d8bd5bc35c000db65fb645a4bfab",
                "credit_tx": "0x2470a4436020d97f6a1dbeb70f90079826e25c34e1e5195f0d37f007cf1ae953",
                "wallet": "0xf30d7e22a3139b53940f68397e88958a4153b95d",
                "value": 6.174729411420538,
                "lag_sec": 1260,
            },
        ),
    },
}

# Bridges we RECOGNISE but deliberately do not follow, with the reason. A trace
# that reaches one stops there and says why, rather than either guessing a
# destination or quietly treating the bridge as an unknown wallet.
#
# Both Arbitrum routes were removed from the registry after review: the deposit
# route was keyed on the L1 Bridge contract, but users call the Inbox and the
# Bridge only receives ETH by an internal transaction, which this tool does not
# fetch; the withdrawal route was keyed on the L2 Gateway Router, which ETH
# withdrawals do not pass through. Neither could ever produce a correct match,
# and a route that looks registered but silently cannot fire is worse than an
# honest "not supported".
BRIDGE_UNSUPPORTED: dict[tuple[str, str], str] = {
    ("ethereum", "0x8315177ab297ba92a06054ce80a67ed4dbd7ed3a"): (
        "Arbitrum Bridge is a recognised bridge, but this tool does not follow it: "
        "deposits reach it by an internal transaction from the Arbitrum Inbox, and "
        "internal transactions are not fetched, so no deposit could be matched to its "
        "Arbitrum credit with evidence. The trace stops here rather than guessing."
    ),
}


def _chain_key(chain_slug: str, address: str) -> tuple[str, str]:
    """(slug, address) keyed by that chain's own address rule; see core/addresses.py."""
    from core import addresses

    slug = (chain_slug or "").strip().lower()
    return slug, addresses.try_normalize(address, slug) or (address or "").strip()


def bridge_unsupported_reason(chain_slug: str, address: str) -> str | None:
    """Why we recognise this bridge but do not follow it, or None."""
    key = _chain_key(chain_slug, address)
    return BRIDGE_UNSUPPORTED.get(key)


def bridge_lookup(chain_slug: str, address: str) -> dict | None:
    """
    The registry entry for a bridge address on a chain, or None.

    Returns None for a wallet tagged `type: bridge` in labels.json that is not in
    this registry. That is a real state and not a failure: the tracer must still
    flag the bridge and stop honestly there, and say that it has no route
    recorded rather than pretending the bridge does not exist.
    """
    key = _chain_key(chain_slug, address)
    return BRIDGE_REGISTRY.get(key)


def bridge_destinations(chain_slug: str) -> set[str]:
    """Destination chain slugs reachable from this chain in one registered hop."""
    slug = (chain_slug or "").strip().lower()
    return {entry["to_chain"] for (from_slug, _), entry in BRIDGE_REGISTRY.items() if from_slug == slug}


# LABEL COVERAGE. Below this many labels on a chain, identification there is
# treated as NOT POSSIBLE rather than merely weak. Four exchange addresses on a
# chain with thousands of exchange wallets will almost never be the one a trace
# reaches, so reporting that chain as "covered" would let an empty result read as
# "no exchange was involved". The number is a judgement, stated so it can be
# argued with.
MIN_LABELS_FOR_COVERAGE = _env_int("MIN_LABELS_FOR_COVERAGE", 25)

# Cap on outgoing transfers expanded per wallet, largest-value first. Stops one
# hot wallet from fanning the graph out to thousands of nodes.
MAX_EDGES_PER_NODE = 25

# Etherscan free tier allows 5 calls/sec; we stay comfortably under it.
ETHERSCAN_RATE_LIMIT_PER_SEC = 5
ETHERSCAN_REQUEST_DELAY_SEC = 0.25
# TronGrid, keyless: about 3 requests a second, below its throttle for
# unauthenticated callers. A 403/429 is backed off and retried (services/tron.py).
TRONGRID_REQUEST_DELAY_SEC = 0.35
# Transient network failures (DNS, dropped connections) retried per request,
# with exponential backoff, before a fetch is reported as failed.
NETWORK_RETRIES = 4
# Pages of 200 rows per endpoint before a Tron wallet's history is reported as
# truncated (25 pages = 5,000 rows, the same depth as MAX_HISTORY_PAGES on EVM).
TRON_MAX_HISTORY_PAGES = 25

# KNOWN LABEL GAPS, named per chain so an empty result is never a silent hole.
COVERAGE_GAPS: dict[str, str] = {
    "tron": (
        "Tron exchange labels cover Binance, Huobi, KuCoin and Bitfinex only (27 addresses, "
        "against about 1,500 labels in total). OKX, a major venue for TRC-20 USDT, has no Tron "
        "labels here, so funds reaching OKX on Tron would not be named."
    ),
}

# Most recent transactions pulled per wallet. Etherscan allows up to 10000 per
# page, but a trace does not need a hot wallet's entire history to see where the
# money went next — and asking for it would blow both latency and the quota.
MAX_TXNS_PER_ADDRESS = 1000
# How many windows of MAX_TXNS_PER_ADDRESS rows to page back from the as-of
# height before a wallet's history is declared truncated. Each extra page is one
# more call per endpoint (txlist, tokentx), spent only on wallets that fill a
# whole window. A wallet still not exhausted after this is reported, per wallet,
# as "history truncated at block N" - never silently cut.
MAX_HISTORY_PAGES = 5

# Hard ceiling on wallets expanded in one trace. Last line of defence against a
# pathological fan-out; the depth cap normally bites long before this does.
MAX_NODES_PER_TRACE = 400


def has_etherscan_key() -> bool:
    """True when a live trace is possible. Without it we fall back to replay mode."""
    return bool(ETHERSCAN_API_KEY)
