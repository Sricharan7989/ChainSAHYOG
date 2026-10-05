"""
Stamp `actionable`, `actionable_reason` and `jurisdiction` onto exchange labels.

    python -m scripts.apply_vasp_status --dry-run
    python -m scripts.apply_vasp_status

The facts live in core/vasp_status.py; this copies them onto each exchange row
in data/labels.json so the label file is self-describing. Also stamps any
non-exchange row whose company has a recorded bar (e.g. Garantex, listed as
sanctioned), so the bar travels with every label of that company. Idempotent.
"""

import argparse
import collections
import json
import sys

from app import config
from core import vasp_status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    raw = json.loads(config.LABELS_PATH.read_text(encoding="utf-8"))
    changed = 0
    tally = collections.Counter()
    for key, meta in raw.items():
        if key.startswith("_") or not isinstance(meta, dict):
            continue
        entity = meta.get("entity", "")
        if meta.get("type") != "exchange" and entity not in vasp_status.NOT_ACTIONABLE:
            continue
        status = vasp_status.status_for(entity)
        if any(meta.get(k) != v for k, v in status.items()):
            meta.update(status)
            changed += 1
        tally[(meta["actionable"], meta["jurisdiction"])] += 1

    print(f"{changed} label rows stamped or updated.")
    for (actionable, jurisdiction), n in sorted(tally.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        print(f"  actionable={actionable!s:5} jurisdiction={jurisdiction:8} {n}")
    barred = sorted({m["entity"] for k, m in raw.items()
                     if not k.startswith("_") and isinstance(m, dict) and m.get("actionable") is False})
    print("not actionable:", barred)
    if not args.dry_run and changed:
        config.LABELS_PATH.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {config.LABELS_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
