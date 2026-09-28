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

# Transfers below this (in ETH) are ignored. Criminals and bots spray tiny
# "dust" amounts around; following them adds noise, not signal.
DUST_THRESHOLD_ETH = 0.001

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
