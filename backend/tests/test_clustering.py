"""
Entity-cluster tests.

Covers the three things that must hold:
  1. two wallets of one entity collapse into one cluster;
  2. an unlabelled consolidation group forms a SUSPECTED cluster, unnamed;
  3. hop distance is unchanged by clustering - the number the headline reports
     with clustering on is the number it reported without it.
"""
import asyncio
import sys

# Run from backend/:  python -m tests.test_clustering
import app  # noqa: E402,F401
from core import clustering, tracer  # noqa: E402
from services import graph_store  # noqa: E402
from services.etherscan import Transfer  # noqa: E402

# Two real Binance wallets and one Coinbase wallet, all in labels.json.
BINANCE_A = "0x28c6c06298d514db089934071355e5743bf21d60"
BINANCE_B = "0x21a31ee1afc51d94c2efccaa2092ad1028285549"
COINBASE = "0x71660c4005ba85c37ccec55d0c4493e66fe775d3"

fail = 0


def check(name, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got!r}" + ("" if ok else f", want {want!r}"))


def A(n):
    return "0x" + f"{n:040x}"


def tx(frm, to, val):
    return Transfer(hash="0x" + "c" * 64, from_addr=frm, to_addr=to,
                    value=val, timestamp=1700000000, block=1)


class FakeClient:
    def __init__(self, book):
        self.book = book
        self.api_calls = 0
        self.cache_hits = 0

    def reset_stats(self):
        self.api_calls = 0

    async def has_token_activity(self, address, chain_id=None):
        return False  # offline: no token probe in these suites

    async def get_wallet_transfers(self, address, chain_id=None):
        """Both directions, as Etherscan returns them: the book is the world."""
        outgoing = self.book.get(address, [])
        incoming = [
            t
            for transfers in self.book.values()
            for t in transfers
            if t.to_addr == address
        ]
        return outgoing + incoming

    async def get_outgoing_transfers(self, address, chain_id=None):
        return self.book.get(address, [])


async def run(book, start, depth=4):
    """Trace pinned to the in-memory store so the suite needs no database."""
    original = graph_store.get_store
    graph_store.get_store = lambda trace_id=None, prefer=None: original(trace_id, prefer="memory")
    try:
        return await tracer.trace(start, max_depth=depth, dust_threshold=0.001,
                                  client=FakeClient(book))
    finally:
        graph_store.get_store = original


async def main():
    # ---------------------------------------------------------------- case 1
    # Two Binance wallets reached by separate branches, plus a Coinbase wallet.
    print("--- 1. two wallets of one entity collapse into one cluster ---")
    book = {
        A(0): [tx(A(0), A(1), 50.0), tx(A(0), A(2), 40.0), tx(A(0), A(3), 30.0)],
        A(1): [tx(A(1), BINANCE_A, 45.0)],
        A(2): [tx(A(2), BINANCE_B, 35.0)],
        A(3): [tx(A(3), COINBASE, 25.0)],
    }
    result = await run(book, A(0))
    clusters = {c.cluster_id: c for c in result.clusters}

    binance = [c for c in result.clusters if c.entity == "Binance"]
    check("one Binance cluster, not two", len(binance), 1)
    check("both Binance wallets are members", sorted(binance[0].members),
          sorted([BINANCE_A, BINANCE_B]))
    check("member_count", binance[0].member_count, 2)
    check("cluster is named", binance[0].named, True)
    check("cluster method", binance[0].method, "known_label")
    check("stable cluster id", binance[0].cluster_id, "label:binance")
    check("total value across members, per asset",
          {k: round(v, 4) for k, v in binance[0].value_received.items()},
          {"ETH": 80.0})

    coinbase = [c for c in result.clusters if c.entity == "Coinbase"]
    check("Coinbase is a separate cluster", len(coinbase), 1)
    check("Coinbase has one member", coinbase[0].member_count, 1)

    # every attribution points at its cluster
    binance_attrs = [a for a in result.attributions if a.entity == "Binance"]
    check("both Binance attributions kept", len(binance_attrs), 2)
    check("both reference the same cluster",
          {a.cluster_id for a in binance_attrs}, {"label:binance"})

    payload = tracer.to_json(result)
    check("payload exposes clusters", "clusters" in payload, True)
    check("payload cluster count", payload["stats"]["clusters"], len(result.clusters))
    check("attribution carries cluster_id",
          payload["attributions"][0]["cluster_id"] is not None, True)

    # ---------------------------------------------------------------- case 2
    # Seven unlabelled wallets sweeping into one hub: a suspected cluster.
    print("\n--- 2. unlabelled consolidation group forms a suspected cluster ---")
    HUB = A(200)
    book2 = {A(0): [tx(A(0), A(i), 10.0) for i in range(10, 17)]}
    for i in range(10, 17):
        book2[A(i)] = [tx(A(i), HUB, 9.0)]
    result2 = await run(book2, A(0))

    suspected = [c for c in result2.clusters if c.method == "consolidation"]
    check("one suspected cluster", len(suspected), 1)
    cluster = suspected[0]
    check("cluster type stays suspected_exchange", cluster.entity_type, "suspected_exchange")
    check("cluster is NOT named", cluster.named, False)
    check("no company name invented", "Unknown" in cluster.entity, True)
    check("confidence within the 67% ceiling", cluster.confidence_score <= 67, True)
    check("hub recorded", cluster.hub, HUB)
    check("hub is a member", HUB in cluster.members, True)
    check("the seven sweeping wallets are members",
          all(A(i) in cluster.members for i in range(10, 17)), True)
    check("member_count = hub + 7 depositors", cluster.member_count, 8)
    check("stable id from the hub", cluster.cluster_id, f"hub:{HUB}")

    # ---------------------------------------------------------------- case 3
    # Two wallets of one entity ON THE SAME PATH at different depths.
    print("\n--- 3. hop distance is unchanged by clustering ---")
    book3 = {
        A(0): [tx(A(0), A(1), 50.0)],
        A(1): [tx(A(1), BINANCE_A, 45.0)],   # Binance at hop 2
        A(2): [tx(A(2), BINANCE_B, 20.0)],
    }
    # Binance_B sits deeper, reached via a longer branch.
    book3[A(0)].append(tx(A(0), A(5), 10.0))
    book3[A(5)] = [tx(A(5), A(2), 9.0)]      # -> A(2) -> BINANCE_B at hop 3
    result3 = await run(book3, A(0))

    per_address = {a.address: a.hop_distance for a in result3.attributions}
    check("Binance A reached at hop 2", per_address.get(BINANCE_A), 2)
    check("Binance B reached at hop 3", per_address.get(BINANCE_B), 3)

    binance3 = next(c for c in result3.clusters if c.entity == "Binance")
    check("cluster has both members", binance3.member_count, 2)
    check("cluster hop = FIRST member reached", binance3.hop_distance, 2)
    check("per-member hops preserved", binance3.member_hops,
          {BINANCE_A: 2, BINANCE_B: 3})
    check("cluster hop is not shortened below the nearest member",
          binance3.hop_distance, min(per_address[BINANCE_A], per_address[BINANCE_B]))

    summary3 = tracer.summarize(result3)
    check("headline hop count matches the nearest attribution",
          summary3["hop_distance"], 2)
    check("headline names the entity", summary3["exchange"], "Binance")
    check("summary references the cluster", summary3["cluster_id"], "label:binance")
    check("summary reports member count", summary3["cluster_members"], 2)

    payload3 = tracer.to_json(result3)
    cluster_json = next(c for c in payload3["clusters"] if c["entity"] == "Binance")
    check("payload states the hop rule",
          "first cluster member reached" in cluster_json["hop_distance_rule"], True)

    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail

def test_suite():
    """
    The pytest entry point. Each suite is a script of named checks that prints
    PASS/FAIL per check and returns its failure count; pytest runs the whole
    script once and fails if any check failed. Run it directly for the per-check
    listing:  python -m tests.test_clustering
    """
    assert asyncio.run(main()) == 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
