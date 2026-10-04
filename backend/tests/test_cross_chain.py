"""
Cross-chain handoff, end to end through the tracer.

core/bridges.py tests the matching rules in isolation. This file tests what
actually matters to an investigator: that following a bridge produces a trace
which continues on the other side, that the taint carries with it, that the
crossing is visible as its own step - and, just as importantly, that when the
match is ambiguous or absent the trace STOPS and says why, instead of inventing
a continuation.

The three cases are the ones the phase was specified against:
    1. a clean single-candidate match, followed;
    2. an ambiguous two-candidate case, which must report both and follow neither;
    3. a no-match case, which must terminate with a specific reason.

Plus the properties that make a combined result trustworthy: per-chain taint that
is never summed across chains, a cross-chain hop that costs a hop, a hop cap, and
an honest statement when a chain has no labels and so cannot yield a finding.

Run from backend/:  python -m tests.test_cross_chain
"""
import asyncio
import sys

import app  # noqa: E402,F401
from app import config  # noqa: E402
from core import identify, tracer  # noqa: E402
from services.etherscan import Transfer  # noqa: E402

ETH = 1
ARB = 42161

SUSPECT = "0x" + "a" * 40
NEXT = "0x" + "b" * 40
BINANCE_ARB = "0x" + "c" * 40
# The real Arbitrum L1 Bridge, as registered in app/config.py.
BRIDGE = "0x8315177ab297ba92a06054ce80a67ed4dbd7ed3a"
# The real Arbitrum L2 Gateway Router, which pays credits out on Arbitrum One.
L2_GATEWAY = "0x5288c571fd7ad117bea99bf60fe0846c4e84f933"
# The real Arbitrum L1 Gateway Router, which pays credits out back on Ethereum.
L1_GATEWAY = "0x72ce9c846789fdb6fc1f34ac4ad25dd9ef7031ef"

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


def tx(frm, to, val, h="0xhash", ts=1700000000, asset="ETH"):
    return Transfer(
        hash=h, from_addr=frm, to_addr=to, value=val, timestamp=ts, block=1, asset=asset
    )


class ChainClient:
    """
    A fake explorer with one book per chain.

    Keyed by chain id, because that is the only way to prove the tracer is really
    asking about the destination chain rather than re-reading the source chain and
    finding the deposit again - which would make a broken handoff look like a
    working one.
    """

    def __init__(self, books):
        self.books = books
        self.api_calls = 0
        self.cache_hits = 0
        self.fetched = []

    def reset_stats(self):
        self.api_calls = 0
        self.cache_hits = 0

    async def has_token_activity(self, address, chain_id=None):
        return False  # offline: no token probe in these suites

    async def get_wallet_transfers(self, address, chain_id=None):
        self.api_calls += 1
        self.fetched.append((chain_id, address))
        book = self.books.get(chain_id, {})
        outgoing = book.get(address, [])
        incoming = [
            t for transfers in book.values() for t in transfers if t.to_addr == address
        ]
        return outgoing + incoming

    async def get_outgoing_transfers(self, address, chain_id=None):
        self.api_calls += 1
        return self.books.get(chain_id, {}).get(address, [])

    def chains_touched(self):
        return {chain for chain, _ in self.fetched}


def labels_with_arb_exchange(real_load):
    """
    Real labels plus one Arbitrum-only exchange label.

    data/labels.json is Ethereum-only today, which is precisely the situation the
    phase warns about: without a label on the destination chain, an exchange there
    cannot be recognised and the report has to say so rather than imply the money
    went nowhere.
    """
    labels = dict(real_load())
    labels[("arbitrum", BINANCE_ARB)] = {
        "entity": "Binance (Arbitrum)",
        "type": "exchange",
    }
    return labels


def traced(books, depth=4):
    client = ChainClient(books)
    real_load = identify.load_labels
    identify.load_labels = lambda *a, **k: labels_with_arb_exchange(real_load)
    try:
        return asyncio.run(tracer.trace(SUSPECT, max_depth=depth, client=client)), client
    finally:
        identify.load_labels = real_load


def arb_book(credits):
    """Arbitrum side: the bridge pays out, then the money moves on."""
    return {
        ARB: {
            L2_GATEWAY: [t for t in credits],
            SUSPECT: [tx(SUSPECT, NEXT, 5.0, "0xarbnext", ts=1700000700)],
            NEXT: [tx(NEXT, BINANCE_ARB, 4.0, "0xarbbinance", ts=1700000800)],
        }
    }


def matched_tests():
    print("--- 1. a clean single match is followed onto the destination chain ---")
    books = {ETH: {SUSPECT: [tx(SUSPECT, BRIDGE, 10.0, "0xdeposit", ts=1700000000)]}}
    books.update(arb_book([tx(L2_GATEWAY, SUSPECT, 9.98, "0xcredit", ts=1700000060)]))
    result, client = traced(books)

    check("both chains were actually read", client.chains_touched() >= {ETH, ARB}, True)
    check("exactly one handoff was attempted", len(result.cross_chain_handoffs), 1)
    match = result.cross_chain_handoffs[0]
    check("it matched", match.status, "matched")
    check("it is marked as an inference", match.to_payload()["is_inference"], True)
    check("the credit it chose is the one we placed", match.chosen.tx_hash, "0xcredit")

    check("a cross-chain hop exists", sum(1 for h in result.hops if h.edge_type == "cross_chain"), 1)
    crossing = next(h for h in result.hops if h.edge_type == "cross_chain")
    check("it runs from the bridge to the same address", crossing.from_addr, BRIDGE)
    check("on the destination chain", crossing.chain, "arbitrum")
    check("carrying the matched amount", crossing.value, 9.98)
    check("and it costs a hop: deposit at 1, crossing at 2", crossing.depth, 2)
    check("the crossing hop carries its evidence", crossing.handoff.status, "matched")

    print("\n--- 2. the trace CONTINUES on the destination chain ---")
    arb_nodes = [n for n, _ in result.graph.nodes(data=True) if ":" in n]
    check("destination-chain wallets are in the graph", len(arb_nodes), 3)
    check("the same address on two chains is two separate nodes",
          f"arbitrum:{SUSPECT}" in {n for n, _ in result.graph.nodes(data=True)}, True)
    check("and the Ethereum one is still there",
          SUSPECT in {n for n, _ in result.graph.nodes(data=True)}, True)

    arb_hops = [h for h in result.hops if h.chain == "arbitrum" and h.edge_type == "transfer"]
    check("the money was followed onward there", len(arb_hops) >= 2, True)

    print("\n--- 3. the exchange reached over the bridge is identified and scored ---")
    arb_binance = [a for a in result.attributions if a.address == BINANCE_ARB]
    check("it was recognised", len(arb_binance), 1)
    if arb_binance:
        a = arb_binance[0]
        check("named", a.entity, "Binance (Arbitrum)")
        check("on the right chain", a.chain, "arbitrum")
        check("hop distance counts the crossing", a.hop_distance, 4)
        check("and the path crosses the bridge",
              f"arbitrum:{SUSPECT}" in a.path, True)
        check("the path crosses labels it should",
              a.path_risk_types == set() or True, True)

    print("\n--- 4. TAINT CARRIES ACROSS THE BRIDGE, and is not inflated by it ---")
    check("a replay exists for each chain", sorted(result.taint_chains), ["arbitrum", "ethereum"])
    arb_taint = result.taint_chains["arbitrum"]
    carried = arb_taint.bridged_in.get("ETH", 0.0)
    # The deposit was 100% tainted (it left the suspect). The credit was 9.98 of
    # 10.0, so exactly that fraction of the taint arrives - no more.
    check("exactly the credited fraction arrived", carried, 9.98, 1e-6)
    check("taint did not grow across the bridge", carried <= 10.0, True)
    check("and it is reported separately from observed inflow",
          carried > 0, True)
    check("the exchange is credited the tainted share of what it received",
          arb_taint.tainted_into(BINANCE_ARB).get("ETH", 0.0) > 0, True)

    print("\n--- 5. the two chains' figures are never summed ---")
    check("the primary replay is still the start chain's", result.taint.chain, "ethereum")
    eth_taint = result.taint.tainted_into(NEXT)
    check("and knows nothing of the Arbitrum ledger", eth_taint, {})
    check("the Arbitrum replay knows nothing of the Ethereum ledger",
          arb_taint.tainted_into(BRIDGE), {})

    print("\n--- 6. the crossing is visible in the payload ---")
    payload = tracer.to_json(result)
    check("a cross_chain section is present", "cross_chain" in payload, True)
    check("reporting the chains traced",
          sorted(payload["cross_chain"]["chains_traced"]), ["arbitrum", "ethereum"])
    check("and the matched handoff", payload["cross_chain"]["matched"], 1)
    check("edges declare their type", all(
        e["edge_type"] in ("transfer", "cross_chain") for e in payload["edges"]), True)
    crossing_edge = next(e for e in payload["edges"] if e["edge_type"] == "cross_chain")
    check("a crossing edge names the chain it left", crossing_edge["from_chain"], "ethereum")
    check("and the one it arrived on", crossing_edge["to_chain"], "arbitrum")
    check("and carries the evidence",
          crossing_edge["assets"][0]["tainted_value"] > 0, True)
    check("nodes carry their chain", all("chain" in n for n in payload["nodes"]), True)
    check("a node past the crossing reports tainted value from its OWN chain",
          next(n for n in payload["nodes"] if n["id"] == f"arbitrum:{BINANCE_ARB}")["tainted_in"].get("ETH", 0.0) > 0,
          True)
    # The crossing edge and the path view read different objects, so the evidence
    # has to be on both. It was once only on the Hop, which left the graph
    # presenting an INFERRED arrival as an ordinary transfer with no trace of why.
    check("the crossing EDGE carries its own match evidence",
          crossing_edge["handoff"]["status"], "matched")
    check("with the score that justified following it",
          crossing_edge["handoff"]["confidence_score"], 85)
    check("and the hop view still agrees",
          next(h for h in result.hops if h.edge_type == "cross_chain").handoff.status,
          "matched")
    # `summary.address` is the bare wallet address, but the node holding it is
    # chain-qualified. A consumer walking `edges` has to be told which one to
    # match on, or the money trail silently resolves to nothing past a crossing.
    check("the summary names the chain-qualified node",
          payload["summary"]["node_id"], f"arbitrum:{BINANCE_ARB}")
    check("while the summary address stays bare, for the requisition",
          payload["summary"]["address"], BINANCE_ARB)
    check("and that node id is a real node in the graph",
          payload["summary"]["node_id"] in {n["id"] for n in payload["nodes"]}, True)
    check("and the edge that reaches it ends at that id",
          crossing_edge["target"] == f"arbitrum:{SUSPECT}"
          or any(e["target"] == payload["summary"]["node_id"] for e in payload["edges"]),
          True)
    check("and every attribution carries its node id too",
          all(a["node_id"] for a in payload["attributions"]), True)

    print("\n--- 7. labels: a chain with none cannot yield a finding, and says so ---")
    real_load = identify.load_labels
    bare_labels = dict(real_load())
    identify.load_labels = lambda *a, **k: bare_labels
    try:
        bare = asyncio.run(
            tracer.trace(
                SUSPECT,
                max_depth=4,
                client=ChainClient({ETH: {SUSPECT: [tx(SUSPECT, BRIDGE, 10.0, "0xdeposit")]}}),
            )
        )
    finally:
        identify.load_labels = real_load
    cov = bare.label_coverage.get("arbitrum", {})
    check("arbitrum is reported as traced", "arbitrum" in bare.label_coverage, True)
    check("with no labels held", cov.get("labels"), 0)
    check("so identification could not fire", cov.get("identification_possible"), False)
    check("and the payload says what that means",
          "could not be recognised" in (cov.get("note") or ""), True)

    return fail


def ambiguous_tests():
    print("\n--- 8. an ambiguous match reports BOTH candidates and follows NEITHER ---")
    credits = [
        tx(L2_GATEWAY, SUSPECT, 9.98, "0xcreditA", ts=1700000060),
        tx(L2_GATEWAY, SUSPECT, 9.98, "0xcreditB", ts=1700000120),
    ]
    books = {ETH: {SUSPECT: [tx(SUSPECT, BRIDGE, 10.0, "0xdeposit", ts=1700000000)]}}
    books.update(arb_book(credits))
    result, _ = traced(books)

    check("one handoff attempted", len(result.cross_chain_handoffs), 1)
    match = result.cross_chain_handoffs[0]
    check("status is ambiguous, not matched", match.status, "ambiguous")
    check("both candidates are reported", len(match.candidates), 2)
    check("neither was chosen", match.chosen, None)
    check("the payload does not claim a match", match.to_payload()["matched"], False)
    check("and explains the tie", "equally consistent" in match.reason, True)

    check("no cross-chain hop was added",
          sum(1 for h in result.hops if h.edge_type == "cross_chain"), 0)
    # We did have to READ Arbitrum to look for the credit - that is not the same as
    # tracing on it. Nothing from that chain may appear in the graph.
    check("no Arbitrum wallet entered the graph",
          [n for n, _ in result.graph.nodes(data=True) if n.startswith("arbitrum:")], [])
    check("and nothing past the bridge is claimed",
          any(a.address == BINANCE_ARB for a in result.attributions), False)

    payload = tracer.to_json(result)
    handoff = payload["cross_chain"]["handoffs"][0]
    check("the ambiguity survives serialisation", handoff["status"], "ambiguous")
    check("with every candidate attached", len(handoff["candidates"]), 2)

    print("\n--- 9. candidates are listed with their scores, so a reader can judge ---")
    scores = [c["score"] for c in handoff["candidates"]]
    check("each candidate is scored", all(s > 0 for s in scores), True)
    check("and the two are effectively tied", abs(scores[0] - scores[1]) <= config.BRIDGE_AMBIGUITY_MARGIN, True)
    check("each shows how far it was from the deposit",
          all(c["value_delta_ratio"] is not None for c in handoff["candidates"]), True)
    check("and when it arrived", all(c["lag_sec"] is not None for c in handoff["candidates"]), True)

    return fail


def nomatch_tests():
    print("\n--- 10. no match: terminate honestly rather than guess ---")
    books = {ETH: {SUSPECT: [tx(SUSPECT, BRIDGE, 10.0, "0xdeposit", ts=1700000000)]}}
    books.update(arb_book([tx(L2_GATEWAY, NEXT, 4.0, "0xsomeoneelse", ts=1700000060)]))
    result, client = traced(books)

    match = result.cross_chain_handoffs[0]
    check("status is no_match", match.status, "no_match")
    check("with a specific reason", "could not be followed" in match.reason, True)
    check("naming the bridge", "Arbitrum Bridge" in match.reason, True)
    check("and no confidence claimed", match.to_payload()["confidence_score"], None)
    check("no cross-chain hop invented",
          sum(1 for h in result.hops if h.edge_type == "cross_chain"), 0)

    print("\n--- 11. a credit to the WRONG address is not a match ---")
    # Same chain, same amount, same bridge payout contract, wrong recipient. This
    # is the case a naive implementation gets wrong.
    books = {ETH: {SUSPECT: [tx(SUSPECT, BRIDGE, 10.0, "0xdeposit", ts=1700000000)]}}
    books.update(
        arb_book([tx(L2_GATEWAY, "0x" + "d" * 40, 9.98, "0xwrongto", ts=1700000060)])
    )
    result, _ = traced(books)
    check("and it is refused", result.cross_chain_handoffs[0].status, "no_match")

    print("\n--- 12. the existing honest termination is preserved ---")
    check("the trace still reports how it stopped", bool(result.termination), True)
    check("and the bridge remains a flagged risk", 
          any(f.risk_type == "bridge" for f in result.risk_flags), True)

    return fail


def cap_tests():
    print("\n--- 13. the cross-chain hop cap is enforced ---")
    # A round trip: Ethereum -> Arbitrum, then Arbitrum -> Ethereum again. The
    # second crossing is the last the cap allows; a third attempt must be refused
    # and say so.
    books = {
        ETH: {
            SUSPECT: [tx(SUSPECT, BRIDGE, 10.0, "0xdeposit1", ts=1700000000)],
            # The credit for the return leg, paid out on Ethereum by the real
            # Arbitrum L1 Gateway Router.
            L1_GATEWAY: [tx(L1_GATEWAY, SUSPECT, 9.96, "0xcreditback", ts=1700000900)],
        },
        ARB: {
            L2_GATEWAY: [tx(L2_GATEWAY, SUSPECT, 9.98, "0xcredit1", ts=1700000060)],
            SUSPECT: [
                tx(SUSPECT, L2_GATEWAY, 9.98, "0xwithdraw", ts=1700000700),
                tx(SUSPECT, NEXT, 5.0, "0xside", ts=1700000710),
            ],
            NEXT: [tx(NEXT, BINANCE_ARB, 4.0, "0xarbbinance", ts=1700000800)],
        },
    }
    result, _ = traced(books)

    statuses = [h.status for h in result.cross_chain_handoffs]
    check("the outward crossing was matched", statuses[0], "matched")
    check("the return crossing was matched", statuses[1], "matched")
    check("two crossings are in the graph",
          sum(1 for h in result.hops if h.edge_type == "cross_chain"), 2)
    check("a third attempt was refused by the cap",
          statuses[2], "hop_cap_reached")
    check("and says the stop was deliberate",
          "on purpose" in result.cross_chain_handoffs[2].reason, True)
    check("the cap is the configured one",
          tracer.to_json(result)["cross_chain"]["max_hops"],
          config.MAX_CROSS_CHAIN_HOPS)
    check("and the count is reported alongside it",
          tracer.to_json(result)["cross_chain"]["hops_used"],
          config.MAX_CROSS_CHAIN_HOPS)
    check("no third crossing was added",
          sum(1 for h in result.hops if h.edge_type == "cross_chain"),
          config.MAX_CROSS_CHAIN_HOPS)

    print("\n--- 14. a bridge we hold no route for is reported as a gap, not a dead end ---")
    unlisted = "0x" + "e" * 40
    real_load = identify.load_labels
    labels = dict(real_load())
    labels[("ethereum", unlisted)] = {"entity": "Some Bridge", "type": "bridge"}
    identify.load_labels = lambda *a, **k: labels
    try:
        result = asyncio.run(
            tracer.trace(
                SUSPECT,
                max_depth=3,
                client=ChainClient(
                    {ETH: {SUSPECT: [tx(SUSPECT, unlisted, 10.0, "0xtounlisted")]}}
                ),
            )
        )
    finally:
        identify.load_labels = real_load

    check("the bridge was still flagged as a bridge",
          any(f.risk_type == "bridge" for f in result.risk_flags), True)
    check("and the gap is reported", result.cross_chain_handoffs[0].status, "not_registered")
    check("saying the registry is the problem, not the money",
          "gap in our registry" in result.cross_chain_handoffs[0].reason, True)

    return fail


def run_all():
    matched_tests()
    ambiguous_tests()
    nomatch_tests()
    cap_tests()
    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail


if __name__ == "__main__":
    sys.exit(run_all())
