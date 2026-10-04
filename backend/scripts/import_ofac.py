"""
Import every crypto address on the US Treasury OFAC SDN list into data/labels.json.

    python -m scripts.import_ofac                  # download the official XML, merge, report
    python -m scripts.import_ofac --dry-run        # report only, write nothing
    python -m scripts.import_ofac --file PATH      # use an already-downloaded SDN_ADVANCED.XML

Source: OFAC's own SDN_ADVANCED.XML from the Sanctions List Service. It replaces
the community ultrasoundmoney mirror, which carried Ethereum only - and so
discarded about 943 of the list's 1,063 crypto addresses, including every
Bitcoin and Tron one. A US government work, so public domain (17 U.S.C. 105):
redistributable, and committed.

WHAT EACH ROW CARRIES. The SDN party's primary name as `entity`, its
programmes and listing date, and a citation built from them. Evidence tier:
government list. Every address goes through core/addresses.py for its chain,
so a Tron or legacy Bitcoin address keeps its case. An address that does not
parse for its chain is REPORTED, never forced through, and the format guard is
not loosened to admit it.

WHICH CHAIN. The XML tags each address with a currency code. XBT is Bitcoin,
ETH Ethereum, TRX Tron, BSC BNB Chain, ARB Arbitrum. A stablecoin code (USDT,
USDC) names a token, not a chain, so the chain is read from the address format
(T... is Tron, 0x... Ethereum, a Bitcoin address is Omni-layer USDT on
Bitcoin). Codes for chains this tool has no address
format for (LTC, XMR, ZEC, ...) are counted and reported, not imported.

SANCTIONS STATUS CHANGES. A row means "on the list as downloaded on <date>".
Rerun before relying on it. Rows from earlier runs (and from the old mirror)
are removed and rebuilt from the current list on every run, so a delisted
address disappears - Tornado Cash, delisted on 21 Mar 2025, is not on today's
list and is not imported as sanctioned.

EXISTING LABELS. A row from another source at the same (chain, address) keeps
its entity and type (a mixer stays a mixer); the SDN listing is added to its
provenance and, being a stronger tier than a third-party pack, becomes its
citation. Idempotent.

WHAT A "sanctioned" LABEL DOES. It raises a critical risk flag on the wallet and
is reported in the PDF. It does NOT stop the trace: a sanctioned wallet is not a
cash-out point. See core/identify.py:is_terminal().
"""

import argparse
import collections
import datetime as dt
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from app import config
from core import addresses, provenance

SDN_URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN_ADVANCED.XML"
CACHE = config.DATA_DIR / ".ofac-cache" / "SDN_ADVANCED.XML"
SOURCE_TAG = "ofac_sdn"
OLD_SOURCE_TAGS = {"ofac", SOURCE_TAG}

# Currency code -> chain slug. None: decide from the address format.
CURRENCY_CHAIN = {
    "XBT": "bitcoin",
    "ETH": "ethereum",
    "TRX": "tron",
    "BSC": "bnb",
    "ARB": "arbitrum",
    "USDT": None,
    "USDC": None,
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def download(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(SDN_URL, headers={"User-Agent": "chainsahyog"})
    with urllib.request.urlopen(req, timeout=300) as response, open(path, "wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)
    if path.stat().st_size < 1_000_000:
        raise RuntimeError("SDN_ADVANCED.XML download is implausibly small - nothing imported.")
    return path


def parse(path: Path) -> tuple[list[dict], str]:
    """
    Every Digital Currency Address on the list, with its party's name, programmes
    and listing date. Returns (entries, publication date).
    """
    feature_types: dict[str, str] = {}
    profiles: dict[str, dict] = {}       # profile id -> {name, addresses[(code, addr)]}
    entries: dict[str, dict] = {}        # profile id -> {programmes, listed}
    published = ""

    for _, el in ET.iterparse(path, events=("end",)):
        tag = _local(el.tag)
        if tag == "FeatureType":
            if (el.text or "").startswith("Digital Currency Address - "):
                feature_types[el.get("ID")] = el.text.split(" - ", 1)[1].strip()
        elif tag == "DateOfIssue" and not published:
            parts = {(_local(c.tag)): c.text for c in el}
            if parts.get("Year"):
                published = f"{parts['Year']}-{int(parts['Month']):02d}-{int(parts['Day']):02d}"
        elif tag == "DistinctParty":
            profile = next((c for c in el if _local(c.tag) == "Profile"), None)
            if profile is None:
                el.clear()
                continue
            pid = profile.get("ID")
            found = []
            for feature in profile.iter():
                if _local(feature.tag) != "Feature" or feature.get("FeatureTypeID") not in feature_types:
                    continue
                detail = next((d for d in feature.iter() if _local(d.tag) == "VersionDetail"), None)
                if detail is not None and (detail.text or "").strip():
                    found.append((feature_types[feature.get("FeatureTypeID")], detail.text.strip()))
            if found:
                profiles[pid] = {"name": _primary_name(profile), "addresses": found}
            el.clear()
        elif tag == "SanctionsEntry":
            pid = el.get("ProfileID")
            if pid in profiles:
                dates, programmes = [], []
                for child in el:
                    name = _local(child.tag)
                    if name == "EntryEvent":
                        d = next((x for x in child if _local(x.tag) == "Date"), None)
                        if d is not None:
                            p = {_local(x.tag): x.text for x in d}
                            dates.append(f"{p['Year']}-{int(p['Month']):02d}-{int(p['Day']):02d}")
                    elif name == "SanctionsMeasure":
                        comment = next((x for x in child if _local(x.tag) == "Comment"), None)
                        if comment is not None and (comment.text or "").strip():
                            programmes.append(comment.text.strip())
                entries[pid] = {"programmes": sorted(set(programmes)), "listed": min(dates) if dates else ""}
            el.clear()

    out = []
    for pid, prof in profiles.items():
        entry = entries.get(pid, {})
        for code, address in prof["addresses"]:
            out.append({
                "profile_id": pid,
                "name": prof["name"],
                "currency": code,
                "address": address,
                "programmes": entry.get("programmes", []),
                "listed": entry.get("listed", ""),
            })
    return out, published


def _primary_name(profile) -> str:
    """The party's primary Latin-script name, as the list prints it."""
    for alias in profile.iter():
        if _local(alias.tag) != "Alias" or alias.get("Primary") != "true":
            continue
        for doc in alias:
            if _local(doc.tag) == "DocumentedName" and doc.get("DocNameStatusID") == "1":
                parts = [v.text.strip() for v in doc.iter() if _local(v.tag) == "NamePartValue" and v.text]
                if parts:
                    # Individuals are listed SURNAME, Given - keep the list's own form.
                    return f"{parts[0]}, {' '.join(parts[1:])}" if len(parts) > 1 else parts[0]
    return "Unnamed SDN party"


def chain_for(code: str, address: str) -> str | None:
    if code in CURRENCY_CHAIN and CURRENCY_CHAIN[code]:
        return CURRENCY_CHAIN[code]
    if code in CURRENCY_CHAIN:  # a stablecoin: the chain comes from the address format
        families = addresses.families_for(address)
        if "tron" in families:
            return "tron"
        if "evm" in families:
            return "ethereum"
        if "bitcoin" in families:
            return "bitcoin"  # USDT on the Omni Layer, which lives on Bitcoin
    return None


SDN_BESIDE_MARKER = ". Separately, this address is on the OFAC SDN list under "


def _same_party(label_entity: str, sdn_name: str) -> bool:
    """Loose match of our label's entity against the SDN party name."""
    a = "".join(ch for ch in label_entity.lower() if ch.isalnum())
    b = "".join(ch for ch in sdn_name.lower() if ch.isalnum())
    return bool(a) and bool(b) and (a in b or b in a)


def citation(e: dict, published: str) -> str:
    progs = ", ".join(e["programmes"]) or "programme not stated"
    return (
        f"US Treasury OFAC Specially Designated Nationals list (official SDN_ADVANCED.XML, "
        f"publication of {published or 'unknown date'}): {e['name']}; programme {progs}; "
        f"listed {e['listed'] or 'date not stated'}; Digital Currency Address - {e['currency']}"
    )


def merge(entries: list[dict], published: str, dry_run: bool) -> dict:
    labels = json.loads(config.LABELS_PATH.read_text(encoding="utf-8"))
    before = sum(1 for k, v in labels.items() if not k.startswith("_") and isinstance(v, dict))

    # Rebuild from the current list: drop every row an earlier OFAC import made.
    removed = [k for k, v in labels.items() if isinstance(v, dict) and v.get("source") in OLD_SOURCE_TAGS]
    for k in removed:
        del labels[k]

    index = {}
    for k, v in labels.items():
        if k.startswith("_") or not isinstance(v, dict):
            continue
        chain_from_key, _, addr = k.rpartition(":")
        ch = v.get("chain") or chain_from_key or "ethereum"
        canon = addresses.try_normalize(addr, ch)
        if canon:
            index[(ch, canon)] = k

    stats = collections.Counter()
    unsupported = collections.Counter()
    refused: list[tuple[str, str, str]] = []
    by_chain = collections.Counter()
    seen: dict[tuple[str, str], str] = {}
    for e in entries:
        chain = chain_for(e["currency"], e["address"])
        if chain is None:
            unsupported[e["currency"]] += 1
            continue
        canon = addresses.try_normalize(e["address"], chain)
        if canon is None:
            refused.append((e["currency"], e["address"], e["name"]))
            continue
        if (chain, canon) in seen:
            stats["duplicate_on_list"] += 1
            # One address listed under two parties: name both, never just the first.
            row = labels.get(seen[(chain, canon)])
            if row is not None and e["name"] not in row["entity"].split("; "):
                row["entity"] = f'{row["entity"]}; {e["name"]}'
                row["citation"] += f". Also listed under: {citation(e, published)}"
                row["provenance"].append({"kind": "government_list", "list": "OFAC SDN",
                                          "profile_id": e["profile_id"], "name": e["name"],
                                          "programmes": e["programmes"], "listed": e["listed"],
                                          "currency_code": e["currency"], "publication": published,
                                          "url": SDN_URL})
                stats["listed_under_several_parties"] += 1
            continue
        by_chain[chain] += 1
        sdn = {
            "kind": "government_list",
            "list": "OFAC SDN",
            "profile_id": e["profile_id"],
            "name": e["name"],
            "programmes": e["programmes"],
            "listed": e["listed"],
            "currency_code": e["currency"],
            "publication": published,
            "url": SDN_URL,
        }
        existing_key = index.get((chain, canon))
        seen[(chain, canon)] = existing_key or (canon if chain == "ethereum" else f"{chain}:{canon}")
        if existing_key is not None:
            # Another source labels this address: keep what it is, add the listing.
            meta = labels[existing_key]
            prov = [p for p in meta.get("provenance") or [] if p.get("list") != "OFAC SDN"]
            meta["provenance"] = [sdn] + prov
            meta["sdn"] = {k: sdn[k] for k in ("name", "programmes", "listed", "profile_id")}
            # The listing supports THIS label only if it names the same party. An
            # address our label calls "Tornado Cash" but the list names as one of
            # its founders is not a government statement that it is Tornado
            # Cash, so the tier stays and the listing is stated beside it.
            same_party = meta.get("type") == "sanctioned" or _same_party(meta.get("entity", ""), e["name"])
            base = (meta.get("citation") or "").split(SDN_BESIDE_MARKER)[0].rstrip(". ")
            if same_party and provenance.tier_rank("government_list") < provenance.tier_rank(meta.get("evidence_tier")):
                meta["evidence_tier"] = "government_list"
                meta["citation"] = citation(e, published) + (f". Also: {base}" if base else "")
            elif not same_party:
                meta["citation"] = (
                    f"{base}{SDN_BESIDE_MARKER}{e['name']} ({citation(e, published)}). The listing "
                    f"names that party, not {meta.get('entity')}, so it does not support this label"
                )
            stats["merged_into_existing"] += 1
            continue
        key = canon if chain == "ethereum" else f"{chain}:{canon}"
        labels[key] = {
            "entity": e["name"],
            "type": "sanctioned",
            "chain": chain,
            "source": SOURCE_TAG,
            "sdn": {k: sdn[k] for k in ("name", "programmes", "listed", "profile_id")},
            "evidence_tier": "government_list",
            "redistributable": True,
            "citation": citation(e, published),
            "provenance": [sdn],
        }
        stats["added"] += 1

    after = sum(1 for k, v in labels.items() if not k.startswith("_") and isinstance(v, dict))
    if not dry_run:
        config.LABELS_PATH.write_text(json.dumps(labels, indent=2) + "\n", encoding="utf-8")
    return {
        "before": before,
        "removed_old_rows": len(removed),
        "after": after,
        "stats": stats,
        "by_chain": by_chain,
        "unsupported": unsupported,
        "refused": refused,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    parser.add_argument("--file", type=Path, help="an already-downloaded SDN_ADVANCED.XML")
    args = parser.parse_args()

    path = args.file
    if path is None:
        print(f"Downloading {SDN_URL}")
        try:
            path = download(CACHE)
        except Exception as exc:  # noqa: BLE001 - a failed fetch must not half-write labels
            print(f"error: {exc}", file=sys.stderr)
            return 1
    entries, published = parse(path)
    print(f"  {len(entries)} crypto addresses on the list (publication {published}, "
          f"read {dt.date.today().isoformat()})")
    print("  by currency code:", collections.Counter(e["currency"] for e in entries).most_common())

    r = merge(entries, published, args.dry_run)
    s = r["stats"]
    print(f"\n  removed rows from earlier OFAC imports : {r['removed_old_rows']}")
    print(f"  added as sanctioned                    : {s['added']}")
    print(f"  merged into an existing label          : {s['merged_into_existing']}")
    print(f"  duplicates on the list                 : {s['duplicate_on_list']}"
          f" ({s['listed_under_several_parties']} listed under more than one party)")
    print(f"  imported by chain                      : {dict(r['by_chain'])}")
    print(f"  not imported, no address format here   : {dict(r['unsupported'])}")
    print(f"  REFUSED by the format guard            : {len(r['refused'])}")
    for code, addr, name in r["refused"]:
        print(f"      {code:5} {addr!r:60} {name}")
    print(f"  labels before / after                  : {r['before']} / {r['after']}")
    if args.dry_run:
        print("\n(dry run - data/labels.json was not modified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
