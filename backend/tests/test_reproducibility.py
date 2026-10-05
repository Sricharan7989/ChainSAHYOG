"""
Trace reproducibility: every investigation is pinned to a block height.

WHY THIS SUITE EXISTS. Fetching "the newest 1,000 transactions" made a trace's
answer depend on WHEN it ran: as a busy wallet kept transacting, older transfers
fell out of the window and a finding could vanish, with nothing in either report
saying so. A defence lawyer who re-runs the trace and gets a different exchange
has broken the report. These checks pin the fix:

  * the same address traced twice at a fixed height gives identical output
  * a trace at an earlier height excludes later transfers
  * the default height is the chain head, captured once
  * a wallet whose history could not be read in full produces the caveat
  * the Etherscan client pages back from the height instead of stopping at 1,000

Run from backend/:  python -m tests.test_reproducibility
"""
import asyncio
import json
import sys

import app  # noqa: E402,F401
from app import config  # noqa: E402
from core import tracer  # noqa: E402
from services import replay  # noqa: E402
from services.etherscan import EtherscanClient, Transfer  # noqa: E402

SUSPECT = "0x" + "a" * 40
MID = "0x" + "b" * 40
BINANCE = "0x28c6c06298d514db089934071355e5743bf21d60"
COINBASE = "0xa090e606e30bd747d4e6245a1517ebe430f0057e"
HEAD = 300

fail = 0


def check(name, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got!r}" + ("" if ok else f", want {want!r}"))


def tx(frm, to, val, h, block):
    return Transfer(hash=h, from_addr=frm, to_addr=to, value=val, timestamp=1_700_000_000 + block * 12,
                    block=block, asset="ETH")


class PinnedClient:
    """A chain with a head, block timestamps, and history that honours as_of_block."""

    def __init__(self, book, truncated=()):
        self.book = book
        self.truncated = set(truncated)
        self.history_reach = {}
        self.api_calls = self.cache_hits = 0
        self.skipped_tokens = {}
        self.asked_heights = []

    def reset_stats(self):
        pass

    async def latest_block(self, chain_id):
        return HEAD

    async def block_timestamp(self, block, chain_id):
        return 1_700_000_000 + block * 12

    async def block_at(self, ts, chain_id, closest="before"):
        return (ts - 1_700_000_000) // 12

    async def get_wallet_transfers(self, address, chain_id=None, as_of_block=None):
        self.asked_heights.append(as_of_block)
        rows = [t for t in self.book.get(address, []) if as_of_block is None or t.block <= as_of_block]
        cut = address in self.truncated
        oldest = min((t.block for t in rows), default=None)
        self.history_reach[(chain_id, address, as_of_block)] = {
            "native": {"rows": len(rows), "truncated": cut, "oldest": 1_700_000_000 + (oldest or 0) * 12,
                       "oldest_block": oldest, "pages": 5},
            "token": {"rows": 0, "truncated": False, "oldest": None, "oldest_block": None, "pages": 1},
        }
        return rows


BOOK = {
    SUSPECT: [tx(SUSPECT, MID, 10.0, "0xs1", 100)],
    MID: [tx(SUSPECT, MID, 10.0, "0xs1", 100),
          tx(MID, COINBASE, 9.0, "0xtocoinbase", 120),
          tx(MID, BINANCE, 0.9, "0xtobinance", 250)],   # only after block 250
}


def run(client, **kw):
    return tracer.to_json(asyncio.run(tracer.trace(SUSPECT, max_depth=3, client=client, **kw)))


def stable(payload):
    """The payload minus run-time stats that legitimately differ between runs."""
    p = json.loads(json.dumps(payload, default=str))
    p.pop("stats", None)
    return p


def tracer_tests():
    print("--- 1. the same address at a fixed height gives identical output ---")
    a = run(PinnedClient(BOOK), as_of_block=200)
    b = run(PinnedClient(BOOK), as_of_block=200)
    check("two traces at block 200 are identical", stable(a) == stable(b), True)
    check("the height is recorded as requested", (a["as_of"]["block"], a["as_of"]["requested"]), (200, True))
    check("and in the parameters", a["params"]["as_of_block"], 200)

    print("\n--- 2. an earlier height excludes later transfers ---")
    exchanges = {x["entity"] for x in a["exchanges"]}
    check("at block 200 the Binance transfer (block 250) is not in the graph", "Binance" in exchanges, False)
    check("and Coinbase (block 120) is", "Coinbase" in exchanges, True)
    later = run(PinnedClient(BOOK), as_of_block=260)
    check("at block 260 both are", {x["entity"] for x in later["exchanges"]} >= {"Binance", "Coinbase"}, True)
    check("no edge in the block-200 graph comes from after block 200",
          all(e.get("tx_hash") != "0xtobinance" for e in a["edges"]), True)

    print("\n--- 3. by default the trace is pinned to the head, captured once ---")
    client = PinnedClient(BOOK)
    d = run(client)
    check("pinned at the head", (d["as_of"]["pinned"], d["as_of"]["block"], d["as_of"]["requested"]), (True, HEAD, False))
    check("every fetch used the same height", set(client.asked_heights), {HEAD})
    check("the statement says a re-run at that height reproduces it",
          "reproduces this result" in d["as_of"]["statement"], True)
    check("the summary carries the same as-of", d["summary"]["as_of"]["block"], HEAD)

    print("\n--- 4. a truncated wallet produces the caveat ---")
    t = run(PinnedClient(BOOK, truncated={MID}), as_of_block=200)
    check("the truncation is listed", [x["address"] for x in t["history_truncation"]], [MID])
    check("with the block it was cut at", t["history_truncation"][0]["truncated_at_block"], 100)
    check("the wallet's node is marked",
          next(n["history_truncated_at_block"] for n in t["nodes"] if n["id"] == MID), 100)
    note = t["summary"].get("history_truncation_note") or ""
    check("the summary says it is on the route, in usable words",
          "on the route to this finding" in note and "would not be seen" in note, True)
    clean = run(PinnedClient(BOOK), as_of_block=200)
    check("an untruncated trace says nothing", clean["summary"].get("history_truncation_note"), None)

    print("\n--- 5. an unpinnable client is reported, not hidden ---")

    class NoHead(PinnedClient):
        latest_block = None

    u = run(NoHead(BOOK))
    check("marked not pinned", u["as_of"]["pinned"], False)
    check("and says a re-run may differ", "NOT pinned" in u["as_of"]["statement"], True)


def replay_tests():
    print("\n--- 6. a replay states the height it was captured at ---")
    p = run(PinnedClient(BOOK), as_of_block=200)
    p["recorded_at"] = "2026-10-05T10:00:00+00:00"
    note = replay.replay_note(p)
    check("names the block and says a re-run reproduces it",
          "pinned at block 200" in note and "reproduces it" in note, True)
    old = {"recorded_at": "2026-10-04T00:00:00+00:00"}
    check("an old recording says its height is unknown", "height is not known" in replay.replay_note(old), True)
    check("a requested-height recording gets its own file",
          replay._path_for(SUSPECT, "ethereum", 200).name, f"{SUSPECT}@200.json")


def client_paging_tests():
    print("\n--- 7. the Etherscan client pages back from the height ---")

    def fake_rows(n_total):
        # n rows, one per block, newest first, ending at block 10_000.
        return [{"hash": f"0x{b:064x}", "from": SUSPECT, "to": MID, "value": "1", "blockNumber": str(b),
                 "timeStamp": str(1_700_000_000 + b), "contractAddress": ""}
                for b in range(10_000, 10_000 - n_total, -1)]

    def client_for(rows):
        c = EtherscanClient()
        calls = []

        async def fake_request(params, chain_id=None):
            calls.append(params["endblock"])
            top = params["endblock"]
            page = [r for r in rows if int(r["blockNumber"]) <= top][: params["offset"]]
            return page

        c._request = fake_request
        return c, calls

    c, calls = client_for(fake_rows(2_500))
    rows, reach = asyncio.run(c._history("txlist", SUSPECT, 1, 10_000))
    check("2,500 rows are read in full across pages", (len(rows), reach["truncated"]), (2_500, False))
    check("each page ends at the oldest block already seen", calls[:2], [10_000, 9_001])

    saved = config.MAX_HISTORY_PAGES
    config.MAX_HISTORY_PAGES = 2
    try:
        c, _ = client_for(fake_rows(2_500))
        rows, reach = asyncio.run(c._history("txlist", SUSPECT, 1, 10_000))
        check("past the page cap the history is marked truncated", reach["truncated"], True)
        # Pages overlap by one block (the boundary block is re-read whole), so two
        # pages of 1,000 reach block 8,002.
        check("at the oldest block it reached", reach["oldest_block"], 8_002)
    finally:
        config.MAX_HISTORY_PAGES = saved

    c, calls = client_for(fake_rows(50))
    rows, reach = asyncio.run(c._history("txlist", SUSPECT, 1, 9_980))
    check("nothing after the height is fetched", max(int(r["blockNumber"]) for r in rows), 9_980)
    check("a short history is one call and not truncated", (len(calls), reach["truncated"]), (1, False))


def run_all():
    tracer_tests()
    replay_tests()
    client_paging_tests()
    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail


def test_suite():
    """pytest entry point; run directly for the per-check listing."""
    assert run_all() == 0


if __name__ == "__main__":
    sys.exit(run_all())
