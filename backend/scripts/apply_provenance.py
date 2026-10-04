"""
Stamp every label row with its real provenance chain and evidence tier.

    python -m scripts.apply_provenance --dry-run
    python -m scripts.apply_provenance

For each row this records, in core/provenance.py's terms: `citation`,
`evidence_tier`, `redistributable` and the structured `provenance` list.

Where the facts come from:
  * GraphSense TagPacks (MIT). Each tag carries its own `source` link, so the
    citation names the pack AND the pack's upstream: "GraphSense TagPack
    etherscan-wordcloud-exchange (MIT), sourced from Etherscan public labels".
    A pack that relays an exchange's own post says that instead - but stays at
    the third-party tier until the address is re-checked against the original
    (scripts/resource_labels does that and upgrades the tier).
  * Same-address inference rows: tier `inferred`, with the origin label's own
    citation carried through.
  * OFAC rows: government list.
  * Bridges: the protocol's own published contract registry.
  * The hand-made seed rows (labels.json _comment: "Seeded by hand from
    Etherscan's public label cloud"): where the same address is also in an MIT
    pack, the pack is the redistributable source and both facts are stated.
    Where it is in no pack, the row is a copy we made ourselves of a name tag we
    may not redistribute, so it is marked redistributable=False and moved to the
    gitignored data/labels.local.json.

Rows that already carry a stronger tier (upgraded by a later re-sourcing) are
left alone. Idempotent.
"""

import argparse
import collections
import json
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import yaml

from app import config
from core import provenance

PACK_API = "https://api.github.com/repos/graphsense/graphsense-tagpacks/contents/packs/"
PACK_RAW = "https://raw.githubusercontent.com/graphsense/graphsense-tagpacks/master/packs/"
CACHE = config.DATA_DIR / ".tagpacks-cache"
LOCAL_PATH = config.DATA_DIR / "labels.local.json"
SEED_NOTE = (
    "Also in this project's original hand-made seed list, which was compiled from "
    "Etherscan's public label cloud"
)

# What a pack's own `source` link points at, in words. Order matters only for
# readability; the first matching key wins.
UPSTREAM = [
    ("etherscan.io", "Etherscan public labels"),
    ("treasury.gov", "US Treasury OFAC SDN list"),
    ("binance.com", "Binance's own published wallet list"),
    ("github.com/bitfinexcom", "Bitfinex's own published wallet list"),
    ("kucoin.com", "KuCoin's own published wallet list"),
    ("huobi.com", "Huobi's own published wallet list"),
    ("deribit.com", "Deribit's own published wallet list"),
    ("bybit", "Bybit's own published wallet statement"),
    ("twitter.com/okx", "OKX's own post on X"),
    ("twitter.com/kris", "a post on X by Crypto.com's CEO"),
    ("nansen.ai", "a Nansen dashboard (third party)"),
    ("bitmex.com", "BitMEX's own proof-of-reserves file"),
]

# Packs that relay an entity's own publication rank above packs that relay a
# block-explorer label, when the same address is in both.
def _source_rank(url: str) -> int:
    u = url or ""
    if "etherscan.io" in u:
        return 3
    if "nansen.ai" in u:
        return 2
    if "treasury.gov" in u or "ofac" in u:
        return 1
    return 0


BRIDGES = {
    "0xa0c68c638235ee32657e8f720a23cec1bfc77c77": (
        "Polygon's own published mainnet contract index (RootChainManagerProxy)",
        "https://static.polygon.technology/network/mainnet/v1/index.json",
    ),
    "0x8315177ab297ba92a06054ce80a67ed4dbd7ed3a": (
        "Arbitrum's own documentation of its contract addresses (Bridge)",
        "https://docs.arbitrum.io/build-decentralized-apps/reference/contract-addresses",
    ),
    "0x99c9fc46f92e8a1c0dec1b1747d010903e884be1": (
        "Optimism's own Superchain Registry (L1StandardBridgeProxy)",
        "https://github.com/ethereum-optimism/superchain-registry/blob/main/superchain/configs/mainnet/op.toml",
    ),
}


def upstream_of(url: str) -> str:
    for needle, words in UPSTREAM:
        if needle in (url or ""):
            return words
    host = urlparse(url or "").netloc
    return f"the source the pack cites ({host})" if host else "a source the pack does not state"


def load_packs() -> dict[str, list[dict]]:
    """address (lowercased for EVM matching) -> [{pack, source_url, entity}], from the cache or GitHub."""
    CACHE.mkdir(parents=True, exist_ok=True)
    names = sorted(p.name for p in CACHE.glob("*.yaml"))
    if not names:
        req = urllib.request.Request(PACK_API, headers={"User-Agent": "chainsahyog"})
        listing = json.loads(urllib.request.urlopen(req, timeout=60).read())
        names = [f["name"] for f in listing if f["name"].endswith((".yaml", ".yml"))]
        for name in names:
            body = urllib.request.urlopen(PACK_RAW + name, timeout=60).read()
            (CACHE / name).write_bytes(body)
    out: dict[str, list[dict]] = collections.defaultdict(list)
    for name in names:
        doc = yaml.safe_load((CACHE / name).read_text(encoding="utf-8")) or {}
        for tag in doc.get("tags") or []:
            address = str(tag.get("address", "")).strip()
            if not address:
                continue
            key = address.lower() if address.lower().startswith("0x") else address
            out[key].append({
                "pack": name.rsplit(".", 1)[0],
                "source_url": str(tag.get("source") or doc.get("source") or ""),
                "label": str(tag.get("label") or doc.get("label") or ""),
            })
    return out


def pack_entries(hits: list[dict]) -> list[dict]:
    seen, entries = set(), []
    for h in sorted(hits, key=lambda h: (_source_rank(h["source_url"]), h["pack"])):
        if h["pack"] in seen:
            continue
        seen.add(h["pack"])
        entries.append({
            "kind": "graphsense_tagpack",
            "pack": h["pack"],
            "licence": "MIT",
            "upstream": upstream_of(h["source_url"]),
            "upstream_url": h["source_url"] or None,
        })
    return entries


def pack_citation(entries: list[dict]) -> str:
    first, rest = entries[0], entries[1:]
    text = f"GraphSense TagPack {first['pack']} (MIT), sourced from {first['upstream']}"
    if first["upstream_url"]:
        text += f" ({first['upstream_url']})"
    if rest:
        text += "; also in " + "; ".join(
            f"GraphSense TagPack {e['pack']} (MIT), sourced from {e['upstream']}" for e in rest
        )
    return text


def stamp(key: str, meta: dict, packs: dict, rows_by_key: dict) -> dict | None:
    """The provenance fields for one row, or None to leave it as it is."""
    if provenance.tier_rank(meta.get("evidence_tier")) < provenance.tier_rank("government_list"):
        return None  # already upgraded to a stronger, first-hand source
    if meta.get("source") == "ofac_sdn":
        return None  # owned by scripts/import_ofac, which cites the official list itself
    chain, _, address = key.rpartition(":")
    chain = meta.get("chain") or chain or "ethereum"
    source = meta.get("source")
    hits = pack_entries(packs.get(address.lower() if address.lower().startswith("0x") else address, []))

    if source == "inferred_cross_chain_same_address":
        origin = meta.get("inferred_from") or {}
        origin_key = origin.get("address", "")
        origin_meta = rows_by_key.get(origin_key) or rows_by_key.get(f"{origin.get('chain')}:{origin_key}") or {}
        origin_citation = origin_meta.get("citation") or "not recorded"
        ev = meta.get("evidence") or {}
        return {
            "evidence_tier": "inferred",
            "redistributable": True,
            "citation": (
                f"Inferred by ChainSAHYOG: the same address is labelled {origin.get('entity', meta.get('entity'))} "
                f"on {origin.get('chain', 'ethereum')}, and on {chain} it is an ordinary account (not a "
                f"contract) with {ev.get('nonce', '?')} outgoing transactions (checked {ev.get('checked', '?')}). "
                f"Provenance of the {origin.get('chain', 'ethereum')} label: {origin_citation}"
            ),
            "provenance": [{"kind": "inference", "method": "same_address_cross_chain",
                            "origin_chain": origin.get("chain"), "origin_address": origin_key}],
        }

    if source == "ofac":
        return {
            "evidence_tier": "government_list",
            "redistributable": True,
            "citation": (
                "US Treasury OFAC SDN list, via the ultrasoundmoney/ofac-ethereum-addresses mirror "
                "(to be replaced by the official SDN XML)"
            ),
            "provenance": [{"kind": "government_list", "list": "OFAC SDN", "via": "ultrasoundmoney mirror"}],
        }

    if meta.get("type") == "bridge" and address.lower() in BRIDGES:
        words, url = BRIDGES[address.lower()]
        return {
            "evidence_tier": "self_published",
            "redistributable": True,
            "citation": f"{words}: {url}",
            "provenance": [{"kind": "self_published", "publisher": meta.get("entity"), "url": url}],
        }

    if hits:
        citation = pack_citation(hits)
        if not source:  # a hand-made seed row that is also in a pack
            citation += f". {SEED_NOTE}"
        return {
            "evidence_tier": "third_party_pack",
            "redistributable": True,
            "citation": citation,
            "provenance": hits,
        }

    if not source:
        # A seed row in no redistributable source: our own copy of an explorer
        # name tag. Kept for local use, not shipped.
        return {
            "evidence_tier": "third_party_pack",
            "redistributable": False,
            "citation": (
                "Copied by hand into this project's seed list from Etherscan's public label cloud; "
                "no redistributable source found. Kept in the local, uncommitted label file"
            ),
            "provenance": [{"kind": "own_copy", "upstream": "Etherscan public labels"}],
        }
    return {
        "evidence_tier": "third_party_pack",
        "redistributable": True,
        "citation": f"Source recorded as {source!r}; its upstream was not found in the GraphSense packs",
        "provenance": [{"kind": "unknown", "source": source}],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    committed = json.loads(config.LABELS_PATH.read_text(encoding="utf-8"))
    local = json.loads(LOCAL_PATH.read_text(encoding="utf-8")) if LOCAL_PATH.exists() else {}
    packs = load_packs()

    rows = {k: v for k, v in committed.items() if not k.startswith("_") and isinstance(v, dict)}
    rows.update({k: v for k, v in local.items() if not k.startswith("_") and isinstance(v, dict)})
    tally, moved, changed = collections.Counter(), [], 0
    # Two passes: inferred rows quote their origin's citation, so origins first.
    order = sorted(rows, key=lambda k: rows[k].get("source") == "inferred_cross_chain_same_address")
    for key in order:
        meta = rows[key]
        fields = stamp(key, meta, packs, rows)
        if fields is not None and any(meta.get(f) != v for f, v in fields.items()):
            meta.update(fields)
            changed += 1
        tally[(meta.get("evidence_tier"), meta.get("redistributable"))] += 1

    out_committed = {k: v for k, v in committed.items() if k.startswith("_") or not isinstance(v, dict)}
    out_local = {"_comment": [
        "Labels we may NOT redistribute (e.g. our own copy of an explorer name tag).",
        "Gitignored. Merged by core/identify.load_labels when present.",
    ]}
    for key in sorted(rows, key=lambda k: list(committed).index(k) if k in committed else 10**9):
        if rows[key].get("redistributable") is False:
            out_local[key] = rows[key]
            if key in committed:
                moved.append(key)
        else:
            out_committed[key] = rows[key]

    print(f"{changed} rows stamped or updated; {len(rows)} rows in all.")
    for (tier, redis), n in sorted(tally.items(), key=lambda kv: provenance.tier_rank(kv[0][0])):
        print(f"  {tier:22} redistributable={redis!s:5} {n}")
    print(f"committed: {sum(1 for k in out_committed if not k.startswith('_'))}   "
          f"local only: {sum(1 for k in out_local if not k.startswith('_'))}   moved to local: {moved}")
    if not args.dry_run:
        config.LABELS_PATH.write_text(json.dumps(out_committed, indent=2) + "\n", encoding="utf-8")
        LOCAL_PATH.write_text(json.dumps(out_local, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {config.LABELS_PATH.name} and {LOCAL_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
