"""Offline verification of tracer graph logic with a fake Etherscan client."""
import asyncio
import sys


# Run from backend/:  python -m tests.<name>
# `import app` first: app/__init__ imports the services package, so importing
# a service module before the app package would hit a partially initialised
# import. Nothing else in these suites depends on import order.
import app  # noqa: E402,F401
from core import tracer  # noqa: E402
from services.etherscan import Transfer  # noqa: E402


def A(n):
    return "0x" + f"{n:040x}"


class FakeClient:
    """Deterministic chain: A0 -> A1 -> A2 -> A3 -> A4, plus dust/loops/noise."""

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


def tx(frm, to, val, h="0xhash", ts=1700000000):
    return Transfer(hash=h, from_addr=frm, to_addr=to, value=val, timestamp=ts, block=1)


book = {
    A(0): [
        tx(A(0), A(1), 10.0, "0xbig"),
        tx(A(0), A(9), 0.0005, "0xdust"),        # dust -> must be dropped
        tx(A(0), A(1), 5.0, "0xsecond"),          # same recipient -> aggregate
    ],
    A(1): [tx(A(1), A(2), 9.0)],
    A(2): [tx(A(2), A(3), 8.0), tx(A(2), A(0), 1.0)],  # A(0) loop-back
    A(3): [tx(A(3), A(4), 7.0)],
    A(4): [tx(A(4), A(5), 6.0)],                        # beyond depth 4
}

fail = 0


def check(name, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got!r}, want {want!r}")


async def main():
    c = FakeClient(book)
    r = await tracer.trace(A(0), max_depth=4, dust_threshold=0.001, client=c)
    g, hops = r  # tuple-unpack contract

    check("dust recipient excluded", A(9) in g, False)
    check("aggregated value A0->A1",
          round(g[A(0)][A(1)]["assets"]["ETH"]["value"], 4), 15.0)
    check("aggregated tx_count", g[A(0)][A(1)]["assets"]["ETH"]["tx_count"], 2)
    check("largest tx kept as example",
          g[A(0)][A(1)]["assets"]["ETH"]["tx_hash"], "0xbig")

    check("start depth", g.nodes[A(0)]["depth"], 0)
    check("A1 depth", g.nodes[A(1)]["depth"], 1)
    check("A4 depth (at cap)", g.nodes[A(4)]["depth"], 4)
    check("A5 beyond cap not in graph", A(5) in g, False)
    check("A4 never expanded", A(4) in c.fetched, False)

    check("loop-back edge recorded", g.has_edge(A(2), A(0)), True)
    check("start not re-expanded (no refetch)", c.fetched.count(A(0)), 1)
    check("hops == edges", len(hops), g.number_of_edges())
    check("hop order is BFS", [h.depth for h in hops], sorted(h.depth for h in hops))
    check("direction: only outgoing edges", all(
        h.from_addr in book and h.to_addr in [t.to_addr for t in book[h.from_addr]]
        for h in hops), True)

    j = tracer.to_json(r)
    check("json node/edge counts", (len(j["nodes"]), len(j["edges"])),
          (g.number_of_nodes(), g.number_of_edges()))
    check("json max_depth_reached", j["stats"]["max_depth_reached"], 4)

    # depth cap actually bites
    c2 = FakeClient(book)
    r2 = await tracer.trace(A(0), max_depth=2, dust_threshold=0.001, client=c2)
    check("depth=2 stops at A2", sorted(r2.graph.nodes[n]["depth"] for n in r2.graph), [0, 1, 2])
    check("depth=2 excludes A3", A(3) in r2.graph, False)

    # dust threshold is honoured as a parameter
    c3 = FakeClient(book)
    r3 = await tracer.trace(A(0), max_depth=1, dust_threshold=0.0001, client=c3)
    check("looser dust includes A9", A(9) in r3.graph, True)

    try:
        await tracer.trace("nonsense", client=FakeClient(book))
        check("invalid address raises", False, True)
    except ValueError:
        check("invalid address raises", True, True)

    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail

def test_suite():
    """
    The pytest entry point. Each suite is a script of named checks that prints
    PASS/FAIL per check and returns its failure count; pytest runs the whole
    script once and fails if any check failed. Run it directly for the per-check
    listing:  python -m tests.test_tracer
    """
    assert asyncio.run(main()) == 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
