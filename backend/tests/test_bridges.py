"""
Cross-chain bridge handoff tests.

Two halves, in order of how much damage a mistake does:

  1. REGISTRY INTEGRITY. An address that is one character wrong never matches a
     real chain, and it fails SILENTLY - the tool reports "no match" and looks
     like it simply failed to follow the money. During development this file
     contained two such addresses (a transposed pair of hex digits in the
     Arbitrum L1 Bridge, and a stray capital letter in a lowercased gateway
     address). Both were invisible to review and were only caught by checking the
     addresses against the projects' published documentation. The tests below
     exist so that cannot recur unnoticed.

  2. MATCHING BEHAVIOUR, with no network: one clear match, two equally good
     candidates, nothing found, a fee just outside tolerance, a credit just
     outside the window, and the ETH -> WETH rename on Polygon that a naive asset
     comparison would reject as a real handoff.

The generic matching rules run against TEST_SPEC, a synthetic fee-charging
route, so they do not depend on which real bridges the registry happens to
hold. The one real route (Polygon PoS) is tested against a deposit/credit pair
checked on both chains.

Run from backend/:  python -m tests.test_bridges
"""
import json
import sys

import app  # noqa: E402,F401
from app import config  # noqa: E402
from core import bridges  # noqa: E402
from services.etherscan import Transfer  # noqa: E402

WALLET = "0x" + "a" * 40
ARB_BRIDGE = "0x8315177ab297ba92a06054ce80a67ed4dbd7ed3a"
POLY_BRIDGE = "0xa0c68c638235ee32657e8f720a23cec1bfc77c77"
TEST_BRIDGE = "0x" + "b" * 40
GATEWAY = "0x" + "6" * 40
ZERO = "0x0000000000000000000000000000000000000000"
WETH_POLYGON = "0x7ceb23fd6bc0add59e62ac25578270cff1b9f619"

# A synthetic route that charges a fee, for the generic matching rules.
TEST_SPEC = {
    "entity": "Test Bridge",
    "from_chain": "ethereum",
    "to_chain": "polygon",
    "credit_sources": (GATEWAY,),
    "asset_map": {"ETH": "ETH"},
    "window_sec": 1800,
    "min_amount": 0.05,
    "fee_tolerance": 0.02,
    "how_it_appears": "test",
    "verified_from": "test",
}

fail = 0


def check(name, got, want, tol=1e-9):
    global fail
    if isinstance(got, float) and isinstance(want, float):
        ok = abs(got - want) <= tol
    else:
        ok = got == want
    if not ok:
        fail += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got!r}" + ("" if ok else f", want {want!r}"))


def credit(value, ts, frm, to=WALLET, asset="ETH", h=None):
    """One transfer on the destination chain."""
    return Transfer(
        hash=h or f"0xcr{ts:016x}",
        from_addr=frm,
        to_addr=to,
        value=value,
        timestamp=ts,
        block=ts,
        asset=asset,
        contract=None if asset in ("ETH", "POL") else "0x" + "f" * 40,
        decimals=18,
        tx_index=0,
    )


def deposit(value=10.0, ts=1000, asset="ETH", chain="ethereum", to_chain="polygon", spec=None):
    spec = spec or TEST_SPEC
    return bridges.Deposit(
        wallet=WALLET,
        bridge=TEST_BRIDGE,
        chain=chain,
        to_chain=to_chain,
        entity=spec.get("entity", "Test Bridge"),
        asset=asset,
        dest_asset=bridges.dest_asset_for(spec, asset),
        value=value,
        timestamp=ts,
        tx_hash="0xdeposit",
    )


ARB_L2_GATEWAY = GATEWAY  # kept so the matching tests below read unchanged
SPEC = TEST_SPEC
POLY = bridges.lookup("ethereum", POLY_BRIDGE)


def registry_tests():
    print("--- 1. registry integrity: an address typo fails silently, so pin them down ---")
    hexdigits = set("0123456789abcdef")

    for (chain, addr), entry in config.BRIDGE_REGISTRY.items():
        check(f"bridge address on {chain} is lowercase", addr, addr.lower())
        check(f"bridge address on {chain} has 42 chars", len(addr), 42)
        check(f"bridge address on {chain} is hex", all(c in hexdigits for c in addr[2:]), True)
        check(f"bridge address on {chain} starts 0x", addr[:2], "0x")
        check(f"bridge address on {chain} matches its own chain", entry["from_chain"], chain)
        check(f"bridge address on {chain} leaves for a real chain", entry["to_chain"] in config.CHAIN_BY_SLUG, True)
        check(f"bridge address on {chain} does not point at itself", entry["to_chain"] != chain, True)
        check(f"bridge address on {chain} names the bridge", bool(entry.get("entity")), True)
        check(f"bridge address on {chain} has a window", int(entry.get("window_sec", 0)) > 0, True)
        check(f"bridge address on {chain} has credit sources", len(entry.get("credit_sources", ())) > 0, True)
        check(f"bridge address on {chain} cites its source", bool(entry.get("verified_from")), True)
        check(f"bridge address on {chain} explains itself", bool(entry.get("how_it_appears")), True)
        for src in entry["credit_sources"]:
            check(f"credit source {src[:10]} on {chain} is lowercase", src, src.lower())
            check(f"credit source {src[:10]} on {chain} is 42 chars", len(src), 42)

    print("\n--- 2. the one registered route, and the routes we deliberately dropped ---")
    check("Polygon RootChainManager is registered", POLY is not None, True)
    check("Polygon is the only registered route", list(config.BRIDGE_REGISTRY),
          [("ethereum", POLY_BRIDGE)])
    check("Polygon route cites verified deposit/credit pairs",
          len(POLY.get("verified_pairs", ())) >= 2, True)
    for pair in POLY.get("verified_pairs", ()):
        check(f"verified pair {pair['deposit_tx'][:10]} has full hashes",
              (len(pair["deposit_tx"]), len(pair["credit_tx"])), (66, 66))
    check("the Polygon payout is a mint from the zero address",
          ZERO in POLY["credit_sources"], True)
    check("the Polygon route is fee-free, so exact", bridges.tolerance_for(POLY), 0.0)
    check("Arbitrum is NOT registered", bridges.lookup("ethereum", ARB_BRIDGE), None)
    check("but is recognised as unsupported, with a reason",
          bool(config.bridge_unsupported_reason("ethereum", ARB_BRIDGE)), True)

    labels = json.loads(config.LABELS_PATH.read_text(encoding="utf-8"))
    for (chain, addr) in config.BRIDGE_REGISTRY:
        known = labels.get(addr)
        if known is not None:
            check(f"{addr[:10]} agrees with labels.json type", known.get("type"), "bridge")

    print("\n--- 3. lookup behaviour ---")
    check("finds a registered bridge, case-insensitively",
          bridges.lookup("ethereum", POLY_BRIDGE.upper()) is not None, True)
    check("returns None for an unknown address",
          bridges.lookup("ethereum", "0x" + "d" * 40), None)
    check("returns None for the wrong chain",
          bridges.lookup("polygon", POLY_BRIDGE), None)
    check("returns None rather than guessing on empty input",
          bridges.lookup("", ""), None)
    check("ethereum reaches polygon", config.bridge_destinations("ethereum"), {"polygon"})
    check("polygon has no registered outbound route",
          config.bridge_destinations("polygon"), set())

    print("\n--- 4. asset renaming across a bridge ---")
    check("ETH becomes WETH on the Polygon bridge",
          bridges.dest_asset_for(POLY, "ETH"), "WETH")
    check("WETH keeps its symbol on the Polygon bridge",
          bridges.dest_asset_for(POLY, "WETH"), "WETH")
    check("an unmapped asset passes through unchanged",
          bridges.dest_asset_for(SPEC, "USDC"), "USDC")
    check("a route without its own tolerance uses the default",
          bridges.tolerance_for({}), config.BRIDGE_FEE_TOLERANCE)

    return fail


def matching_tests():
    print("\n--- 5. one clear match is followed ---")
    dep = deposit()
    transfers = [credit(9.98, 1060, ARB_L2_GATEWAY)]
    cands = bridges.match_candidates(dep, transfers, SPEC)
    check("one candidate found", len(cands), 1)
    match = bridges.resolve(cands, dep, SPEC)
    check("status is matched", match.status, "matched")
    check("it is marked as an inference, not an observation", match.to_payload()["is_inference"], True)
    check("the chosen candidate is the one we found", match.chosen.tx_hash, transfers[0].hash)
    check("the credit source is recognised", match.chosen.from_known_credit_source, True)
    check("the value difference is reported, not hidden", round(match.chosen.value_delta, 4), 0.02)
    check("the time lag is reported", match.chosen.lag_sec, 60)
    check("the score is capped below certainty",
          match.chosen.score <= config.BRIDGE_MATCH_MAX_SCORE, True)
    check("the score is the sum of its parts",
          match.chosen.score,
          min(
              sum(match.chosen.components.values()),
              config.BRIDGE_MATCH_MAX_SCORE,
          ))
    check("same address reported as evidence",
          match.evidence()["destination_address_matched"], True)
    check("deposit recorded as evidence", match.evidence()["deposit_asset"], "ETH")

    print("\n--- 6. two equal candidates are ambiguous, and NEITHER is followed ---")
    transfers = [
        credit(9.98, 1060, ARB_L2_GATEWAY, h="0xaaa1"),
        credit(9.98, 1080, ARB_L2_GATEWAY, h="0xaaa2"),
    ]
    cands = bridges.match_candidates(dep, transfers, SPEC)
    check("both candidates survive", len(cands), 2)
    match = bridges.resolve(cands, dep, SPEC)
    check("status is ambiguous", match.status, "ambiguous")
    check("no candidate is chosen", match.chosen, None)
    check("BOTH candidates are still reported", len(match.candidates), 2)
    check("not reported as a match", match.to_payload()["matched"], False)
    check("the ambiguity is stated, not hidden",
          "cannot tell same-sized withdrawals apart" in match.reason, True)
    check("and the count is the real number of candidates", match.reason.startswith("2 transfers"), True)

    print("\n--- 7. a second in-tolerance credit makes it ambiguous, even when it scores far lower ---")
    transfers = [
        credit(9.99, 1005, ARB_L2_GATEWAY, h="0xnear"),
        # Same address and still within the fee tolerance, so it survives
        # filtering - but it arrives late and from a contract we do not
        # recognise, which is exactly what a weaker candidate should look like.
        credit(9.90, 1700, "0x" + "9" * 40, h="0xfar"),
    ]
    cands = bridges.match_candidates(dep, transfers, SPEC)
    check("both candidates survive filtering", len(cands), 2)
    match = bridges.resolve(cands, dep, SPEC)
    check("the score gap does not pick a winner", match.status, "ambiguous")
    check("nothing is chosen", match.chosen, None)
    check("the strongest is still listed first", match.candidates[0].tx_hash, "0xnear")
    check("and the weaker candidate is listed too", len(match.candidates), 2)

    print("\n--- 7b. two IDENTICAL credits at different lags are ambiguous ---")
    # The case the old score-margin rule got wrong: 10 ETH at +100s scored 84 and
    # 10 ETH at +1700s scored 61, so the first was silently "matched".
    transfers = [
        credit(10.0, 1100, "0x" + "9" * 40, h="0xearly"),
        credit(10.0, 2700, "0x" + "9" * 40, h="0xlate"),
    ]
    cands = bridges.match_candidates(dep, transfers, SPEC)
    check("both survive filtering", len(cands), 2)
    check("their scores differ only by lag", cands[0].score > cands[1].score, True)
    match = bridges.resolve(cands, dep, SPEC)
    check("yet the result is ambiguous", match.status, "ambiguous")
    check("and neither is followed", match.chosen, None)

    print("\n--- 8. nothing found: the trace must stop honestly, not invent a hop ---")
    match = bridges.resolve([], dep, SPEC)
    check("status is no_match", match.status, "no_match")
    check("no candidate is chosen", match.chosen, None)
    check("not reported as a match", match.to_payload()["matched"], False)
    check("the reason says the money could not be followed",
          "could not be followed" in match.reason, True)
    check("with no candidates to inspect", match.candidates, [])
    check("and no confidence claimed", match.to_payload()["confidence_score"], None)

    print("\n--- 9. a credit that arrives but cannot be the same money ---")
    check("a fee far outside tolerance is not a candidate",
          bridges.match_candidates(dep, [credit(3.0, 1060, ARB_L2_GATEWAY)], SPEC), [])
    check("a credit long after the window is not a candidate",
          bridges.match_candidates(dep, [credit(9.98, 1000 + 1801, ARB_L2_GATEWAY)], SPEC), [])
    check("a credit BEFORE the deposit is not a candidate",
          bridges.match_candidates(dep, [credit(9.98, 999, ARB_L2_GATEWAY)], SPEC), [])
    check("a credit to a different address is not a candidate",
          bridges.match_candidates(dep, [credit(9.98, 1060, ARB_L2_GATEWAY, to="0x" + "7" * 40)], SPEC), [])
    check("a credit in a different asset is not a candidate",
          bridges.match_candidates(dep, [credit(9.98, 1060, ARB_L2_GATEWAY, asset="USDC")], SPEC), [])
    check("a bridge test transaction is too small to chase",
          bridges.match_candidates(deposit(value=0.000001), [credit(0.000001, 1060, ARB_L2_GATEWAY)], SPEC), [])
    check("a fee exactly at the tolerance is still a candidate",
          len(bridges.match_candidates(dep, [credit(10.0 * (1 - SPEC["fee_tolerance"]), 1060, ARB_L2_GATEWAY)], SPEC)), 1)
    check("a credit exactly at the window edge is still a candidate",
          len(bridges.match_candidates(dep, [credit(9.98, 1000 + 1800, ARB_L2_GATEWAY)], SPEC)), 1)

    print("\n--- 10. an unknown payout contract weakens the match but does not kill it ---")
    cands = bridges.match_candidates(dep, [credit(9.98, 1060, "0x" + "9" * 40)], SPEC)
    check("still a candidate", len(cands), 1)
    check("but flagged as not a known bridge contract",
          cands[0].from_known_credit_source, False)
    check("and scores lower than the recognised-source case",
          cands[0].score < bridges.score_candidate(dep, credit(9.98, 1060, ARB_L2_GATEWAY), SPEC).score, True)

    print("\n--- 11. the real Polygon route: ETH in, WETH minted out, exact amount ---")
    # A real pair, checked through Etherscan V2 on both chains (2026-10-04):
    # 10 ETH from 0x02d2...3817 to the RootChainManager, then 10 WETH minted from
    # the zero address to the same wallet on Polygon 1,249 seconds later.
    pair = POLY["verified_pairs"][0]
    real = bridges.Deposit(
        wallet=pair["wallet"], bridge=POLY_BRIDGE, chain="ethereum", to_chain="polygon",
        entity=POLY["entity"], asset="ETH", dest_asset=bridges.dest_asset_for(POLY, "ETH"),
        value=10.0, timestamp=1791005915, tx_hash=pair["deposit_tx"],
    )

    def poly_credit(h, value, lag, asset="WETH"):
        return Transfer(
            hash=h, from_addr=ZERO, to_addr=pair["wallet"], value=value,
            timestamp=1791005915 + lag, block=94868016, asset=asset,
            contract=None if asset == "POL" else WETH_POLYGON, decimals=18, tx_index=0,
        )

    mint = poly_credit(pair["credit_tx"], 10.0, 1249)
    cands = bridges.match_candidates(real, [mint], POLY)
    match = bridges.resolve(cands, real, POLY)
    check("the real WETH mint is the match", match.status, "matched")
    check("it is the verified credit", match.chosen.tx_hash if match.chosen else None, pair["credit_tx"])
    check("the mint counts as the known payout path",
          match.chosen.from_known_credit_source if match.chosen else None, True)
    check("the asset rename is disclosed in the evidence", match.evidence()["asset_renamed_across_bridge"], True)
    check("a native POL credit of the same amount does NOT match",
          bridges.match_candidates(real, [poly_credit("0xpol", 10.0, 600, asset="POL")], POLY), [])
    check("on this fee-free route, 0.1% short is NOT the same money",
          bridges.match_candidates(real, [poly_credit("0xnear", 9.99, 600)], POLY), [])

    print("\n--- 12. outcomes that never attempted a match ---")
    m = bridges.unmatched("ethereum", "0x" + "e" * 40, "Some Bridge")
    check("unregistered bridge is not a match", m.status, "not_registered")
    check("and says the registry is the gap, not the money",
          "gap in our registry" in m.reason, True)
    m = bridges.unmatched("ethereum", ARB_BRIDGE, "Arbitrum Bridge")
    check("a dropped route is reported as unsupported", m.status, "unsupported")
    check("with its stated reason", "internal transaction" in m.reason, True)
    m = bridges.hop_cap_reached(2, 2, deposit())
    check("hop cap is not a match", m.status, "hop_cap_reached")
    check("and says the stop was deliberate", "on purpose" in m.reason, True)
    m = bridges.destination_unavailable("base", deposit())
    check("unreadable destination is not a match", m.status, "destination_unavailable")
    check("and is named", "base" in m.reason, True)

    print("\n--- 13. ordering is stable, so two runs cannot disagree ---")
    transfers = [
        credit(9.90, 1200, ARB_L2_GATEWAY, h="0xzzz"),
        credit(9.90, 1100, ARB_L2_GATEWAY, h="0xaaa"),
        credit(9.90, 1100, ARB_L2_GATEWAY, h="0xbbb"),
    ]
    first = [c.tx_hash for c in bridges.match_candidates(dep, transfers, SPEC)]
    second = [c.tx_hash for c in bridges.match_candidates(dep, list(reversed(transfers)), SPEC)]
    check("same order regardless of input order", first, second)
    check("ties broken by hash, not by arrival", first[0], "0xaaa")

    return fail


def run_all():
    registry_tests()
    matching_tests()
    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail


if __name__ == "__main__":
    sys.exit(run_all())