"""
Expansion order: deterministic, best-first by the suspect's value, cap stated.

WHY THIS SUITE EXISTS. Pinning fixed WHICH transactions a trace sees, but not
WHICH wallets it chooses to expand. With a node cap, breadth-first discovery
order decided what got cut, and the same address at the same block gave 1,333
or 5,540 ETH. These checks pin the fix:

  * the same input gives identical output, whatever order the API returns rows
  * the walk is best-first: when the cap binds, the high-value branch is the
    one expanded and the low-value branch the one dropped
  * a bound cap is stated loudly, with how many wallets were left unexpanded
  * best-first never inflates a hop count: it stays the shortest distance

Run from backend/:  python -m tests.test_ordering
"""
import asyncio
import json
import random
import sys

import app  # noqa: E402,F401
from app import config  # noqa: E402
from core import tracer  # noqa: E402
from services.etherscan import Transfer  # noqa: E402

BINANCE = "0x28c6c06298d514db089934071355e5743bf21d60"
COINBASE = "0xa090e606e30bd747d4e6245a1517ebe430f0057e"


def A(i):
    return "0x" + f"{i:040x}"


fail = 0


def check(name, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got!r}" + ("" if ok else f", want {want!r}"))


def tx(frm, to, val, h, i):
    return Transfer(hash=h, from_addr=frm, to_addr=to, value=val, timestamp=1_700_000_000 + i, block=1 + i)


class Client:
    def __init__(self, book, shuffle_seed=None):
        self.book = book
        self.seed = shuffle_seed
        self.api_calls = self.cache_hits = 0
        self.skipped_tokens = {}
        self.history_reach = {}

    def reset_stats(self):
        pass

    async def get_wallet_transfers(self, address, chain_id=None):
        rows = list(self.book.get(address, [])) + [
            t for k, ts in self.book.items() if k != address for t in ts if t.to_addr == address
        ]
        if self.seed is not None:
            random.Random(f"{self.seed}{address}").shuffle(rows)
        return rows


S = A(1)
# A HIGH-value branch (100 ETH, three hops to Binance) and a LOW-value branch
# (1 ETH, two hops to Coinbase), plus noise recipients to fill a small cap.
BOOK = {
    S: [tx(S, A(10), 100.0, "h1", 1), tx(S, A(20), 1.0, "l1", 2)]
       + [tx(S, A(100 + k), 0.5, f"n{k}", 3 + k) for k in range(6)],
    A(10): [tx(S, A(10), 100.0, "h1", 1), tx(A(10), A(11), 99.0, "h2", 20)],
    A(11): [tx(A(10), A(11), 99.0, "h2", 20), tx(A(11), BINANCE, 98.0, "h3", 30)],
    A(20): [tx(S, A(20), 1.0, "l1", 2), tx(A(20), COINBASE, 0.9, "l2", 25)],
}


def run(client, depth=4):
    return tracer.to_json(asyncio.run(tracer.trace(S, max_depth=depth, client=client)))


def stable(p):
    p = json.loads(json.dumps(p, default=str))
    p.pop("stats", None)
    return p


def tests():
    print("--- 1. the same input gives the same output, whatever the row order ---")
    a = run(Client(BOOK))
    b = run(Client(BOOK))
    c = run(Client(BOOK, shuffle_seed=7))
    d = run(Client(BOOK, shuffle_seed=99))
    check("two identical runs are identical", stable(a) == stable(b), True)
    check("shuffled API row order gives the identical result", stable(a) == stable(c) == stable(d), True)

    print("\n--- 2. best-first: when the cap binds, the high-value branch survives ---")
    saved = config.MAX_NODES_PER_TRACE
    config.MAX_NODES_PER_TRACE = 11   # suspect + 8 recipients + 2 more
    try:
        p = run(Client(BOOK))
        found = {x["entity"] for x in p["exchanges"]}
        check("the 100 ETH branch reaches Binance", "Binance" in found, True)
        check("the 1 ETH branch is the one cut", "Coinbase" in found, False)
        s = p["summary"]
        check("the cap is stated in the summary", s.get("walk_capped"), True)
        note = s.get("walk_cap_note") or ""
        check("saying the graph is partial, with the unexpanded count, and that more value may exist",
              ("graph is partial" in note, "left unexpanded" in note, "larger cap may attribute more value" in note),
              (True, True, True))
        check("the unexpanded count is a number", isinstance(s["walk_cap"]["unexpanded_wallets"], int), True)
        e = run(Client(BOOK, shuffle_seed=3))
        check("and the capped result is also order-independent", stable(p) == stable(e), True)
    finally:
        config.MAX_NODES_PER_TRACE = saved
    check("an uncapped trace says nothing about a cap", a["summary"].get("walk_cap_note"), None)

    print("\n--- 3. best-first never inflates a hop count ---")
    # Binance is reachable by a long high-value route (3 hops) and a short
    # low-value one (1 hop). The reported distance must be 1.
    book = dict(BOOK)
    book[S] = BOOK[S] + [tx(S, BINANCE, 0.2, "direct", 50)]
    p = run(Client(book))
    check("hop distance is the shortest route", p["summary"].get("hop_distance"), 1)


def run_all():
    tests()
    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail


def test_suite():
    """pytest entry point; run directly for the per-check listing."""
    assert run_all() == 0


if __name__ == "__main__":
    sys.exit(run_all())
