"""
Replay mode — serve a previously recorded trace instantly, from disk.

WHY THIS EXISTS
---------------
A live trace of a busy wallet makes up to a few hundred Etherscan calls against
a rate-limited free tier, and takes anywhere from two seconds to two minutes.
That is fine for investigative work and completely unacceptable in front of a
panel of judges: a slow network, a rate-limit trip or a flaky connection would
take the demo down at the worst possible moment, and none of it would say
anything about whether the tool works.

So a trace can be RECORDED once, to data/cache/<address>.json, and replayed
verbatim afterwards. The replayed payload is byte-for-byte the same JSON the
live path produces - it is the real result of a real trace, just not fetched
again. Nothing is faked; the only thing that changes is where the bytes come
from.

The recording carries `source` and `recorded_at` so the UI can say plainly that
it is showing a cached result. A demo that quietly pretends to be live would be
dishonest, and an investigator needs to know how fresh the data is.
"""

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from app import config
from core import addresses

CACHE_DIR = config.DATA_DIR / "cache"


DEFAULT_CHAIN = "ethereum"


def _path_for(address: str, chain: str | None = None, as_of_block: int | None = None) -> Path:
    """
    One file per (chain, address), keyed by the chain's own address rule.

    Ethereum keeps the bare `<address>.json` filename it has always had, so every
    recording made before multi-chain support still replays. Other chains are
    prefixed. A hyphen, not a colon: colons are illegal in Windows filenames.

    CASE-SENSITIVE ADDRESSES (Tron base58, legacy Bitcoin) keep their case AND get
    a short hash of the exact address appended. Windows and macOS filesystems are
    case-insensitive, so two addresses differing only in case would otherwise
    share one file and one would replay as the other.
    """
    chain_name = (chain or DEFAULT_CHAIN).strip().lower()
    stem = addresses.try_normalize(address, chain_name) or address.strip().lower()
    if addresses.is_case_sensitive(chain_name):
        stem = f"{stem}_{hashlib.sha256(stem.encode()).hexdigest()[:8]}"
    if chain_name != DEFAULT_CHAIN:
        stem = f"{chain_name}-{stem}"
    # A recording made at a REQUESTED height is a different trace from the
    # default one, so it gets its own file: the same address at two heights can
    # be replayed side by side, each reproducing its own answer.
    if as_of_block is not None:
        stem = f"{stem}@{int(as_of_block)}"
    return CACHE_DIR / f"{stem}.json"


def replay_note(payload: dict) -> str:
    """What a replay must say about the point in time it shows."""
    as_of = payload.get("as_of") or {}
    when = payload.get("recorded_at") or "an unrecorded time"
    if as_of.get("pinned"):
        return (
            f"Replayed from a recording captured at {when}, pinned at block {as_of['block']} on "
            f"{as_of.get('chain_name') or as_of.get('chain')}"
            + (f" ({as_of['time_utc']})" if as_of.get("time_utc") else "")
            + ". Re-running the trace live at that height reproduces it."
        )
    return (
        f"Replayed from a recording captured at {when}, made before traces were pinned to a "
        "block height. Its height is not known, so a live re-run may differ."
    )


def _chain_of(payload: dict) -> str:
    """Which chain a recorded payload describes; Ethereum when it predates chains."""
    return str((payload.get("params") or {}).get("chain") or DEFAULT_CHAIN).lower()


def save_trace(payload: dict) -> Path:
    """
    Record a completed trace so it can be replayed instantly later.

    Stamps the payload with when it was captured. The stamp matters: a cached
    trace is a snapshot of the chain at a moment in time, and funds may well
    have moved since.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    address = payload.get("start_address", "")
    if not address:
        raise ValueError("Cannot cache a trace with no start_address")
    chain = _chain_of(payload)

    recorded = dict(payload)
    recorded["source"] = "cache"
    recorded["recorded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    recorded["recorded_epoch"] = int(time.time())

    # A trace pinned at a height the caller ASKED for is stored under that
    # height; a default trace (pinned at the head when it ran) is the address's
    # default recording. Either way the payload itself carries `as_of`.
    requested = (payload.get("params") or {}).get("as_of_block")
    path = _path_for(address, chain, requested)
    path.write_text(json.dumps(recorded, indent=2), encoding="utf-8")
    return path


def load_trace(address: str, chain: str | None = None, as_of_block: int | None = None) -> dict | None:
    """The recorded trace for this address on this chain (at this height, if given), or None."""
    path = _path_for(address, chain, as_of_block)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # A corrupt recording must not take the demo down - fall through to live.
        return None
    payload["source"] = "cache"
    payload["replay_note"] = replay_note(payload)
    return payload


def has_trace(address: str, chain: str | None = None) -> bool:
    return _path_for(address, chain).exists()


def list_cached() -> list[dict]:
    """Every recorded trace, for the UI's demo picker."""
    if not CACHE_DIR.exists():
        return []

    entries = []
    for path in sorted(CACHE_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        summary = payload.get("summary", {})
        entries.append(
            {
                "address": payload.get("start_address", path.stem),
                "chain": _chain_of(payload),
                "chain_name": (payload.get("params") or {}).get("chain_name"),
                "recorded_at": payload.get("recorded_at"),
                # The height the recording is pinned at, and whether it was a
                # height the caller asked for (a "two heights" demo) or the head.
                "as_of_block": (payload.get("as_of") or {}).get("block"),
                "as_of_time": (payload.get("as_of") or {}).get("time_utc"),
                "as_of_requested": (payload.get("params") or {}).get("as_of_block") is not None,
                "headline": summary.get("headline", ""),
                "exchange": summary.get("exchange"),
                "hop_distance": summary.get("hop_distance"),
                "confidence_score": summary.get("confidence_score"),
                "nodes": payload.get("stats", {}).get("nodes", 0),
            }
        )
    return entries


def delete_trace(address: str, chain: str | None = None) -> bool:
    path = _path_for(address, chain)
    if path.exists():
        path.unlink()
        return True
    return False
