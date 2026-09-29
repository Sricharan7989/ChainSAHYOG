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

# address -> entity mapping (exchanges, mixers, bridges). Method (a) of
# exchange identification — the known-label lookup — reads from here.
LABELS_PATH = DATA_DIR / "labels.json"

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
DUST_THRESHOLD_ETH = 0.001

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
    entry = TOKEN_CONTRACTS.get(chain_id, {}).get(contract.strip().lower())
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

# Cap on outgoing transfers expanded per wallet, largest-value first. Stops one
# hot wallet from fanning the graph out to thousands of nodes.
MAX_EDGES_PER_NODE = 25

# Etherscan free tier allows 5 calls/sec; we stay comfortably under it.
ETHERSCAN_RATE_LIMIT_PER_SEC = 5
ETHERSCAN_REQUEST_DELAY_SEC = 0.25

# Most recent transactions pulled per wallet. Etherscan allows up to 10000 per
# page, but a trace does not need a hot wallet's entire history to see where the
# money went next — and asking for it would blow both latency and the quota.
MAX_TXNS_PER_ADDRESS = 1000

# Hard ceiling on wallets expanded in one trace. Last line of defence against a
# pathological fan-out; the depth cap normally bites long before this does.
MAX_NODES_PER_TRACE = 400


def has_etherscan_key() -> bool:
    """True when a live trace is possible. Without it we fall back to replay mode."""
    return bool(ETHERSCAN_API_KEY)
