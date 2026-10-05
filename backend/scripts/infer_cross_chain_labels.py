"""
Infer exchange labels on other EVM chains from the SAME address on Ethereum.

    python -m scripts.infer_cross_chain_labels                 # polygon + arbitrum, write
    python -m scripts.infer_cross_chain_labels --dry-run       # report only
    python -m scripts.infer_cross_chain_labels --chains polygon

WHY THIS EXISTS
---------------
Identification needs labels, and the public label sets barely cover the chains
other than Ethereum: across all 78 GraphSense TagPacks there are 4 Polygon and
16 BNB Chain exchange addresses, against tens of thousands on Ethereum. A trace
that crosses onto Polygon therefore has almost nothing to recognise.

An exchange hot wallet, though, is usually an ordinary externally-owned account
(EOA), and an EOA's address is derived from its private key - the same key
controls the same address on every EVM chain. Exchanges commonly run the same hot
wallet across chains. So an address labelled "Binance" on Ethereum that is also
an active EOA on Polygon is PROBABLY Binance there too.

"Probably" is the whole point, and it is why this is a separate, clearly marked
source rather than a registry match. The rules below are not negotiable, because
an address can legitimately belong to someone else on another chain:

  1. NEVER a contract on the destination chain. A contract at the same address is
     a different deployment, possibly by a different deployer, with different
     ownership. eth_getCode must return empty.
  2. REAL ACTIVITY on the destination chain: at least MIN_NONCE outgoing
     transactions there. A key that has never been used on that chain says
     nothing about who operates it there.
  3. Recorded as source "inferred_cross_chain_same_address", never as a registry
     or TagPack match, with the Ethereum label it came from.
  4. Scored BELOW a true label match and ABOVE the fan-in pattern (core/scoring.py
     METHOD_POINTS["inferred_label"]), and shown as an inference in the UI and PDF.

Only exchange labels are inferred. Mixers and bridges are contracts (rule 1 would
reject them anyway), and a sanctions designation attaches to a specific listing,
not to a key's activity on another chain.

Existing labels always win: an address already labelled on the destination
chain is left exactly as it is.
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone

import httpx

from app import config
from core import identify

SOURCE = "inferred_cross_chain_same_address"

# Outgoing transactions required on the destination chain before a key's
# Ethereum identity is carried over. Same bar the TagPack importer uses for an
# exchange-scale wallet.
MIN_NONCE = 25

DEFAULT_CHAINS = ("polygon", "arbitrum")


async def _rpc(client: httpx.AsyncClient, action: str, address: str, chain_id: int) -> str:
    base_url, api_key, send_chainid = config.chain_api(chain_id)
    params = {"module": "proxy", "action": action, "address": address, "tag": "latest", "apikey": api_key}
    if send_chainid:
        params["chainid"] = chain_id
    await asyncio.sleep(config.ETHERSCAN_REQUEST_DELAY_SEC)
    response = await client.get(base_url, params=params, timeout=30)
    body = response.json()
    result = body.get("result")
    if not isinstance(result, str) or not result.startswith("0x"):
        raise RuntimeError(str(result)[:120])
    return result


async def infer(chains: list[str]) -> tuple[dict, dict]:
    """Return (additions keyed for labels.json, per-chain stats)."""
    labels = identify.load_labels(force_reload=True)
    sources = sorted(
        (address, meta)
        for (chain, address), meta in labels.items()
        if chain == "ethereum" and meta.get("type") == "exchange"
        and meta.get("source") != SOURCE
    )
    stamp = datetime.now(timezone.utc).date().isoformat()
    additions: dict[str, dict] = {}
    stats: dict[str, dict] = {}

    async with httpx.AsyncClient() as client:
        for slug in chains:
            chain = config.chain_by_slug(slug)
            row = stats.setdefault(slug, {"candidates": len(sources), "already_labelled": 0,
                                         "contract": 0, "inactive": 0, "failed": 0, "inferred": 0})
            if chain is None or not config.chain_readable(chain["chain_id"]):
                row["skipped"] = f"{slug} cannot be read with the configured API key"
                continue
            started = time.monotonic()
            for i, (address, meta) in enumerate(sources, 1):
                if (slug, address) in labels:
                    row["already_labelled"] += 1
                    continue
                try:
                    code = await _rpc(client, "eth_getCode", address, chain["chain_id"])
                    if code not in ("0x", "0x0"):
                        row["contract"] += 1  # rule 1: a contract here is someone else's deployment
                        continue
                    nonce = int(await _rpc(client, "eth_getTransactionCount", address, chain["chain_id"]), 16)
                except Exception:  # noqa: BLE001 - a failed lookup is not evidence either way
                    row["failed"] += 1
                    continue
                if nonce < MIN_NONCE:
                    row["inactive"] += 1  # rule 2: no real activity on this chain
                    continue
                additions[f"{slug}:{address}"] = {
                    "entity": meta.get("entity", ""),
                    **({"role": meta["role"]} if meta.get("role") else {}),
                    "type": "exchange",
                    "chain": slug,
                    "source": SOURCE,
                    "inferred_from": {"chain": "ethereum", "address": address,
                                      "entity": meta.get("entity", ""),
                                      "source": meta.get("source", "")},
                    "evidence": {"is_contract": False, "nonce": nonce, "checked": stamp},
                }
                row["inferred"] += 1
                if i % 50 == 0:
                    print(f"  {slug}: {i}/{len(sources)} checked, {row['inferred']} inferred "
                          f"({time.monotonic() - started:.0f}s)")
    return additions, stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Infer same-address exchange labels on other EVM chains.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--chains", nargs="+", default=list(DEFAULT_CHAINS))
    args = parser.parse_args()
    if not config.has_etherscan_key():
        print("ETHERSCAN_API_KEY missing", file=sys.stderr)
        return 2

    additions, stats = asyncio.run(infer(args.chains))
    for slug, row in stats.items():
        print(f"\n{slug}: {json.dumps(row)}")
    if not args.dry_run and additions:
        raw = json.loads(config.LABELS_PATH.read_text(encoding="utf-8"))
        for key, value in additions.items():
            raw.setdefault(key, value)  # existing entries always win
        config.LABELS_PATH.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {len(additions)} inferred labels to {config.LABELS_PATH.name}")
    elif args.dry_run:
        print("\n(dry run - labels.json not modified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
