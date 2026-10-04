"""
Import OFAC-sanctioned Ethereum addresses into data/labels.json.

    python -m scripts.import_ofac            # fetch, merge, report
    python -m scripts.import_ofac --dry-run  # report only, write nothing

Source: https://github.com/ultrasoundmoney/ofac-ethereum-addresses (data.csv),
a community-maintained extract of the Ethereum addresses on the US Treasury's
SDN list. Each row becomes {"entity": <sanctioned party>, "type": "sanctioned"}.

WHY THIS LIST, WHEN THE GRAPHSENSE OFAC PACK WAS REJECTED
---------------------------------------------------------
Sanctions status changes. The GraphSense ofac.yaml snapshot dates from
2024-02-26, before Tornado Cash was delisted in March 2025, so importing it
would have labelled Tornado Cash "sanctioned" - a false statement about a real
entity. This list is maintained, and at the time of writing it carries no
Tornado Cash entity. Re-run this script before relying on it: a sanctions label
is only as true as the last time it was refreshed.

WHAT A "sanctioned" LABEL DOES, AND DOES NOT, DO
------------------------------------------------
It raises a critical risk flag on the wallet and is reported in the PDF. It does
NOT stop the trace: a sanctioned wallet is not a cash-out point, so the money
keeps moving past it and so must we. See core/identify.py:is_terminal().

Existing labels always win. If an address is already labelled (for instance a
Tornado Cash contract we tagged "mixer"), it is left untouched rather than
overwritten, which also makes a second run a no-op.
"""

import argparse
import collections
import csv
import io
import json
import re
import sys
import urllib.request

from app import config
from core import addresses

SOURCE_URL = (
    "https://raw.githubusercontent.com/ultrasoundmoney/ofac-ethereum-addresses/main/data.csv"
)
ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

# What we stamp on every row we add, so a later reader can tell where a label
# came from and re-import or retire the whole set by source.
SOURCE_TAG = "ofac"


def fetch_csv() -> str:
    """
    Download the CSV.

    An empty body must fail loudly rather than read as "zero sanctioned
    addresses": raw.githubusercontent.com has returned empty responses on some
    networks, and silently importing nothing would look like success.
    """
    request = urllib.request.Request(
        SOURCE_URL, headers={"User-Agent": "vasp-attribution-engine"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        text = response.read().decode("utf-8")

    if not text.strip():
        raise RuntimeError("Empty response from the OFAC source - nothing imported.")
    return text


def merge(rows: list[dict], dry_run: bool) -> dict:
    """
    Fold CSV rows into labels.json, leaving every existing entry untouched.

    Deduplication is on the lowercased address, matching how identify.py keys
    its lookups - so a checksummed address in the feed still matches a
    lowercased one already on file.
    """
    labels = json.loads(config.LABELS_PATH.read_text(encoding="utf-8"))
    existing = {k.lower() for k in labels if not k.startswith("_")}

    stats = {"before": len(existing), "added": 0, "already_labelled": 0, "invalid": 0}

    for row in rows:
        address = (row.get("address") or "").strip()
        name = (row.get("name") or "").strip()

        # This feed is Ethereum-only; the key is the EVM canonical form.
        key = addresses.try_normalize(address, "ethereum")
        if key is None or not name:
            stats["invalid"] += 1
            continue

        if key in existing:
            stats["already_labelled"] += 1
            continue

        labels[key] = {"entity": name, "type": "sanctioned", "source": SOURCE_TAG}
        existing.add(key)
        stats["added"] += 1

    stats["after"] = stats["before"] + stats["added"]
    stats["by_type"] = collections.Counter(
        meta.get("type", "unknown")
        for key, meta in labels.items()
        if not key.startswith("_") and isinstance(meta, dict)
    )

    if not dry_run and stats["added"]:
        config.LABELS_PATH.write_text(
            json.dumps(labels, indent=2) + "\n", encoding="utf-8"
        )

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import OFAC-sanctioned Ethereum addresses into data/labels.json."
    )
    parser.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = parser.parse_args()

    print(f"Fetching {SOURCE_URL}")
    try:
        rows = list(csv.DictReader(io.StringIO(fetch_csv())))
    except Exception as exc:  # noqa: BLE001 - a failed fetch must not half-write labels
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"  {len(rows)} rows\n")

    stats = merge(rows, args.dry_run)

    print(f"  sanctioned addresses added : {stats['added']}")
    print(f"  skipped, already labelled  : {stats['already_labelled']}")
    print(f"  skipped, invalid row       : {stats['invalid']}")
    print(f"  labels before              : {stats['before']}")
    print(f"  TOTAL LABELS NOW           : {stats['after']}")
    print()
    print("  by type:")
    for entity_type, count in sorted(stats["by_type"].items(), key=lambda kv: -kv[1]):
        print(f"    {entity_type:<12} {count:>5}")

    if args.dry_run:
        print("\n(dry run - data/labels.json was not modified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
