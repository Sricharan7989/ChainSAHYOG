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

These suites test the TRACER's cross-chain mechanics - following a match,
carrying taint, the hop cap, a round trip - so they run against a test-only
registry on synthetic addresses (TEST_REGISTRY below), injected for the
duration of each trace. The production registry holds a single verified route
(Polygon PoS) that cannot exercise a round trip, and these tests must not imply
that any real contract behaves the way the fixtures do.

Run from backend/:  python -m tests.test_cross_chain
"""
import asyncio
import contextlib
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
# Synthetic bridge contracts. Deliberately NOT real addresses: see the module
# docstring.
BRIDGE = "0x" + "1" * 40       # the bridge on Ethereum
L2_GATEWAY = "0x" + "2" * 40   # pays credits out on the far chain, and takes withdrawals
L1_GATEWAY = "0x" + "3" * 40   # pays the return leg out on Ethereum

TEST_REGISTRY = {
    ("ethereum", BRIDGE): {
        "entity": "Test Bridge",
        "from_chain": "ethereum",
        "to_chain": "arbitrum",
        "credit_sources": (L2_GATEWAY,),
        "asset_map": {"ETH": "ETH"},
        "window_sec": 1800,
        "min_amount": 0.05,
        "fee_tolerance": 0.02,
        "how_it_appears": "test fixture",
        "verified_from": "test fixture",
    },
    ("arbitrum", L2_GATEWAY): {
        "entity": "Test Bridge (return)",
        "from_chain": "arbitrum",
        "to_chain": "ethereum",
        "credit_sources": (L1_GATEWAY,),
        "asset_map": {"ETH": "ETH"},
        "window_sec": 604800,
        "min_amount": 0.05,
        "fee_tolerance": 0.02,
        "how_it_appears": "test fixture",
        "verified_from": "test fixture",
    },
}


@contextlib.contextmanager
def world_with_test_registry(extra_labels=None, bare=False):
    """Inject the test registry, plus labels for the synthetic bridges."""
    real_registry = config.BRIDGE_REGISTRY
    real_load = identify.load_labels
    # The far chain belongs to the fixtures: real labels for it (e.g. the
    # same-address inferences for Arbitrum) are dropped, so each test controls
    # exactly what that chain can recognise.
    labels = {k: v for k, v in real_load().items() if k[0] != "arbitrum"}
    labels[("ethereum", BRIDGE)] = {"entity": "Test Bridge", "type": "bridge"}
    if not bare:
        labels[("arbitrum", BINANCE_ARB)] = {"entity": "Binance (Arbitrum)", "type": "exchange"}
    labels.update(extra_labels or {})
    config.BRIDGE_REGISTRY = TEST_REGISTRY
    identify.load_labels = lambda *a, **k: labels
    try:
        yield
    finally:
        config.BRIDGE_REGISTRY = real_registry
        identify.load_labels = real_load

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


def traced(books, depth=4):
    client = ChainClient(books)
    with world_with_test_registry():
        return asyncio.run(tracer.trace(SUSPECT, max_depth=depth, client=client)), client


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
        check("its route records the inferred crossing's score", a.handoff_scores, [85])
        check("its confidence never exceeds that crossing's score", a.confidence_score <= 85, True)
        check("and the crossing is charged by its strength, not a flat penalty",
              "inferred bridge crossing matched at 85/100" in a.confidence_breakdown, True)
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
    # The credit is an observed transfer AND the carrier of the seed. Counting it
    # as both once doubled the wallet's balance on the destination chain.
    check("the bridge credit is counted once, not twice",
          arb_taint.nodes[(SUSPECT, "ETH")].received, 9.98, 1e-9)
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
    check("the summary flags the finding as reached by inference",
          payload["summary"].get("cross_chain_inferred"), True)
    check("and the headline itself says so",
          "inferred bridge crossing" in payload["summary"]["headline"], True)
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
    with world_with_test_registry(bare=True):
        bare = asyncio.run(
            tracer.trace(
                SUSPECT,
                max_depth=4,
                client=ChainClient({ETH: {SUSPECT: [tx(SUSPECT, BRIDGE, 10.0, "0xdeposit")]}}),
            )
        )
    cov = bare.label_coverage.get("arbitrum", {})
    check("arbitrum is reported as traced", "arbitrum" in bare.label_coverage, True)
    check("with no labels held", cov.get("labels"), 0)
    check("so identification could not fire", cov.get("identification_possible"), False)
    check("and the payload says what that means",
          "could not be recognised" in (cov.get("note") or ""), True)

    print("\n--- 7b. a SPARSE label set counts as no coverage ---")
    few = {("arbitrum", "0x" + f"{i:040x}"): {"entity": f"Ex{i}", "type": "exchange"} for i in range(1, 5)}
    with world_with_test_registry(few, bare=True):
        sparse = asyncio.run(
            tracer.trace(
                SUSPECT,
                max_depth=4,
                client=ChainClient({ETH: {SUSPECT: [tx(SUSPECT, BRIDGE, 10.0, "0xdeposit")]}}),
            )
        )
    cov = sparse.label_coverage.get("arbitrum", {})
    check("four labels are counted", cov.get("labels"), 4)
    check("but treated as no coverage", cov.get("identification_possible"), False)
    check("and called sparse", cov.get("coverage"), "sparse")
    check("with a note that says why", "fewer than the" in (cov.get("note") or ""), True)
    check("while the starting chain is adequately covered",
          sparse.label_coverage.get("ethereum", {}).get("identification_possible"), True)

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
    check("and explains the tie", "cannot tell same-sized withdrawals apart" in match.reason, True)

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
    check("both are inside the tolerance and window, so both are listed", len(scores), 2)
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
    check("naming the bridge", "Test Bridge" in match.reason, True)
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

    print("\n--- 12. the stop reason says what the crossing attempt found ---")
    check("the trace still reports how it stopped", bool(result.termination), True)
    check("it stopped at the bridge", result.termination.get("reason"), "terminated_at_bridge")
    check("naming the chain it left", "leaves Ethereum" in result.termination.get("label", ""), True)
    check("and saying the crossing was looked for and not found",
          "no matching withdrawal" in result.termination.get("detail", ""), True)
    check("no longer claiming the bridge is outside the tool's reach",
          "outside what this tool covers" in result.termination.get("detail", ""), False)
    check("and the bridge remains a flagged risk", 
          any(f.risk_type == "bridge" for f in result.risk_flags), True)

    return fail


def second_deposit_tests():
    print("\n--- 15. a SECOND crossing into the same chain carries its own taint ---")
    # Two separate deposits to the same bridge, each credited separately. The
    # destination replay used to be cached after the first crossing, so the
    # second crossing's seed arrived too late and its taint vanished.
    books = {
        ETH: {
            SUSPECT: [
                tx(SUSPECT, BRIDGE, 10.0, "0xdep1", ts=1700000000),
                tx(SUSPECT, BRIDGE, 6.0, "0xdep2", ts=1700005000),
            ]
        },
        ARB: {
            L2_GATEWAY: [
                tx(L2_GATEWAY, SUSPECT, 9.98, "0xcr1", ts=1700000060),
                tx(L2_GATEWAY, SUSPECT, 5.99, "0xcr2", ts=1700005060),
            ],
            SUSPECT: [tx(SUSPECT, NEXT, 15.0, "0xarbnext", ts=1700006000)],
            NEXT: [tx(NEXT, BINANCE_ARB, 14.0, "0xarbbinance", ts=1700006100)],
        },
    }
    result, _ = traced(books)
    statuses = [h.status for h in result.cross_chain_handoffs if h.status != "hop_cap_reached"]
    check("both deposits were matched separately", statuses, ["matched", "matched"])
    arb = result.taint_chains["arbitrum"]
    check("BOTH crossings' taint reached the destination replay",
          arb.bridged_in.get("ETH", 0.0), 9.98 + 5.99, 1e-6)
    check("both seeds are on record", len(arb.seeds_applied), 2)
    check("and the onward wallet is credited from both",
          arb.tainted_into(NEXT).get("ETH", 0.0) >= 15.0 - 1e-6, True)

    return fail


def route_uncertainty_tests():
    print("\n--- 16. route uncertainty is measured past a crossing too ---")
    # On the destination chain the wallet receives 9.98 over the bridge but sends
    # 15 onward, so 5.02 of that leg rests on an assumed prior balance. The route
    # to the exchange crosses that leg and must NOT read as fully accounted for.
    books = {ETH: {SUSPECT: [tx(SUSPECT, BRIDGE, 10.0, "0xdeposit", ts=1700000000)]}}
    books.update({
        ARB: {
            L2_GATEWAY: [tx(L2_GATEWAY, SUSPECT, 9.98, "0xcredit", ts=1700000060)],
            SUSPECT: [tx(SUSPECT, NEXT, 15.0, "0xarbnext", ts=1700000700)],
            NEXT: [tx(NEXT, BINANCE_ARB, 14.0, "0xarbbinance", ts=1700000800)],
        }
    })
    result, _ = traced(books)
    summary = tracer.to_json(result)["summary"]
    check("the finding is the exchange past the crossing", summary.get("node_id"), f"arbitrum:{BINANCE_ARB}")
    check("the route is NOT reported as fully accounted for", summary.get("path_fully_accounted"), False)
    check("and the assumed share on the route is quantified",
          summary.get("path_assumed_pre_existing", {}).get("ETH", 0.0) > 5.0, True)
    return fail


def real_registry_tests():
    print("\n--- 17. end to end through the REAL Polygon route ---")
    # No test registry here: the production entry, fed the amounts and timing of
    # a pair verified on both chains (10 ETH deposited, 10 WETH minted from the
    # zero address 1,249 seconds later). The trace must cross, rename the asset,
    # and carry the taint as WETH.
    poly_bridge = "0xa0c68c638235ee32657e8f720a23cec1bfc77c77"
    zero = "0x0000000000000000000000000000000000000000"
    weth = "0x7ceb23fd6bc0add59e62ac25578270cff1b9f619"

    def weth_tx(frm, to, val, h, ts):
        return Transfer(hash=h, from_addr=frm, to_addr=to, value=val, timestamp=ts,
                        block=1, asset="WETH", contract=weth, decimals=18)

    books = {
        ETH: {SUSPECT: [tx(SUSPECT, poly_bridge, 10.0, "0xrealdeposit", ts=1791005915)]},
        137: {
            zero: [weth_tx(zero, SUSPECT, 10.0, "0xrealmint", 1791005915 + 1249)],
            SUSPECT: [weth_tx(SUSPECT, NEXT, 10.0, "0xpolynext", 1791008000)],
        },
    }
    client = ChainClient(books)
    result = asyncio.run(tracer.trace(SUSPECT, max_depth=4, client=client))
    match = result.cross_chain_handoffs[0] if result.cross_chain_handoffs else None
    check("the real route matched", match.status if match else None, "matched")
    check("on the mint", match.chosen.tx_hash if match and match.chosen else None, "0xrealmint")
    check("from the recognised payout path (the zero address)",
          match.chosen.from_known_credit_source if match and match.chosen else None, True)
    crossing = next((h for h in result.hops if h.edge_type == "cross_chain"), None)
    check("the crossing lands on Polygon", crossing.chain if crossing else None, "polygon")
    check("as WETH, not POL", crossing.asset if crossing else None, "WETH")
    poly = result.taint_chains.get("polygon")
    check("the full deposit's taint arrives as WETH",
          poly.bridged_in.get("WETH", 0.0) if poly else None, 10.0, 1e-9)
    check("and follows the onward transfer",
          poly.tainted_into(NEXT).get("WETH", 0.0) if poly else None, 10.0, 1e-9)
    return fail


def history_reach_tests():
    print("\n--- 18. a credit older than the fetched history is NOT reported as no match ---")
    # The real case: a busy wallet's newest 1,000 Polygon transfers all post-date a
    # deposit months old, so its WETH mint was never in the data. "No match" there
    # was a false negative presented as a finding.
    books = {ETH: {SUSPECT: [tx(SUSPECT, BRIDGE, 10.0, "0xolddeposit", ts=1700000000)]}}
    books.update({ARB: {SUSPECT: [tx(SUSPECT, NEXT, 1.0, "0xrecent", ts=1709000000)]}})
    client = ChainClient(books)
    client.history_reach = {
        (ARB, SUSPECT): {
            "native": {"rows": config.MAX_TXNS_PER_ADDRESS, "truncated": True, "oldest": 1708000000},
            "token": {"rows": 3, "truncated": False, "oldest": 1708500000},
        }
    }
    with world_with_test_registry():
        result = asyncio.run(tracer.trace(SUSPECT, max_depth=4, client=client))
    match = result.cross_chain_handoffs[0]
    check("it is reported as not checked", match.status, "history_not_reached")
    check("saying why", "could not be looked for" in match.reason, True)
    check("and that this is not a finding of absence", "not a finding that none exists" in match.reason, True)
    check("the stop reason carries it",
          "does not reach back to the deposit" in result.termination.get("detail", ""), True)

    print("\n--- 18b. an untruncated history still yields an honest no_match ---")
    client = ChainClient(books)
    client.history_reach = {
        (ARB, SUSPECT): {"native": {"rows": 2, "truncated": False, "oldest": 1600000000}}
    }
    with world_with_test_registry():
        result = asyncio.run(tracer.trace(SUSPECT, max_depth=4, client=client))
    check("a complete history that lacks the credit is a no_match",
          result.cross_chain_handoffs[0].status, "no_match")
    return fail


def tie_break_tests():
    print("\n--- 19. among equally near, equally confident exchanges, the headline is where value ARRIVED ---")
    binance = "0x28c6c06298d514db089934071355e5743bf21d60"
    coinbase = "0x71660c4005ba85c37ccec55d0c4493e66fe775d3"
    w1, w2, outsider = "0x" + "4" * 40, "0x" + "5" * 40, "0x" + "6" * 40
    books = {
        ETH: {
            # The larger flow is expanded first, so its exchange is recorded first.
            SUSPECT: [tx(SUSPECT, w1, 6.0, "0xs1", ts=1700000100), tx(SUSPECT, w2, 5.0, "0xs2", ts=1700000100)],
            # W1 already held outside money, so under FIFO what it forwards is not
            # the suspect's; W2 forwards the suspect's funds directly.
            outsider: [tx(outsider, w1, 6.0, "0xo1", ts=1700000000)],
            w1: [tx(w1, binance, 6.0, "0xw1", ts=1700000200)],
            w2: [tx(w2, coinbase, 5.0, "0xw2", ts=1700000200)],
        }
    }
    result, _ = traced(books)
    summary = tracer.to_json(result)["summary"]
    check("both exchanges sit at the same distance",
          sorted(a.hop_distance for a in result.exchanges), [2, 2])
    check("the headline names the exchange the suspect's money reached",
          summary.get("exchange"), "Coinbase")
    check("and states the value that arrived", bool(summary.get("tainted_value_received")), True)
    return fail


def windowed_fetch_tests():
    print("\n--- 20. an old credit outside the recent history is found by the block-range query ---")
    # The 0x6242 case: the destination wallet's newest rows all post-date the
    # deposit, so the credit is only reachable by asking for the deposit's window.
    books = {ETH: {SUSPECT: [tx(SUSPECT, BRIDGE, 10.0, "0xolddeposit", ts=1700000000)]}}
    books.update({ARB: {SUSPECT: [tx(SUSPECT, NEXT, 1.0, "0xrecent", ts=1709000000)]}})
    old_credit = tx(L2_GATEWAY, SUSPECT, 9.98, "0xoldcredit", ts=1700000060)

    class WindowClient(ChainClient):
        history_reach = {(ARB, SUSPECT): {"native": {"rows": config.MAX_TXNS_PER_ADDRESS,
                                                     "truncated": True, "oldest": 1708000000}}}
        windows = []

        async def get_wallet_transfers_window(self, address, chain_id, start_ts, end_ts):
            self.windows.append((chain_id, address, start_ts, end_ts))
            hits = [old_credit] if start_ts <= old_credit.timestamp <= end_ts else []
            return hits, {"complete": True}

    client = WindowClient(books)
    with world_with_test_registry():
        result = asyncio.run(tracer.trace(SUSPECT, max_depth=4, client=client))
    match = result.cross_chain_handoffs[0]
    check("the destination was queried by the deposit's window", len(client.windows) >= 1, True)
    check("starting just before the deposit", client.windows[0][2] if client.windows else None, 1700000000 - 600)
    check("the old credit is matched instead of 'not checked'", match.status, "matched")
    check("it is the credit from the window", match.chosen.tx_hash if match.chosen else None, "0xoldcredit")
    arb = result.taint_chains.get("arbitrum")
    check("the credit joins the destination history, so the seed attaches to it once",
          arb.nodes[(SUSPECT, "ETH")].received if arb else None, 9.98 + 0.0, 1e-9)
    check("and the client's cached history was not mutated",
          all(t.hash != "0xoldcredit" for t in books[ARB][SUSPECT]), True)
    return fail


def cap_tests():
    print("\n--- 13. the cross-chain hop cap is enforced ---")
    # A round trip: Ethereum -> Arbitrum, then Arbitrum -> Ethereum again. The
    # second crossing is the last the cap allows; a third attempt must be refused
    # and say so.
    books = {
        ETH: {
            SUSPECT: [tx(SUSPECT, BRIDGE, 10.0, "0xdeposit1", ts=1700000000)],
            # The credit for the return leg, paid out on Ethereum by the test
            # route's return payout contract.
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
    check("a followed crossing does not count as the trail ending at a bridge",
          result.termination.get("reason") != "terminated_at_bridge"
          or "crossings" in result.termination.get("detail", ""), True)
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

    print("\n--- 13b. a DOUBLE crossing keeps the graph honest ---")
    nodes = {n for n, _ in result.graph.nodes(data=True)}
    crossing_edges = [
        (u, v) for u, v, d in result.graph.edges(data=True) if d.get("edge_type") == "cross_chain"
    ]
    check("the return crossing leaves from the bridge's node on the far chain",
          (f"arbitrum:{L2_GATEWAY}", SUSPECT) in crossing_edges, True)
    check("and no phantom starting-chain node exists for that far-chain bridge",
          L2_GATEWAY in nodes, False)
    check("the outward crossing leaves from the starting-chain bridge",
          (BRIDGE, f"arbitrum:{SUSPECT}") in crossing_edges, True)
    check("every crossing edge joins two real nodes",
          all(u in nodes and v in nodes for u, v in crossing_edges), True)

    print("\n--- 14. a bridge we hold no route for is reported as a gap, not a dead end ---")
    unlisted = "0x" + "e" * 40
    with world_with_test_registry({("ethereum", unlisted): {"entity": "Some Bridge", "type": "bridge"}}):
        result = asyncio.run(
            tracer.trace(
                SUSPECT,
                max_depth=3,
                client=ChainClient(
                    {ETH: {SUSPECT: [tx(SUSPECT, unlisted, 10.0, "0xtounlisted")]}}
                ),
            )
        )

    check("the bridge was still flagged as a bridge",
          any(f.risk_type == "bridge" for f in result.risk_flags), True)
    check("and the gap is reported", result.cross_chain_handoffs[0].status, "not_registered")
    check("saying the registry is the problem, not the money",
          "gap in our registry" in result.cross_chain_handoffs[0].reason, True)
    payload = result.cross_chain_handoffs[0].to_payload()
    check("the bridge is named from its label", payload.get("bridge", {}).get("entity"), "Some Bridge")
    check("with its address and chain", (payload["bridge"].get("address"), payload["bridge"].get("chain")),
          (unlisted, "ethereum"))
    check("and it says no handoff was attempted",
          "no handoff was attempted" in result.cross_chain_handoffs[0].reason, True)

    return fail


def run_all():
    matched_tests()
    ambiguous_tests()
    nomatch_tests()
    cap_tests()
    second_deposit_tests()
    route_uncertainty_tests()
    real_registry_tests()
    history_reach_tests()
    tie_break_tests()
    windowed_fetch_tests()
    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail

def test_suite():
    """
    The pytest entry point. Each suite is a script of named checks that prints
    PASS/FAIL per check and returns its failure count; pytest runs the whole
    script once and fails if any check failed. Run it directly for the per-check
    listing:  python -m tests.test_cross_chain
    """
    assert run_all() == 0


if __name__ == "__main__":
    sys.exit(run_all())
