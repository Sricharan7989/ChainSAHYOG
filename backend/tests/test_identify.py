"""Offline verification of identify.py and the identification-aware tracer."""
import asyncio
import sys


import networkx as nx  # noqa: E402
from core import identify  # noqa: E402
# Run from backend/:  python -m tests.<name>
# `import app` first: app/__init__ imports the services package, so importing
# a service module before the app package would hit a partially initialised
# import. Nothing else in these suites depends on import order.
import app  # noqa: E402,F401
from core import tracer  # noqa: E402
from services.etherscan import Transfer  # noqa: E402

BINANCE = "0x28c6c06298d514db089934071355e5743bf21d60"
TORNADO = "0xa160cdab225685da1d56aa342ad8841c3b53f291"
BRIDGE = "0x8315177ab297ba92a06054ce80a67ed4dbd7ed3a"

fail = 0


def check(name, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got!r}, want {want!r}")


def A(n):
    return "0x" + f"{n:040x}"


def tx(frm, to, val, h="0xh", ts=1700000000):
    return Transfer(hash=h, from_addr=frm, to_addr=to, value=val, timestamp=ts, block=1)


# --- (a) known_label_lookup ---------------------------------------------------
print("--- method (a) known_label_lookup ---")
hit = identify.known_label_lookup(BINANCE)
check("binance identified", hit.entity, "Binance")
check("binance type", hit.entity_type, "exchange")
check("binance method", hit.method, "known_label")
check("confidence < 1.0 (never certain)", hit.confidence < 1.0, True)
check("checksummed case matches", identify.known_label_lookup(BINANCE.upper().replace("0X", "0x")).entity, "Binance")
check("unknown address -> None", identify.known_label_lookup(A(7)), None)
check("tornado is mixer", identify.known_label_lookup(TORNADO).entity_type, "mixer")
check("arbitrum is bridge", identify.known_label_lookup(BRIDGE).entity_type, "bridge")
check("_comment key not loaded", "_comment" in identify.load_labels(), False)

# --- (b) consolidation_score --------------------------------------------------
print("\n--- method (b) consolidation_score ---")
g = nx.DiGraph()
target = A(99)
g.add_node(target)
for i in range(3):
    g.add_edge(A(i), target)
check("3 senders -> below min, score 0", identify.consolidation_score(target, g), 0.0)

for i in range(3, 12):
    g.add_edge(A(i), target)
check("12 senders -> saturated 1.0", identify.consolidation_score(target, g), 1.0)

g2 = nx.DiGraph()
t2 = A(98)
for i in range(8):
    g2.add_edge(A(i), t2)
s = identify.consolidation_score(t2, g2)
check("8 senders -> mid-range score", 0 < s < 1, True)
check("8 senders -> flagged", identify.consolidation_identify(t2, g2) is not None, True)
g2b = nx.DiGraph()
for i in range(5):
    g2b.add_edge(A(i), A(97))
check("5 senders -> not flagged", identify.consolidation_identify(A(97), g2b), None)

check("absent node -> 0.0", identify.consolidation_score(A(500), g2), 0.0)

g3 = nx.DiGraph()
g3.add_edge(A(1), A(1))  # self-loop only
check("self-loop not counted", identify.consolidation_score(A(1), g3), 0.0)

ident = identify.consolidation_identify(t2, g2)
check("consolidation method name", ident.method, "consolidation")
check("consolidation type is SUSPECTED", ident.entity_type, "suspected_exchange")
check("consolidation never names a company", "Unknown" in ident.entity, True)
check("consolidation confidence below label", ident.confidence < identify.LABEL_CONFIDENCE, True)

# --- (c)/(d) stubs ------------------------------------------------------------
print("\n--- methods (c)/(d) stubs ---")
check("behavioral_classifier is inert", identify.behavioral_classifier(BINANCE, g), None)
check("cospend_cluster is inert", identify.cospend_cluster(BINANCE, g), None)

# --- is_terminal --------------------------------------------------------------
print("\n--- stop rules ---")
check("exchange is terminal", identify.is_terminal(identify.known_label_lookup(BINANCE)), True)
check("mixer is terminal", identify.is_terminal(identify.known_label_lookup(TORNADO)), True)
check("bridge is terminal", identify.is_terminal(identify.known_label_lookup(BRIDGE)), True)
check("None is not terminal", identify.is_terminal(None), False)


# --- tracer integration -------------------------------------------------------
class FakeClient:
    def __init__(self, book):
        self.book = book
        self.api_calls = 0
        self.cache_hits = 0
        self.fetched = []

    def reset_stats(self):
        self.api_calls = 0
        self.cache_hits = 0

    async def has_token_activity(self, address, chain_id=None):
        return False  # offline: no token probe in these suites

    async def get_wallet_transfers(self, address, chain_id=None):
        """Both directions, as Etherscan returns them: the book is the world."""
        self.api_calls += 1
        self.fetched.append(address)
        outgoing = self.book.get(address, [])
        incoming = [
            t
            for transfers in self.book.values()
            for t in transfers
            if t.to_addr == address
        ]
        return outgoing + incoming

    async def get_outgoing_transfers(self, address, chain_id=None):
        self.api_calls += 1
        self.fetched.append(address)
        return self.book.get(address, [])


async def main():
    print("\n--- tracer integration ---")
    # A0 -> A1 -> A2 -> BINANCE -> (would continue, must not)
    book = {
        A(0): [tx(A(0), A(1), 10.0)],
        A(1): [tx(A(1), A(2), 9.0)],
        A(2): [tx(A(2), BINANCE, 8.0)],
        BINANCE: [tx(BINANCE, A(50), 7.0)],
    }
    c = FakeClient(book)
    r = await tracer.trace(A(0), max_depth=4, dust_threshold=0.001, client=c)

    check("binance never expanded", BINANCE in c.fetched, False)
    check("nothing past binance in graph", A(50) in r.graph, False)
    check("binance marked is_vasp", r.graph.nodes[BINANCE]["is_vasp"], True)
    check("one attribution", len(r.attributions), 1)
    a = r.attributions[0]
    check("attribution entity", a.entity, "Binance")
    check("attribution hop distance", a.hop_distance, 3)
    check("attribution method", a.method, "known_label")
    check("value received tracked", a.value_received_eth, 8.0)
    check("exchanges property", len(r.exchanges), 1)
    check("no false flags", len(r.flags), 0)

    s = tracer.summarize(r)
    check("summary found", s["found"], True)
    check("summary names SAHYOG action", "SAHYOG" in s["recommended_action"], True)
    check("termination reason reported", s["termination"]["reason"], "exchange_reached")

    # HONESTY OF THE CLAIM. Phase 2 required the headline to state connectivity
    # and explicitly NOT to claim value arrival, because no taint was computed.
    # Taint is computed now, so the headline states value arrival instead - and
    # that is the point: the old wording understated a finding we can now make.
    # What must not change is that every figure names its accounting rule.
    check("summary headline",
          s["headline"],
          "8.00 ETH of the suspect's funds reached Binance, 3 hops, 81% confidence")
    check("headline leads with value arrival, not mere connectivity",
          s["headline"].startswith("8.00 ETH of the suspect's funds reached"), True)
    check("taint was computed for this finding", s["taint_computed"], True)
    check("the attributed amount is carried as data too",
          s["tainted_value_received"], {"ETH": 8.0})
    check("the caveat now names the accounting rule",
          "FIFO accounting" in s.get("caveat", ""), True)
    check("and no longer claims taint is untracked",
          "not value-level taint tracking" in s.get("caveat", ""), False)

    # The Phase 2 wording is not deleted, it is CONDITIONAL. With no taint pass
    # the old caveat and the old connectivity headline are still the honest ones.
    import copy  # noqa: PLC0415 - local to keep this check self-contained
    untainted = copy.copy(r)
    untainted.taint = None
    s_untainted = tracer.summarize(untainted)
    check("without a taint pass the connectivity wording returns",
          s_untainted["headline"],
          "Transaction path connects to Binance, 3 hops, 81% confidence")
    check("and so does the connectivity caveat",
          "not value-level taint tracking" in s_untainted.get("caveat", ""), True)
    check("which is flagged as such", s_untainted["taint_computed"], False)

    j = tracer.to_json(r)
    check("json exposes attributions", len(j["attributions"]), 1)
    check("json exposes summary", j["summary"]["found"], True)
    check("json exposes termination", "termination" in j, True)
    check("json exposes token_warnings", "token_warnings" in j, True)
    check("json node carries label", [n for n in j["nodes"] if n["id"] == BINANCE][0]["label"], "Binance")

    # mixer: terminal, flagged, but NOT reported as an actionable exchange
    book2 = {A(0): [tx(A(0), TORNADO, 100.0)], TORNADO: [tx(TORNADO, A(60), 90.0)]}
    c2 = FakeClient(book2)
    r2 = await tracer.trace(A(0), max_depth=4, dust_threshold=0.001, client=c2)
    check("mixer not expanded", TORNADO in c2.fetched, False)
    check("mixer flagged", len(r2.flags), 1)
    check("mixer NOT an exchange", len(r2.exchanges), 0)
    check("mixer marked", r2.graph.nodes[TORNADO]["is_mixer"], True)
    s2 = tracer.summarize(r2)
    check("no exchange -> found False", s2["found"], False)
    check("mixer listed in summary", s2["mixers_or_bridges_crossed"], ["Tornado Cash (100 ETH pool)"])

    # nearest exchange wins when two are reachable
    book3 = {
        A(0): [tx(A(0), A(1), 10.0), tx(A(0), BINANCE, 5.0)],
        A(1): [tx(A(1), "0x71660c4005ba85c37ccec55d0c4493e66fe775d3", 9.0)],
    }
    c3 = FakeClient(book3)
    r3 = await tracer.trace(A(0), max_depth=4, dust_threshold=0.001, client=c3)
    check("two exchanges found", len(r3.exchanges), 2)
    check("nearest reported first", tracer.summarize(r3)["exchange"], "Binance")
    check("nearest hop distance", tracer.summarize(r3)["hop_distance"], 1)

    # convergence: 6 branches funnel into one unlabelled wallet
    sink = A(200)
    book4 = {A(0): [tx(A(0), A(i), 10.0) for i in range(1, 7)]}
    for i in range(1, 7):
        book4[A(i)] = [tx(A(i), sink, 9.0)]
    c4 = FakeClient(book4)
    r4 = await tracer.trace(A(0), max_depth=4, dust_threshold=0.001, client=c4)
    check("sink fan-in detected", r4.graph.nodes[sink].get("is_vasp"), True)
    sink_attr = [a for a in r4.attributions if a.address == sink]
    check("sink attributed by consolidation", sink_attr[0].method, "consolidation")
    check("sink not named as a company", sink_attr[0].entity_type, "suspected_exchange")

    print("\n--- same-address labels inferred from Ethereum are marked and scored as inferences ---")
    from core import scoring
    from types import SimpleNamespace as NS

    eth_addr = "0x28c6c06298d514db089934071355e5743bf21d60"  # Binance 14 on Ethereum
    real_load = identify.load_labels
    labels = dict(real_load())
    labels[("polygon", eth_addr)] = {
        "entity": "Binance", "type": "exchange", "chain": "polygon",
        "source": identify.INFERRED_LABEL_SOURCE,
        "inferred_from": {"chain": "ethereum", "address": eth_addr, "entity": "Binance"},
        "evidence": {"is_contract": False, "nonce": 1234},
    }
    identify.load_labels = lambda *a, **k: labels
    try:
        hit = identify.known_label_lookup(eth_addr, chain="polygon")
        check("an inferred label is found on its chain", hit is not None, True)
        check("under its own method, not as a direct label", hit.method if hit else None, "inferred_label")
        check("its evidence says it is an inference", "INFERRED" in (hit.evidence if hit else ""), True)
        check("the Ethereum label is still a direct match on Ethereum",
              identify.known_label_lookup(eth_addr, chain="ethereum").method, "known_label")
        check("and an Ethereum label never matches on a chain with no entry for it",
              identify.known_label_lookup(eth_addr, chain="arbitrum"), None)
        check("inferred labels are counted separately", identify.inferred_label_count("polygon"), 1)
    finally:
        identify.load_labels = real_load

    def score(method):
        return scoring.compute_confidence(NS(method=method, hop_distance=1, path_risk_types=set(),
                                             handoff_scores=[])).score
    check("inferred scores below a direct label", score("inferred_label") < score("known_label"), True)
    check("and above the fan-in pattern", score("inferred_label") > score("consolidation"), True)
    check("best case for an inferred label is 80", score("inferred_label"), 80)

    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail

def test_suite():
    """
    The pytest entry point. Each suite is a script of named checks that prints
    PASS/FAIL per check and returns its failure count; pytest runs the whole
    script once and fails if any check failed. Run it directly for the per-check
    listing:  python -m tests.test_identify
    """
    assert asyncio.run(main()) == 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
