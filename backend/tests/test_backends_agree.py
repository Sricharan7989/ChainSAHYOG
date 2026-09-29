"""
Prove the Neo4j and in-memory graph stores produce IDENTICAL trace results.

This is the test that makes the fallback safe. If the two backends can disagree,
then "Neo4j was down so we used memory" silently changes the answer an
investigator acts on - which would be worse than having no fallback at all.

Runs the same deterministic fake trace through both stores and diffs the full
JSON payload, field by field.
"""
import asyncio
import json
import sys


# Run from backend/:  python -m tests.test_backends_agree
import app  # noqa: E402,F401  (import app first: keeps import order safe)
from services import graph_store  # noqa: E402
from core import tracer  # noqa: E402
from services.etherscan import Transfer  # noqa: E402

BINANCE = "0x28c6c06298d514db089934071355e5743bf21d60"
COINBASE = "0x71660c4005ba85c37ccec55d0c4493e66fe775d3"
TORNADO = "0xa160cdab225685da1d56aa342ad8841c3b53f291"
BRIDGE = "0x8315177ab297ba92a06054ce80a67ed4dbd7ed3a"

fail = 0


def check(name, got, want=True):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f": got {got!r}, want {want!r}"))


def A(n):
    return "0x" + f"{n:040x}"


def tx(frm, to, val, h=None):
    return Transfer(hash=h or f"0x{abs(hash((frm,to,val)))%10**16:016x}",
                    from_addr=frm, to_addr=to, value_eth=val,
                    timestamp=1700000000, block=1)


class FakeClient:
    def __init__(self, book):
        self.book = book
        self.api_calls = 0
        self.cache_hits = 0

    def reset_stats(self):
        self.api_calls = 0

    async def has_token_activity(self, address, chain_id=None):
        return False  # offline: no token probe in these suites

    async def get_outgoing_transfers(self, address, chain_id=None):
        return self.book.get(address, [])


# A graph exercising every feature: a chain to an exchange, a mixer branch, a
# bridge branch, a 7-way convergence (consolidation), and a loop back.
SINK = A(200)
BOOK = {
    A(0): [tx(A(0), A(1), 50.0), tx(A(0), TORNADO, 30.0), tx(A(0), BRIDGE, 5.0)]
          + [tx(A(0), A(i), 10.0) for i in range(10, 17)],
    A(1): [tx(A(1), A(2), 40.0)],
    A(2): [tx(A(2), BINANCE, 35.0), tx(A(2), A(0), 1.0)],
}
for i in range(10, 17):
    BOOK[A(i)] = [tx(A(i), SINK, 9.0)]
BOOK[SINK] = [tx(SINK, COINBASE, 60.0)]


async def run(prefer):
    """Run the identical trace pinned to one backend."""
    original = graph_store.get_store
    graph_store.get_store = lambda trace_id=None, prefer=None, _p=prefer: original(trace_id, prefer=_p)
    try:
        result = await tracer.trace(A(0), max_depth=4, dust_threshold=0.001,
                                    client=FakeClient(BOOK))
        return tracer.to_json(result), result.backend
    finally:
        graph_store.get_store = original


def normalise(payload):
    """Strip fields that legitimately differ between runs (timing, backend name)."""
    p = json.loads(json.dumps(payload))
    for key in ("elapsed_sec", "api_calls", "cache_hits", "graph_backend"):
        p["stats"].pop(key, None)
    p["notes"] = sorted(p["notes"])
    return p


async def main():
    print("--- in-memory backend ---")
    mem, mem_backend = await run("memory")
    check(f"memory backend used (got {mem_backend!r})", mem_backend, "memory")
    print(f"  {mem['summary']['headline']}")
    print(f"  {mem['stats']['nodes']} nodes, {mem['stats']['edges']} edges, "
          f"{mem['stats']['identified']} identified, {len(mem['risk_flags'])} risk flags")

    print("\n--- neo4j backend ---")
    store = graph_store.get_store()
    if store.backend != "neo4j":
        # A skip is not a failure: this suite needs a database the others do
        # not, and reporting it as failing would train people to ignore reds.
        print("  SKIPPED: Neo4j not reachable - cannot compare backends.")
        print("  Start it with:  docker compose up -d   (then re-run)")
        return 0
    store.close()

    neo, neo_backend = await run(None)
    check(f"neo4j backend used (got {neo_backend!r})", neo_backend, "neo4j")
    print(f"  {neo['summary']['headline']}")
    print(f"  {neo['stats']['nodes']} nodes, {neo['stats']['edges']} edges, "
          f"{neo['stats']['identified']} identified, {len(neo['risk_flags'])} risk flags")

    print("\n--- do the two backends agree? ---")
    m, n = normalise(mem), normalise(neo)

    check("summary identical", m["summary"], n["summary"])
    check("stats identical", m["stats"], n["stats"])
    check("attributions identical", m["attributions"], n["attributions"])
    check("risk flags identical", m["risk_flags"], n["risk_flags"])
    check("nodes identical", m["nodes"], n["nodes"])
    check("edges identical", m["edges"], n["edges"])
    check("hops identical", m["hops"], n["hops"])
    check("notes identical", m["notes"], n["notes"])
    check("WHOLE PAYLOAD identical", m, n)

    if m != n:
        for key in m:
            if m[key] != n[key]:
                print(f"\n  difference in {key!r}:")
                print(f"    memory: {json.dumps(m[key])[:300]}")
                print(f"    neo4j : {json.dumps(n[key])[:300]}")

    print("\n" + ("BOTH BACKENDS AGREE" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail


sys.exit(asyncio.run(main()))
