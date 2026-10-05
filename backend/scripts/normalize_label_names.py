"""
Apply core/label_names.py to data/labels.json: company as entity, wallet role apart.

    python -m scripts.normalize_label_names --dry-run   # show what would change
    python -m scripts.normalize_label_names             # write

Idempotent: a row already rewritten keeps its original `source_name` and is not
changed again. Inferred cross-chain labels are normalised too, and the Ethereum
name recorded in their `inferred_from` evidence is left as the source wrote it.
"""

import argparse
import json
import sys

from app import config
from core import label_names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    raw = json.loads(config.LABELS_PATH.read_text(encoding="utf-8"))
    changed = []
    for key, meta in raw.items():
        if key.startswith("_") or not isinstance(meta, dict):
            continue
        before = meta.get("entity", "")
        if label_names.apply(meta):
            changed.append((key, before, meta["entity"], meta.get("role")))

    left = sorted({
        meta.get("entity") for key, meta in raw.items()
        if not key.startswith("_") and isinstance(meta, dict)
        and meta.get("entity") in label_names.LEAVE_AS_IS
    })
    print(f"{len(changed)} labels changed; {len(left)} names deliberately left as they are.")
    for key, before, after, role in changed:
        print(f"  {before!r:40} -> {after!r}" + (f"  [role: {role}]" if role else ""))
    for name in left:
        print(f"  left as-is: {name!r} - {label_names.LEAVE_AS_IS[name]}")

    if not args.dry_run and changed:
        config.LABELS_PATH.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {config.LABELS_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
