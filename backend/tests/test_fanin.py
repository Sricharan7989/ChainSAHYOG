"""
Fan-in correctness: a consolidation lead is decided on CHAIN-WIDE fan-in.

WHY THIS SUITE EXISTS. Counting only senders inside the traced graph cannot
tell "several of the suspect's own paths reconverge" from "an exchange collects
deposits from hundreds of unrelated customers" - the subgraph looks the same.
These checks pin the fix:

  * a reconverging self-pool (few senders chain-wide) does not fire
  * a true high-fan-in hub does, reporting both figures
  * with no chain-wide count, the lead says so and loses confidence
  * the adaptive floor is computed per chain, independent across chains

Run from backend/:  python -m tests.test_fanin
"""
import asyncio
import sys

import networkx as nx

import app  # noqa: E402,F401
from core import identify, tracer  # noqa: E402
from services import graph_store  # noqa: E402
from services.etherscan import Transfer  # noqa: E402

SUSPECT = "0x" + "a" * 40
HUB = "0x" + "e" * 40
SPLITS = ["0x" + f"{i:02d}" * 20 for i in range(1, 8)]

fail = 0


def check(name, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got!r}" + ("" if ok else f", want {want!r}"))


def tx(frm, to, val, h, i=0):
    return Transfer(hash=h, from_addr=frm, to_addr=to, value=val, timestamp=1_700_000_000 + i,
                    block=1 + i, asset="ETH")


BOOK = {SUSPECT: [tx(SUSPECT, s, 10.0, f"0xs{i}", i) for i, s in enumerate(SPLITS)]}
for i, s in enumerate(SPLITS):
    BOOK[s] = [tx(SUSPECT, s, 10.0, f"0xs{i}", i), tx(s, HUB, 9.9, f"0xh{i}", 100 + i)]


class Client:
    def __init__(self, chain_senders=None, complete=True):
        self.chain_senders = chain_senders
        self.complete = complete
        self.api_calls = self.cache_hits = 0
        self.skipped_tokens = {}
        self.history_reach = {}
        self.sender_queries = 0

    def reset_stats(self):
        pass

    async def get_wallet_transfers(self, address, chain_id=None):
        return BOOK.get(address, [])


class CountingClient(Client):
    async def get_inbound_senders(self, address, chain_id, as_of_block=None):
        self.sender_queries += 1
        return {"senders": self.chain_senders, "complete": self.complete, "rows": 1000, "calls": 2}


def run(client):
    return tracer.to_json(asyncio.run(tracer.trace(SUSPECT, max_depth=4, client=client)))


def trace_tests():
    print("--- 1. a reconverging self-pool does not fire ---")
    c = CountingClient(chain_senders=7, complete=True)
    p = run(c)
    check("no collection point is reported", p["summary"].get("lead"), False)
    checks = p["consolidation_checks"]
    check("the candidate was checked chain-wide", [x["address"] for x in checks], [HUB])
    check("and rejected with both figures", (checks[0]["kept"], checks[0]["subgraph_senders"],
                                             checks[0]["chain_senders"]), (False, 7, 7))
    check("the reason says the paths reconverge",
          "reconverge" in (checks[0]["reason"] or ""), True)
    check("one sender query, costing 2 calls",
          (c.sender_queries, checks[0]["api_calls"]), (1, 2))

    print("\n--- 2. a true high-fan-in hub fires, reporting both figures ---")
    p = run(CountingClient(chain_senders=350, complete=False))
    s = p["summary"]
    check("a collection point is reported", s.get("lead"), True)
    check("the headline gives both figures",
          "7 senders in this trace, at least 350 chain-wide" in s["headline"], True)
    check("the fan-in travels with the finding",
          (s["fan_in"]["subgraph_senders"], s["fan_in"]["chain_senders"]), (7, 350))
    check("the score credits the chain-wide count",
          any("at least 350 distinct senders chain-wide" in c["label"] for c in s["confidence_components"]),
          True)

    print("\n--- 3. without a chain-wide count, it says so and loses confidence ---")
    blind = run(Client())["summary"]
    check("still reported as a lead", blind.get("lead"), True)
    check("the headline says the chain-wide count was not obtained",
          "chain-wide count not obtained" in blind["headline"], True)
    check("the evidence says it rests on subgraph structure only",
          any("subgraph structure only" in c["label"] for c in blind["confidence_components"]), True)
    check("and it scores below the verified hub", blind["confidence_score"] < s["confidence_score"], True)


def floor_tests():
    print("\n--- 4. the adaptive floor is per chain ---")
    store = graph_store.MemoryStore()
    g = nx.DiGraph()
    # Ethereum: a dense leg - 40 wallets each receiving from 10 senders.
    for i in range(40):
        g.add_node(f"e{i}", chain="ethereum")
        for j in range(10):
            g.add_node(f"es{i}_{j}", chain="ethereum")
            g.add_edge(f"es{i}_{j}", f"e{i}")
    # Polygon: a thin leg - one wallet with 6 senders, the rest with 1.
    g.add_node("polygon:hub", chain="polygon")
    for j in range(6):
        g.add_node(f"polygon:s{j}", chain="polygon")
        g.add_edge(f"polygon:s{j}", "polygon:hub")
    store._g = g  # noqa: SLF001
    whole = identify.adaptive_fan_in_floor(store)
    eth = identify.adaptive_fan_in_floor(store, chain="ethereum")
    poly = identify.adaptive_fan_in_floor(store, chain="polygon")
    check("the Ethereum floor is set by Ethereum's dense leg", eth, 10)
    check("the Polygon floor ignores Ethereum entirely", poly <= 6, True)
    check("measured over the whole graph, Ethereum would have set Polygon's bar", whole >= poly, True)
    hit = identify.consolidation_identify("hub", store, node="polygon:hub", chain="polygon")
    check("the Polygon hub passes its own chain's floor", hit is not None, True)


def run_all():
    trace_tests()
    floor_tests()
    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail


def test_suite():
    """pytest entry point; run directly for the per-check listing."""
    assert run_all() == 0


if __name__ == "__main__":
    sys.exit(run_all())
