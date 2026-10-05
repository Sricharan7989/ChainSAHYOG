"""
Label provenance: every row says who published the fact and through whom we got
it, carries an evidence tier, and is shipped only if redistributable.

WHY THIS SUITE EXISTS. A finding is only as good as the label under it, and a
court will ask who said so. These checks pin the rules from core/provenance.py:

  * every row has a citation and a known evidence tier
  * no citation is collapsed to "public labels" or an internal file name
  * a row from GraphSense's Etherscan packs says exactly that
  * nothing marked not-redistributable sits in the committed file
  * the loader merges labels.local.json, and a committed row always wins

Run from backend/:  python -m tests.test_provenance
"""
import json
import sys
import tempfile
from pathlib import Path

import app  # noqa: E402,F401
from app import config  # noqa: E402
from core import identify, provenance  # noqa: E402

fail = 0


def check(name, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got!r}" + ("" if ok else f", want {want!r}"))


def committed_rows():
    raw = json.loads(config.LABELS_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, dict)}


def file_tests():
    print("--- 1. every committed row is cited, tiered and redistributable ---")
    rows = committed_rows()
    check("every row has a citation", [k for k, v in rows.items() if not v.get("citation")], [])
    check("every tier is a known one",
          sorted({v.get("evidence_tier") for v in rows.values()} - set(provenance.TIERS)), [])
    check("nothing not-redistributable is committed",
          [k for k, v in rows.items() if v.get("redistributable") is False], [])
    check("no citation names an internal file",
          [k for k, v in rows.items() if "labels.json" in v.get("citation", "")], [])
    check("no citation is collapsed to a bare 'public labels'",
          [k for k, v in rows.items()
           if "public labels" in v.get("citation", "") and "Etherscan public labels" not in v["citation"]], [])
    ether = [v for v in rows.values() if any(
        "etherscan" in (e.get("pack") or "") for e in v.get("provenance") or [])]
    check("rows from GraphSense's Etherscan packs say so, in full",
          all("(MIT), sourced from Etherscan public labels" in v["citation"] for v in ether), True)
    check("there are such rows (the 345 are kept, not retired)", len(ether) >= 345, True)

    print("\n--- 2. both demo endpoints keep their labels, with the real chain cited ---")
    for addr, entity in (("0x0577a79cfc63bbc0df38833ff4c4a3bf2095b404", "Huobi"),
                         ("0xa090e606e30bd747d4e6245a1517ebe430f0057e", "Coinbase")):
        meta = rows.get(addr, {})
        check(f"{entity} {addr[:10]} is still labelled", meta.get("entity"), entity)
        check(f"{entity} {addr[:10]} cites its pack and upstream",
              "GraphSense TagPack" in meta.get("citation", "") and "Etherscan" in meta.get("citation", ""), True)

    print("\n--- 3. inferred rows carry their origin's citation ---")
    inferred = [v for v in rows.values() if v.get("evidence_tier") == "inferred"]
    check("inferred rows exist", bool(inferred), True)
    check("each says it is our inference and quotes the origin's provenance",
          all(v["citation"].startswith("Inferred by ChainSAHYOG") and "Provenance of the" in v["citation"]
              for v in inferred), True)


def sdn_tests():
    print("\n--- 5. the official OFAC SDN import ---")
    rows = committed_rows()
    sdn = {k: v for k, v in rows.items() if v.get("source") == "ofac_sdn"}
    check("the old Ethereum-only mirror rows are gone", [k for k, v in rows.items() if v.get("source") == "ofac"], [])
    chains = {v.get("chain") for v in sdn.values()}
    check("Bitcoin, Tron and Ethereum are all imported", {"bitcoin", "tron", "ethereum"} <= chains, True)
    check("every SDN row is a government-list tier",
          all(v.get("evidence_tier") == "government_list" for v in sdn.values()), True)
    check("every SDN citation names the party, programme and listing date",
          all("programme" in v["citation"] and "listed" in v["citation"] and v["sdn"]["name"] in v["citation"]
              for v in sdn.values()), True)
    tron = [k for k in sdn if k.startswith("tron:")]
    check("Tron keys keep their base58 case", all(k.split(":", 1)[1][0] == "T" and k != k.lower() for k in tron), True)
    semenov = rows.get("0x5f48c2a71b2cc96e3f0ccae4e39318ff0dc375b2", {})
    check("a listing under a DIFFERENT party does not upgrade our label's tier",
          (semenov.get("entity"), semenov.get("evidence_tier")), ("Tornado Cash", "third_party_pack"))
    check("but it is stated beside the label",
          "does not support this label" in semenov.get("citation", ""), True)


def resourcing_tests():
    print("\n--- 6. re-sourcing upgrades existing rows only, honestly ---")
    rows = committed_rows()
    binance = rows.get("0x28c6c06298d514db089934071355e5743bf21d60", {})
    check("Binance 0x28c6 is self-published, citing Binance's own page",
          (binance.get("evidence_tier"), "binance.com" in binance.get("citation", "")), ("self_published", True))
    check("and keeps its earlier pack citation", "Earlier source: GraphSense TagPack" in binance.get("citation", ""), True)
    huobi = rows.get("0x0577a79cfc63bbc0df38833ff4c4a3bf2095b404", {})
    check("the Ronin Huobi wallet is NOT on Huobi's own list, so it stays a third-party pack",
          huobi.get("evidence_tier"), "third_party_pack")
    tornado = [v for v in rows.values() if v.get("type") == "mixer" and v.get("evidence_tier") == "government_list"]
    check("Tornado Cash mixers cite OFAC's designation record", len(tornado) >= 50, True)
    check("and say it is not a current sanction",
          all("not a current sanction" in v["citation"] for v in tornado), True)
    check("no re-sourced row is typed as sanctioned (delisted is not sanctioned)",
          all(v.get("type") != "sanctioned" for v in tornado), True)
    check("re-sourcing added no rows of its own",
          [k for k, v in rows.items() if v.get("resourced") and not v.get("citation", "").count("Earlier source:")], [])


def step4_label_tests():
    print("\n--- 7. Step 4: exchange-published additions; KuCoin excluded; Tornado status ---")
    rows = committed_rows()
    added = [v for v in rows.values() if v.get("source") == "self_published"]
    by_entity = {}
    for v in added:
        by_entity[v["entity"]] = by_entity.get(v["entity"], 0) + 1
    check("Binance 29, Huobi 20, Bitfinex 6 added as self-published",
          by_entity, {"Binance": 29, "Huobi": 20, "Bitfinex": 6})
    check("all of them at the self-published tier",
          {v["evidence_tier"] for v in added}, {"self_published"})
    check("no KuCoin address was harvested from its page",
          [v for v in added if v["entity"] == "KuCoin"], [])
    tornado = [v for v in rows.values() if v.get("sanctions_status")]
    check("Tornado Cash rows carry a plain status sentence", len(tornado) >= 50, True)
    sample = next(v for v in tornado if v["sanctions_status"]["status"] == "delisted")
    check("which says designated 2022, delisted 21 March 2025, not a current sanction",
          ("2022" in sample["sanctions_status"]["text"],
           "21 March 2025" in sample["sanctions_status"]["text"],
           sample["sanctions_status"]["text"].endswith("Not a current sanction.")),
          (True, True, True))

    from core import tracer as _tracer
    identify.load_labels(force_reload=True)
    status = _tracer._sanctions_status("ethereum", "0x722122df12d4e14e13ac3b6895a86e84145b6967")
    check("a risk flag on that mixer reads the status", (status or "").endswith("Not a current sanction."), True)
    current = _tracer._sanctions_status("ethereum", "0x098b716b8aaf21512996dc57eb0615e2383e2f96")
    check("a current SDN listing says so", (current or "").endswith("A current sanction."), True)


def loader_tests():
    print("\n--- 4. the loader merges labels.local.json; a committed row wins a clash ---")
    a, b = "0x" + "1" * 40, "0x" + "2" * 40
    committed = {a: {"entity": "Committed Co", "type": "exchange", "citation": "c", "evidence_tier": "third_party_pack"}}
    local = {a: {"entity": "Local Override", "type": "exchange"},
             b: {"entity": "Local Only", "type": "exchange", "redistributable": False}}
    saved = (config.LABELS_PATH, config.LABELS_LOCAL_PATH)
    with tempfile.TemporaryDirectory() as tmp:
        config.LABELS_PATH = Path(tmp) / "labels.json"
        config.LABELS_LOCAL_PATH = Path(tmp) / "labels.local.json"
        config.LABELS_PATH.write_text(json.dumps(committed), encoding="utf-8")
        config.LABELS_LOCAL_PATH.write_text(json.dumps(local), encoding="utf-8")
        try:
            identify.load_labels(force_reload=True)
            check("the local-only row is loaded",
                  getattr(identify.known_label_lookup(b, chain="ethereum"), "entity", None), "Local Only")
            check("the committed row wins the clash",
                  getattr(identify.known_label_lookup(a, chain="ethereum"), "entity", None), "Committed Co")
            stats = identify.label_stats()
            check("/health counts committed and local separately",
                  (stats["committed"], stats["local"], stats["local_file_present"]), (1, 1, True))
            check("the evidence quotes the citation, not a file name",
                  "labels.json" in identify.known_label_lookup(a, chain="ethereum").evidence, False)
        finally:
            config.LABELS_PATH, config.LABELS_LOCAL_PATH = saved
            identify.load_labels(force_reload=True)


def run_all():
    file_tests()
    sdn_tests()
    resourcing_tests()
    step4_label_tests()
    loader_tests()
    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail


def test_suite():
    """pytest entry point; run directly for the per-check listing."""
    assert run_all() == 0


if __name__ == "__main__":
    sys.exit(run_all())
