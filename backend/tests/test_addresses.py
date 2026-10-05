"""
Per-chain address handling (core/addresses.py) and the places that key on it.

WHY THIS SUITE EXISTS. Every address used to be lowercased. That is right for EVM
and silently wrong for Tron base58 and legacy Bitcoin, where case is part of the
address - a lowercased Tron address fails its checksum and matches nothing, and
the trace looks as if the wallet simply had no history. These checks pin:

  * a base58 Tron address survives a round trip unchanged
  * the hex (41...) and base58 (T...) forms of one Tron address are one node
  * a legacy Bitcoin address survives unchanged; bech32 is canonically lowercase
  * a label on one chain family is refused for another on format alone

Run from backend/:  python -m tests.test_addresses
"""
import json
import sys
import tempfile
from pathlib import Path

import app  # noqa: E402,F401
from app import config  # noqa: E402
from core import addresses, identify, taint, tracer  # noqa: E402
from services import replay  # noqa: E402
from services.etherscan import Transfer  # noqa: E402

# Real addresses with independently known encodings.
TRON_B58 = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"            # USDT TRC-20 contract
TRON_HEX = "41a614f803b6fd780986a42c78ec9c7f77e6ded13c"    # the same account, hex
TRON_B58_2 = "TLa2f6VPqDgRE67v1736s7bJ8Ray5wYjU7"          # a second, unrelated account
BTC_P2PKH = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"          # genesis coinbase
BTC_P2SH = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
BTC_BECH32 = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"  # BIP-173 vector
BTC_TAPROOT = "bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8ztwac72sfr9rusxg3297"  # BIP-350
EVM_MIXED = "0x28C6c06298d514Db089934071355E5743bf21d60"
EVM = EVM_MIXED.lower()

fail = 0


def check(name, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got!r}" + ("" if ok else f", want {want!r}"))


def normaliser_tests():
    print("--- 1. Tron: base58 is kept exactly; hex and base58 are one address ---")
    check("base58 survives a round trip unchanged", addresses.normalize(TRON_B58, "tron"), TRON_B58)
    check("the hex form normalises to the same base58", addresses.normalize(TRON_HEX, "tron"), TRON_B58)
    check("upper-case hex too", addresses.normalize(TRON_HEX.upper(), "tron"), TRON_B58)
    check("and back to hex for APIs that want it", addresses.tron_hex(TRON_B58), TRON_HEX)
    check("same() treats the two forms as one wallet", addresses.same(TRON_HEX, TRON_B58, "tron"), True)
    check("a lowercased base58 address is REFUSED (checksum), not silently accepted",
          addresses.is_valid(TRON_B58.lower(), "tron"), False)
    check("Tron is case-sensitive", addresses.is_case_sensitive("tron"), True)

    print("\n--- 2. Bitcoin: legacy kept exactly; bech32 canonical lowercase ---")
    check("legacy P2PKH survives unchanged", addresses.normalize(BTC_P2PKH, "bitcoin"), BTC_P2PKH)
    check("legacy P2SH survives unchanged", addresses.normalize(BTC_P2SH, "bitcoin"), BTC_P2SH)
    check("lowercased legacy is refused (checksum)", addresses.is_valid(BTC_P2PKH.lower(), "bitcoin"), False)
    check("bech32 v0 accepted", addresses.normalize(BTC_BECH32, "bitcoin"), BTC_BECH32)
    check("all-upper bech32 normalises to lowercase", addresses.normalize(BTC_BECH32.upper(), "bitcoin"), BTC_BECH32)
    check("mixed-case bech32 is refused (BIP-173)",
          addresses.is_valid(BTC_BECH32[:5] + BTC_BECH32[5:].upper(), "bitcoin"), False)
    check("taproot (bech32m) accepted", addresses.is_valid(BTC_TAPROOT, "bitcoin"), True)

    print("\n--- 3. EVM: unchanged behaviour ---")
    check("mixed case lowercases", addresses.normalize(EVM_MIXED, "polygon"), EVM)
    check("EVM is not case-sensitive", addresses.is_case_sensitive("ethereum"), False)

    print("\n--- 4. the format guard: an address only parses on its own family ---")
    check("an EVM address is not a Tron address", addresses.is_valid(EVM, "tron"), False)
    check("an EVM address is not a Bitcoin address", addresses.is_valid(EVM, "bitcoin"), False)
    check("a Tron address is not an EVM address", addresses.is_valid(TRON_B58, "ethereum"), False)
    check("a Bitcoin address is not a Tron address", addresses.is_valid(BTC_P2PKH, "tron"), False)
    check("families_for names the family it does parse as",
          (addresses.families_for(TRON_B58), addresses.families_for(EVM), addresses.families_for(BTC_P2PKH)),
          ({"tron"}, {"evm"}, {"bitcoin"}))
    check("an unknown chain keys nothing", addresses.try_normalize(EVM, "solana"), None)


def label_tests():
    print("\n--- 5. labels: per-chain keys, hex/base58 match, cross-family refused ---")
    rows = {
        "_comment": "test fixture",
        f"tron:{TRON_B58}": {"entity": "Test Exchange", "type": "exchange", "chain": "tron"},
        f"bitcoin:{BTC_P2PKH}": {"entity": "BTC Exchange", "type": "exchange", "chain": "bitcoin"},
        EVM: {"entity": "Binance", "type": "exchange", "chain": "ethereum"},
        # Mis-filed: an EVM address under Tron, and a Tron address under Ethereum.
        f"tron:{EVM}": {"entity": "Misfiled EVM", "type": "exchange", "chain": "tron"},
        f"ethereum:{TRON_B58_2}": {"entity": "Misfiled Tron", "type": "exchange", "chain": "ethereum"},
    }
    saved = config.LABELS_PATH
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "labels.json"
        path.write_text(json.dumps(rows), encoding="utf-8")
        config.LABELS_PATH = path
        try:
            identify.load_labels(force_reload=True)
            check("the base58 key is stored exactly, not lowercased",
                  ("tron", TRON_B58) in identify.load_labels(), True)
            hit_b58 = identify.known_label_lookup(TRON_B58, chain="tron")
            hit_hex = identify.known_label_lookup(TRON_HEX, chain="tron")
            check("base58 lookup finds the Tron label", getattr(hit_b58, "entity", None), "Test Exchange")
            check("the hex form finds the same label", getattr(hit_hex, "entity", None), "Test Exchange")
            check("and reports the canonical base58 address", getattr(hit_hex, "address", None), TRON_B58)
            check("a lowercased Tron address matches nothing",
                  identify.known_label_lookup(TRON_B58.lower(), chain="tron"), None)
            check("the legacy Bitcoin label is found with its case intact",
                  getattr(identify.known_label_lookup(BTC_P2PKH, chain="bitcoin"), "entity", None), "BTC Exchange")
            check("the Ethereum label still matches on Ethereum, any case",
                  getattr(identify.known_label_lookup(EVM_MIXED, chain="ethereum"), "entity", None), "Binance")
            check("the Ethereum label is NOT matched for the same string on Tron",
                  identify.known_label_lookup(EVM, chain="tron"), None)
            check("a Tron address looked up on Ethereum matches nothing",
                  identify.known_label_lookup(TRON_B58_2, chain="ethereum"), None)
            check("both mis-filed rows were refused at load by the format guard",
                  sorted(identify.rejected_label_keys), sorted([f"tron:{EVM}", f"ethereum:{TRON_B58_2}"]))
        finally:
            config.LABELS_PATH = saved
            identify.load_labels(force_reload=True)


def node_tests():
    print("\n--- 6. one Tron wallet is one node, one taint key, one cache file ---")
    node_hex = tracer._node_id(addresses.normalize(TRON_HEX, "tron"), "tron", "ethereum")
    node_b58 = tracer._node_id(addresses.normalize(TRON_B58, "tron"), "tron", "ethereum")
    check("hex and base58 resolve to the same graph node", node_hex, node_b58)
    check("and the node keeps the base58 case", node_b58, f"tron:{TRON_B58}")

    # Taint replay on a case-sensitive chain: the suspect named in hex must still be
    # found among transfers recorded in base58. Lowercasing would find nothing.
    fetched = {TRON_B58: [Transfer(hash="t1", from_addr=TRON_B58, to_addr=TRON_B58_2,
                                   value=5.0, timestamp=1, block=1, asset="TRX")]}
    result = taint.compute_taint(fetched, TRON_HEX, chain="tron")
    check("taint finds the suspect given in hex form", result.tainted_into(TRON_B58_2), {"TRX": 5.0})

    check("the replay cache file is the same for both forms",
          replay._path_for(TRON_HEX, "tron"), replay._path_for(TRON_B58, "tron"))
    check("two Tron addresses never share a cache file, even on a case-insensitive disk",
          replay._path_for(TRON_B58, "tron").name.lower() != replay._path_for(TRON_B58_2, "tron").name.lower(), True)
    check("Ethereum cache filenames are unchanged",
          replay._path_for(EVM_MIXED, "ethereum").name, f"{EVM}.json")


def run_all():
    normaliser_tests()
    label_tests()
    node_tests()
    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail


def test_suite():
    """pytest entry point; run directly for the per-check listing."""
    assert run_all() == 0


if __name__ == "__main__":
    sys.exit(run_all())
