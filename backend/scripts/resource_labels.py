"""
Re-source labels we already hold to a stronger, first-hand source.

    python -m scripts.resource_labels --dry-run
    python -m scripts.resource_labels

WHY. In court, "Binance published this address itself" beats "a block explorer
labelled it, relayed by a third-party pack". This script UPGRADES the citation
and evidence tier of rows we already hold when a first-hand source confirms
them. It never adds a new address and never renames an entity:

  a. Mixers -> US Treasury OFAC's own designation record for TORNADO CASH
     (data/sources/ofac_tornado_cash.json, public domain). Tornado Cash was
     designated on 8 Aug 2022, redesignated on 8 Nov 2022 and removed from the
     SDN list on 21 Mar 2025, so the citation says it is a record of the
     designation, not a current sanction. Tier: government list.

  b. Exchanges -> the exchange's own published wallet list, matched on the SAME
     chain (data/.sources-cache/self_published.json, gitignored). Tier:
     self-published. A page that lists an address on Ethereum says nothing
     about the same address on Polygon.

  c. New addresses from the exchanges' own lists, for the exchanges in
     ADD_NEW only (approved 2026-10-05): Binance, Huobi, Bitfinex. Self-published
     tier, same citation form as the upgrades.

KUCOIN IS DELIBERATELY EXCLUDED FROM (c) - DO NOT ADD IT. KuCoin's Terms of
Use, Articles 90-92, forbid copying its content and systematically compiling
it into a database. Harvesting new addresses from its page is exactly that.
Upgrading the citation on rows we already held from an MIT pack (b) is not, and
stays. Decided by the project lead in Step 4; reversing it needs their sign-off.

Rows it touches carry `resourced: true`, which scripts/apply_provenance leaves
alone. Idempotent.
"""

import argparse
import collections
import json
import sys

from app import config
from core import addresses, provenance

TORNADO = config.DATA_DIR / "sources" / "ofac_tornado_cash.json"

# Exchanges whose own published lists may ADD addresses we do not hold (c).
# KuCoin is not here on purpose - see the module docstring.
ADD_NEW = {"Binance", "Huobi", "Bitfinex"}
NEVER_ADD = {"KuCoin": "KuCoin Terms of Use Arts. 90-92 forbid compiling its content into a database"}
SELF_PUBLISHED = config.DATA_DIR / ".sources-cache" / "self_published.json"


def _index(labels: dict) -> dict:
    out = {}
    for key, meta in labels.items():
        if key.startswith("_") or not isinstance(meta, dict):
            continue
        chain_from_key, _, addr = key.rpartition(":")
        chain = meta.get("chain") or chain_from_key or "ethereum"
        canon = addresses.try_normalize(addr, chain)
        if canon:
            out[(chain, canon)] = key
    return out


def _strip(citation: str) -> str:
    """The row's own citation without any earlier upgrade prefix, so reruns do not stack."""
    marker = ". Earlier source: "
    return citation.split(marker, 1)[1] if marker in citation else citation


def mixers(labels: dict, index: dict, stats: collections.Counter) -> None:
    if not TORNADO.exists():
        return
    record = json.loads(TORNADO.read_text(encoding="utf-8"))
    removed = set(record["removal"]["addresses"])
    designated: dict[str, list[dict]] = collections.defaultdict(list)
    for d in record["designations"]:
        for a in d["addresses"]:
            designated[a].append(d)
    for addr, events in designated.items():
        key = index.get(("ethereum", addr))
        if key is None or labels[key].get("type") != "mixer" or labels[key].get("entity") != "Tornado Cash":
            continue
        meta = labels[key]
        when = " and ".join(f"{e['date']} ({e['url']})" for e in events)
        if addr in removed:
            status = (f"removed from the SDN list on {record['removal']['date']} "
                      f"({record['removal']['url']}). A government record that the address "
                      "belonged to Tornado Cash, not a current sanction")
        else:
            status = ("not on the current SDN list; this tool did not establish when it was "
                      "removed. A government record that the address belonged to Tornado Cash, "
                      "not a current sanction")
        before = _strip(meta.get("citation", ""))
        designated = " and ".join(_human(e["date"]) for e in events)
        meta.update({
            "evidence_tier": "government_list",
            "citation": (f"US Treasury OFAC designation of TORNADO CASH, listing this address: {when}; "
                         f"{status}. Earlier source: {before}"),
            "resourced": True,
            # The status in one plain sentence, for the finding panel and the PDF.
            "sanctions_status": {
                "status": "delisted" if addr in removed else "not_currently_listed",
                "designated": [e["date"] for e in events],
                "delisted": record["removal"]["date"] if addr in removed else None,
                "text": (f"Designated by US Treasury OFAC on {designated}; "
                         + (f"removed from the SDN list on {_human(record['removal']['date'])}. "
                            if addr in removed else "not on the current SDN list (removal date not established). ")
                         + "Not a current sanction."),
            },
        })
        prov = [p for p in meta.get("provenance") or [] if p.get("kind") != "government_record"]
        meta["provenance"] = [{"kind": "government_record", "list": "OFAC SDN (designation record)",
                               "designated": [e["date"] for e in events],
                               "removed": record["removal"]["date"] if addr in removed else None}] + prov
        stats["mixers_upgraded"] += 1


def _human(iso: str) -> str:
    """2025-03-21 -> 21 March 2025."""
    import datetime as dt

    return dt.date.fromisoformat(iso).strftime("%d %B %Y").lstrip("0")


def exchanges(labels: dict, index: dict, stats: collections.Counter, unheld: dict) -> None:
    if not SELF_PUBLISHED.exists():
        print(f"  ({SELF_PUBLISHED} not present - exchange re-sourcing skipped)")
        return
    sources = json.loads(SELF_PUBLISHED.read_text(encoding="utf-8"))
    for name, src in sources.items():
        if name.startswith("_"):
            continue
        for chain, addrs in src["addresses"].items():
            for raw in addrs:
                canon = addresses.try_normalize(raw, chain)
                if canon is None:
                    stats["self_published_bad_address"] += 1
                    continue
                key = index.get((chain, canon))
                if key is None:
                    unheld[src["entity"]][chain] += 1
                    if src["entity"] in ADD_NEW:
                        new_key = canon if chain == "ethereum" else f"{chain}:{canon}"
                        labels[new_key] = {
                            "entity": src["entity"],
                            "type": "exchange",
                            "chain": chain,
                            "source": "self_published",
                            "evidence_tier": "self_published",
                            "redistributable": True,
                            "citation": (f"{src['entity']}'s own published wallet list: {src['title']}, "
                                         f"{src['published']} ({src['url']}), retrieved {src['retrieved']}; "
                                         f"lists this address on {chain}"),
                            "provenance": [{"kind": "self_published", "publisher": src["entity"],
                                            "url": src["url"], "published": src["published"],
                                            "retrieved": src["retrieved"], "chain": chain}],
                            "resourced": True,
                        }
                        index[(chain, canon)] = new_key
                        stats[f"added:{src['entity']}:{chain}"] += 1
                    elif src["entity"] in NEVER_ADD:
                        stats[f"not added (terms):{src['entity']}"] += 1
                    continue
                meta = labels[key]
                if meta.get("type") != "exchange" or meta.get("entity") != src["entity"]:
                    stats["self_published_entity_mismatch"] += 1
                    continue
                if provenance.tier_rank(meta.get("evidence_tier")) < provenance.tier_rank("self_published"):
                    continue
                before = _strip(meta.get("citation", ""))
                meta.update({
                    "evidence_tier": "self_published",
                    "citation": (f"{src['entity']}'s own published wallet list: {src['title']}, "
                                 f"{src['published']} ({src['url']}), retrieved {src['retrieved']}; "
                                 f"lists this address on {chain}. Earlier source: {before}"),
                    "resourced": True,
                })
                prov = [p for p in meta.get("provenance") or [] if p.get("kind") != "self_published"]
                meta["provenance"] = [{"kind": "self_published", "publisher": src["entity"],
                                       "url": src["url"], "published": src["published"],
                                       "retrieved": src["retrieved"], "chain": chain}] + prov
                stats[f"upgraded:{src['entity']}:{chain}"] += 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    labels = json.loads(config.LABELS_PATH.read_text(encoding="utf-8"))
    index = _index(labels)
    stats: collections.Counter = collections.Counter()
    unheld: dict = collections.defaultdict(collections.Counter)
    mixers(labels, index, stats)
    exchanges(labels, index, stats, unheld)

    for k, v in sorted(stats.items()):
        print(f"  {k:45} {v}")
    print("  on the exchanges' own pages and not previously held:")
    for entity, by_chain in unheld.items():
        verdict = "added" if entity in ADD_NEW else f"NOT added - {NEVER_ADD.get(entity, 'not approved')}"
        print(f"    {entity:10} {dict(by_chain)}  -> {verdict}")
    if not args.dry_run:
        config.LABELS_PATH.write_text(json.dumps(labels, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {config.LABELS_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
