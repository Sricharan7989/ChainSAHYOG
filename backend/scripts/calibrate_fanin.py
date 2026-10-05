"""
Calibrate the consolidation (fan-in) thresholds against ground truth.

    python -m scripts.calibrate_fanin            # measure, write data/calibration/fanin_sample.json
    python -m scripts.calibrate_fanin --report   # re-print the figures from the saved sample

WHY. The chain-wide sender floor was 20, chosen by feel, and it let the Ronin
attacker's own re-pooling wallet through. A threshold that decides whether an
address is called an exchange must be read off data, so this measures:

  POSITIVES  labelled Ethereum exchange wallets (ground truth: a published or
             self-published label), a deterministic stratified sample - up to
             PER_ENTITY addresses per company, so one company with 40 wallets
             cannot dominate - with each wallet's role kept, because a cold or
             reserve wallet is a genuine exchange address that does NOT collect
             deposits, and the heuristic is about deposit collection.
  NEGATIVES  wallets known to be attackers re-pooling their own funds: the OFAC-
             listed Lazarus Group wallets from the Ronin trace, plus the Ronin
             candidate 0xee009faf (the wallet the original docstring describes).

For each address, at ONE pinned block, the same two calls the tracer makes
(EtherscanClient.get_inbound_senders): distinct senders, distinct recipients,
incoming and outgoing rows in its most recent page of each endpoint.

COST: 2 calls per address.
"""

import argparse
import asyncio
import json
import random
import statistics
import sys

from app import config
from core import identify
from services.etherscan import get_client

OUT = config.DATA_DIR / "calibration" / "fanin_sample.json"
PER_ENTITY = 2
MAX_POSITIVES = 70
SEED = 26182

# The Ronin trace's own re-pooling wallet, and OFAC-listed Lazarus wallets
# (attacker-controlled, so by definition not exchange collection points).
NEGATIVE_EXTRA = {
    "0xee009faf00cf54c1b4387829af7a8dc5f0c8c8c5": "Ronin trace candidate: attacker re-pooling (6 traced senders)",
}


def positives() -> list[dict]:
    labels = identify.load_labels(force_reload=True)
    by_entity: dict[str, list] = {}
    for (chain, address), meta in sorted(labels.items()):
        if chain != "ethereum" or meta.get("type") != "exchange":
            continue
        if meta.get("source") == "inferred_cross_chain_same_address":
            continue
        by_entity.setdefault(meta["entity"], []).append((address, meta))
    rng = random.Random(SEED)
    picked = []
    for entity in sorted(by_entity):
        rows = by_entity[entity][:]
        rng.shuffle(rows)
        for address, meta in rows[:PER_ENTITY]:
            picked.append({"address": address, "entity": entity, "role": meta.get("role") or "",
                           "tier": meta.get("evidence_tier"), "group": "positive"})
    rng.shuffle(picked)
    return sorted(picked[:MAX_POSITIVES], key=lambda r: (r["entity"], r["address"]))


def negatives() -> list[dict]:
    labels = identify.load_labels()
    out = [{"address": a, "entity": why, "role": "", "tier": None, "group": "negative"}
           for a, why in NEGATIVE_EXTRA.items()]
    for (chain, address), meta in sorted(labels.items()):
        if chain == "ethereum" and meta.get("entity", "").lower() == "lazarus group":
            out.append({"address": address, "entity": "Lazarus Group (OFAC SDN)", "role": "",
                        "tier": meta.get("evidence_tier"), "group": "negative"})
    return out


async def measure(rows: list[dict], head: int | None = None) -> dict:
    client = get_client()
    head = head if head is not None else await client.latest_block(1)
    for i, row in enumerate(rows, 1):
        if row.get("value_senders") is not None:
            continue  # already measured (resume)
        row.pop("error", None)
        try:
            r = await client.get_inbound_senders(row["address"], 1, as_of_block=head)
            row.update({k: r.get(k) for k in ("senders", "recipients", "rows", "out_rows", "complete",
                                               "value_senders", "value_recipients")})
        except Exception as exc:  # noqa: BLE001 - recorded, not hidden
            row["error"] = str(exc)
        print(f"  [{i}/{len(rows)}] {row['group']:8} {row['entity'][:28]:28} senders={row.get('senders')} "
              f"recipients={row.get('recipients')} in={row.get('rows')} out={row.get('out_rows')}", flush=True)
    return {"block": head, "api_calls": client.api_calls, "rows": rows}


def ratio(r: dict) -> float:
    """Distinct senders per distinct recipient: high for a collection point."""
    return (r.get("senders") or 0) / max(1, r.get("recipients") or 0)


def describe(name: str, xs: list[float]) -> str:
    if not xs:
        return f"{name}: no data"
    xs = sorted(xs)
    q = statistics.quantiles(xs, n=10) if len(xs) >= 10 else [xs[0]] * 9
    return (f"{name}: n={len(xs)} min={xs[0]:.1f} p10={q[0]:.1f} median={statistics.median(xs):.1f} "
            f"p90={q[-1]:.1f} max={xs[-1]:.1f}")


def report(sample: dict) -> None:
    rows = [r for r in sample["rows"] if r.get("senders") is not None]
    pos = [r for r in rows if r["group"] == "positive"]
    neg = [r for r in rows if r["group"] == "negative"]
    cold = [r for r in pos if any(w in r["role"].lower() for w in ("cold", "reserve"))]
    hot = [r for r in pos if r not in cold]
    print(f"\nblock {sample['block']}   api calls {sample['api_calls']}")
    for label, group in (("positives (all)", pos), ("positives, cold/reserve role", cold),
                         ("positives, other roles", hot), ("negatives", neg)):
        print(f"--- {label}")
        print("   ", describe("senders", [r["senders"] for r in group]))
        print("   ", describe("senders/recipient", [ratio(r) for r in group]))
    print("\nlowest positives by senders:")
    for r in sorted(pos, key=lambda r: r["senders"])[:8]:
        print(f"   {r['senders']:5} senders, {r['recipients']:5} recipients  {r['entity']} {r['role']!r} {r['address']}")
    print("negatives:")
    for r in sorted(neg, key=lambda r: -r["senders"]):
        print(f"   {r['senders']:5} senders, {r['recipients']:5} recipients  ratio {ratio(r):.2f}  {r['entity']} {r['address']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--report", action="store_true", help="re-print from the saved sample")
    parser.add_argument("--resume", action="store_true",
                        help="re-measure only rows that failed, at the saved block")
    args = parser.parse_args()
    if args.report:
        report(json.loads(OUT.read_text(encoding="utf-8")))
        return 0
    if args.resume:
        saved = json.loads(OUT.read_text(encoding="utf-8"))
        todo = [r for r in saved["rows"] if r.get("value_senders") is None]
        print(f"resuming {len(todo)} failed rows at block {saved['block']}")
        again = asyncio.run(measure(saved["rows"], head=saved["block"]))
        again["api_calls"] = saved.get("api_calls", 0) + again["api_calls"]
        sample = again
    else:
        rows = positives() + negatives()
        print(f"measuring {len(rows)} addresses ({2 * len(rows)} calls)")
        sample = asyncio.run(measure(rows))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(sample, indent=1) + "\n", encoding="utf-8")
    report(sample)
    return 0


if __name__ == "__main__":
    sys.exit(main())
