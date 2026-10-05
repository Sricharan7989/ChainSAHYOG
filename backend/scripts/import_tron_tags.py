"""
Import Tron exchange tags from the GraphSense TagPacks (MIT) not already held.

    python -m scripts.import_tron_tags --dry-run
    python -m scripts.import_tron_tags

Reads the cached packs (data/.tagpacks-cache, see scripts/apply_provenance) for
`currency: TRX` exchange tags, validates each as a Tron address
(core/addresses.py), and adds those we do not already hold at the THIRD-PARTY
PACK tier, cited as "GraphSense TagPack <name> (MIT), sourced from <upstream>".
A tag we already hold from the exchange's own page is left at its stronger tier.

KUCOIN. Its 4 Tron addresses come in through this route, from the MIT pack -
the same route as the 345 Etherscan-sourced pack rows we keep - and are cited
as pack-sourced, never self-published. KuCoin's own transparency page remains
OFF LIMITS for harvesting addresses: its Terms of Use, Articles 90-92, forbid
compiling its content into a database (see scripts/resource_labels.py,
NEVER_ADD). Do not "upgrade" these rows by copying from KuCoin's page.

Idempotent.
"""

import argparse
import json
import sys

import yaml

from app import config
from core import addresses
from scripts import apply_provenance

ACTOR_ENTITY = {"binance": "Binance", "huobi": "Huobi", "kucoin": "KuCoin", "bitfinex": "Bitfinex"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    labels = json.loads(config.LABELS_PATH.read_text(encoding="utf-8"))
    held = set()
    for key, meta in labels.items():
        if key.startswith("_") or not isinstance(meta, dict):
            continue
        chain_from_key, _, addr = key.rpartition(":")
        if (meta.get("chain") or chain_from_key) == "tron":
            held.add(addr)

    added, already, refused = [], 0, []
    for path in sorted(apply_provenance.CACHE.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for tag in doc.get("tags") or []:
            currency = str(tag.get("currency") or doc.get("currency") or "").upper()
            category = tag.get("category") or doc.get("category")
            if currency != "TRX" or category != "exchange":
                continue
            canon = addresses.try_normalize(str(tag.get("address", "")), "tron")
            if canon is None:
                refused.append(str(tag.get("address")))
                continue
            if canon in held:
                already += 1
                continue
            actor = str(tag.get("actor") or doc.get("actor") or "").lower()
            entity = ACTOR_ENTITY.get(actor, actor.title())
            entries = apply_provenance.pack_entries(
                [{"pack": path.stem, "source_url": str(tag.get("source") or doc.get("source") or "")}]
            )
            labels[f"tron:{canon}"] = {
                "entity": entity,
                "type": "exchange",
                "chain": "tron",
                "source": "graphsense-tagpacks",
                "evidence_tier": "third_party_pack",
                "redistributable": True,
                "citation": apply_provenance.pack_citation(entries),
                "provenance": entries,
            }
            held.add(canon)
            added.append((entity, canon))

    print(f"added {len(added)}, already held {already}, refused (not a valid Tron address) {len(refused)}")
    for entity, canon in added:
        print(f"   + {entity:10} {canon}")
    for a in refused:
        print(f"   x {a}")
    if not args.dry_run and added:
        config.LABELS_PATH.write_text(json.dumps(labels, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {config.LABELS_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
