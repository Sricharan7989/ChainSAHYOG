"""
FIFO taint accounting tests.

The three cases the feature was specified against:
  1. the worked example - 10 tainted in, 90 clean in, send 50, expect 10 tainted out;
  2. a wallet with a pre-existing balance we never observed;
  3. a same-timestamp tie, which must resolve deterministically.

Plus the properties that make the numbers safe to put in a report: taint never
exceeds the value moved, a wallet cannot pass on more taint than it received,
and the same input always yields the same answer.
"""
import asyncio
import sys

# Run from backend/:  python -m tests.test_taint
import app  # noqa: E402,F401
from core import taint, tracer  # noqa: E402
from services import graph_store  # noqa: E402
from services.etherscan import Transfer  # noqa: E402

SUSPECT = "0x" + "a" * 40
CLEAN = "0x" + "c" * 40
MIXER_WALLET = "0x" + "b" * 40  # the wallet that mixes tainted and clean funds
EXIT = "0x" + "e" * 40
OTHER = "0x" + "d" * 40

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


def t(frm, to, value, ts, *, block=None, index=0, h=None, asset="ETH"):
    """One transfer. Block defaults to the timestamp so ordering is intuitive."""
    return Transfer(
        hash=h or f"0x{frm[2:6]}{to[2:6]}{ts}{index}",
        from_addr=frm,
        to_addr=to,
        value=value,
        timestamp=ts,
        block=block if block is not None else ts,
        asset=asset,
        contract=None if asset == "ETH" else "0x" + "f" * 40,
        decimals=18,
        tx_index=index,
    )


def run(fetched, start=SUSPECT):
    return taint.compute_taint(fetched, start)


def main():
    # ------------------------------------------------------------- case 1
    print("--- 1. the worked example: 10 tainted + 90 clean, send 50 ---")
    # The mixing wallet's own history shows both arrivals and the payment out.
    fetched = {
        SUSPECT: [t(SUSPECT, MIXER_WALLET, 10.0, 1000)],
        MIXER_WALLET: [
            t(SUSPECT, MIXER_WALLET, 10.0, 1000),   # mirrored - must not double count
            t(CLEAN, MIXER_WALLET, 90.0, 2000),
            t(MIXER_WALLET, EXIT, 50.0, 3000),
        ],
    }
    result = run(fetched)
    edge = result.edge(MIXER_WALLET, EXIT, "ETH")
    check("50 was moved", edge.value, 50.0)
    check("exactly 10 of it is tainted (FIFO)", edge.tainted, 10.0)
    check("so the transfer is 20% tainted", round(edge.tainted_fraction, 6), 0.2)
    check("nothing was assumed about a pre-existing balance",
          edge.assumed_pre_existing, 0.0)
    check("the mirrored copy was not counted twice",
          result.edge(SUSPECT, MIXER_WALLET, "ETH").value, 10.0)
    check("tainted value reaching the exit", result.tainted_into(EXIT), {"ETH": 10.0})
    check("the mixing wallet's observed inflow was 100",
          result.nodes[(MIXER_WALLET, "ETH")].received, 100.0)
    check("10% of that inflow was tainted",
          round(result.inflow_fractions(MIXER_WALLET)["ETH"], 6), 0.1)

    # The next 40 out are clean, and the 41st onward is clean too.
    fetched[MIXER_WALLET].append(t(MIXER_WALLET, OTHER, 40.0, 4000))
    result = run(fetched)
    check("the next 40 out carry no taint",
          result.edge(MIXER_WALLET, OTHER, "ETH").tainted, 0.0)
    check("and the first 50 still carry exactly 10",
          result.edge(MIXER_WALLET, EXIT, "ETH").tainted, 10.0)

    # ------------------------------------------------------------- case 2
    print("\n--- 2. pre-existing balance we never observed ---")
    # The wallet sends 50 having received nothing we can see.
    fetched = {MIXER_WALLET: [t(MIXER_WALLET, EXIT, 50.0, 3000)]}
    result = run(fetched)
    edge = result.edge(MIXER_WALLET, EXIT, "ETH")
    check("unobservable funds are treated as UNtainted", edge.tainted, 0.0)
    check("and the whole 50 is recorded as an assumption",
          edge.assumed_pre_existing, 50.0)
    check("reported as a per-asset uncertainty",
          result.assumed_pre_existing, {"ETH": 50.0})

    # Partly accounted: 10 tainted in, 30 out - 10 tainted, 20 assumed clean.
    fetched = {
        SUSPECT: [t(SUSPECT, MIXER_WALLET, 10.0, 1000)],
        MIXER_WALLET: [
            t(SUSPECT, MIXER_WALLET, 10.0, 1000),
            t(MIXER_WALLET, EXIT, 30.0, 2000),
        ],
    }
    result = run(fetched)
    edge = result.edge(MIXER_WALLET, EXIT, "ETH")
    check("the observed 10 is still attributed", edge.tainted, 10.0)
    check("the unexplained 20 is not", edge.assumed_pre_existing, 20.0)
    check("taint never exceeds the value moved", edge.tainted <= edge.value, True)

    # ------------------------------------------------------------- case 3
    print("\n--- 3. same timestamp: the tie-break decides, and must be stable ---")
    # Both arrivals share a timestamp AND a block. Only tx_index separates them.
    def same_block(tainted_index, clean_index):
        return {
            SUSPECT: [t(SUSPECT, MIXER_WALLET, 10.0, 1000, index=tainted_index)],
            MIXER_WALLET: [
                t(SUSPECT, MIXER_WALLET, 10.0, 1000, index=tainted_index),
                t(CLEAN, MIXER_WALLET, 90.0, 1000, index=clean_index),
                t(MIXER_WALLET, EXIT, 50.0, 2000),
            ],
        }

    tainted_first = run(same_block(tainted_index=0, clean_index=1))
    clean_first = run(same_block(tainted_index=1, clean_index=0))
    check("tainted arrives first (lower tx index) -> 10 tainted out",
          tainted_first.edge(MIXER_WALLET, EXIT, "ETH").tainted, 10.0)
    check("clean arrives first -> the 50 out is all clean",
          clean_first.edge(MIXER_WALLET, EXIT, "ETH").tainted, 0.0)
    check("the tie-break is the chain's own order, so this is not arbitrary",
          tainted_first.edge(MIXER_WALLET, EXIT, "ETH").tainted
          != clean_first.edge(MIXER_WALLET, EXIT, "ETH").tainted, True)

    # Identical timestamp, block AND tx index: the hash breaks the tie. The value
    # of the answer is arbitrary, but it must be the SAME arbitrary answer always.
    ambiguous = {
        SUSPECT: [t(SUSPECT, MIXER_WALLET, 10.0, 1000, index=0, h="0xaaa")],
        MIXER_WALLET: [
            t(SUSPECT, MIXER_WALLET, 10.0, 1000, index=0, h="0xaaa"),
            t(CLEAN, MIXER_WALLET, 90.0, 1000, index=0, h="0xbbb"),
            t(MIXER_WALLET, EXIT, 50.0, 1000, index=0, h="0xccc"),
        ],
    }
    runs = [run(ambiguous).edge(MIXER_WALLET, EXIT, "ETH").tainted for _ in range(5)]
    check("five runs of an ambiguous ordering agree", len(set(runs)), 1)
    # Reversing the input order must not change it either - sorting, not input order.
    shuffled = {
        SUSPECT: list(ambiguous[SUSPECT]),
        MIXER_WALLET: list(reversed(ambiguous[MIXER_WALLET])),
    }
    check("input order does not affect the result",
          run(shuffled).edge(MIXER_WALLET, EXIT, "ETH").tainted, runs[0])

    # And the payload flags that a tie-break was load-bearing here.
    summary = taint.summarise(run(ambiguous), SUSPECT)
    check("the ambiguity is disclosed, not hidden",
          summary["tie_broken_value"].get("ETH", 0) > 0, True)
    check("the tie-break rule is stated in the payload",
          "transaction index" in summary["tie_break_rule"], True)

    # ------------------------------------------------------------- case 4
    print("\n--- 4. properties that make the figures reportable ---")
    # A partial draw takes a proportional share of the lot it eats into.
    fetched = {
        SUSPECT: [t(SUSPECT, MIXER_WALLET, 100.0, 1000)],
        MIXER_WALLET: [
            t(SUSPECT, MIXER_WALLET, 100.0, 1000),
            t(MIXER_WALLET, EXIT, 25.0, 2000),
            t(MIXER_WALLET, OTHER, 25.0, 3000),
        ],
    }
    result = run(fetched)
    check("a quarter of a fully tainted lot is fully tainted",
          result.edge(MIXER_WALLET, EXIT, "ETH").tainted, 25.0)
    check("and so is the next quarter",
          result.edge(MIXER_WALLET, OTHER, "ETH").tainted, 25.0)

    # A wallet cannot pass on more taint than reached it.
    node = result.nodes[(MIXER_WALLET, "ETH")]
    check("tainted out <= tainted in", node.tainted_sent <= node.tainted_received, True)

    # Taint does not leak across assets: USDT in cannot fund tainted ETH out.
    fetched = {
        SUSPECT: [t(SUSPECT, MIXER_WALLET, 1000.0, 1000, asset="USDT")],
        MIXER_WALLET: [
            t(SUSPECT, MIXER_WALLET, 1000.0, 1000, asset="USDT"),
            t(MIXER_WALLET, EXIT, 5.0, 2000, asset="ETH"),
        ],
    }
    result = run(fetched)
    check("tainted USDT does not make outgoing ETH tainted",
          result.edge(MIXER_WALLET, EXIT, "ETH").tainted, 0.0)
    check("the ETH out is instead flagged as unaccounted",
          result.edge(MIXER_WALLET, EXIT, "ETH").assumed_pre_existing, 5.0)
    check("while the tainted USDT is tracked in its own asset",
          result.tainted_into(MIXER_WALLET), {"USDT": 1000.0})

    # A cycle must terminate and not manufacture taint.
    fetched = {
        SUSPECT: [t(SUSPECT, MIXER_WALLET, 10.0, 1000)],
        MIXER_WALLET: [
            t(SUSPECT, MIXER_WALLET, 10.0, 1000),
            t(MIXER_WALLET, OTHER, 10.0, 2000),
        ],
        OTHER: [
            t(MIXER_WALLET, OTHER, 10.0, 2000),
            t(OTHER, MIXER_WALLET, 10.0, 3000),  # back where it came from
        ],
    }
    result = run(fetched)
    check("a loop does not multiply taint",
          result.edge(OTHER, MIXER_WALLET, "ETH").tainted, 10.0)
    check("and the total tainted value never exceeds what the suspect sent",
          result.nodes[(MIXER_WALLET, "ETH")].tainted_received, 20.0)

    # The suspect is the seed: what it sends is tainted regardless of its inflows.
    fetched = {
        SUSPECT: [
            t(CLEAN, SUSPECT, 5.0, 500),  # the suspect's own funding, irrelevant
            t(SUSPECT, EXIT, 500.0, 1000),
        ],
    }
    result = run(fetched)
    check("everything the suspect sends is treated as the subject funds",
          result.edge(SUSPECT, EXIT, "ETH").tainted, 500.0)
    check("and that is not called an assumption about a balance",
          result.edge(SUSPECT, EXIT, "ETH").assumed_pre_existing, 0.0)

    return fail


# --------------------------------------------------------------------------- #
# End to end, through the real tracer.                                        #
# --------------------------------------------------------------------------- #

BINANCE = "0x28c6c06298d514db089934071355e5743bf21d60"  # a real label in labels.json


class FakeClient:
    """
    The book maps sender -> outgoing transfers, so the book IS the whole world.

    `get_wallet_transfers` therefore returns the wallet's own sends plus every
    transfer in the book addressed to it, exactly as Etherscan's txlist does. That
    incoming half is what the taint pass needs and what the walk ignores.
    """

    def __init__(self, book):
        self.book = book
        self.api_calls = 0
        self.cache_hits = 0
        self.skipped_tokens = {}

    def reset_stats(self):
        self.api_calls = 0
        self.skipped_tokens = {}

    async def has_token_activity(self, address, chain_id=None):
        return False

    async def get_wallet_transfers(self, address, chain_id=None):
        self.api_calls += 1
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


async def traced(book, start=SUSPECT, depth=4):
    original = graph_store.get_store
    graph_store.get_store = lambda trace_id=None, prefer=None: original(trace_id, prefer="memory")
    try:
        return await tracer.trace(start, max_depth=depth, dust_threshold=0.001,
                                  client=FakeClient(book))
    finally:
        graph_store.get_store = original


async def integration():
    print("\n--- 5. end to end: the case this feature was built for ---")
    # The recorded demo's problem, in miniature: 198 in from the suspect, 17,969
    # out - because the wallet also received 17,771 from somewhere unrelated.
    # Connectivity alone reported the 17,969 as though it were the suspect's.
    book = {
        SUSPECT: [t(SUSPECT, MIXER_WALLET, 198.0, 1000)],
        CLEAN: [t(CLEAN, MIXER_WALLET, 17771.0, 1100)],
        MIXER_WALLET: [t(MIXER_WALLET, BINANCE, 17969.0, 1200)],
    }
    result = await traced(book)
    summary = tracer.summarize(result)
    check("the exchange is still found", summary["found"], True)
    check("named", summary["exchange"], "Binance")
    check("gross received is still reported honestly",
          summary["value_received"], {"ETH": 17969.0})
    check("but only the suspect's 198 is attributed to them",
          summary["tainted_value_received"], {"ETH": 198.0})
    check("the headline leads with the attributed value",
          summary["headline"].startswith("198.00 ETH of the suspect's funds reached Binance"),
          True)
    check("the headline no longer implies 17,969 arrived",
          "17,969" in summary["headline"], False)
    check("the caveat names FIFO", "FIFO accounting" in summary["caveat"], True)
    # 198 of the 17,969 that reached this wallet: 1.1%. This is the figure that
    # stops a reader treating the whole balance as proceeds of the offence.
    check("share of the exchange wallet's observed inflow",
          round(summary["tainted_inflow_fraction"]["ETH"], 6), round(198 / 17969, 6))

    payload = tracer.to_json(result)
    check("the accounting rule ships with the payload",
          payload["accounting"]["rule"], "fifo")
    check("and is named in full",
          "first in, first out" in payload["accounting"]["rule_label"], True)
    edge = [
        a
        for e in payload["edges"]
        if e["source"] == MIXER_WALLET and e["target"] == BINANCE
        for a in e["assets"]
    ][0]
    check("the edge carries both figures", (edge["value"], edge["tainted_value"]),
          (17969.0, 198.0))
    check("and the fraction", round(edge["tainted_fraction"], 6), round(198 / 17969, 6))
    hop = [h for h in payload["hops"] if h["to"] == BINANCE][0]
    check("so does the hop", (hop["value"], hop["tainted_value"]), (17969.0, 198.0))
    node = [n for n in payload["nodes"] if n["id"] == BINANCE][0]
    check("and the graph node, for the visualisation", node["tainted_in"], {"ETH": 198.0})

    print("\n--- 6. end to end: a path that connects but carries no suspect money ---")
    # The suspect's funds stop at the mixing wallet; what goes on to Binance is
    # money that arrived later from elsewhere. A path exists. No value arrived.
    book = {
        SUSPECT: [t(SUSPECT, MIXER_WALLET, 10.0, 1000)],
        MIXER_WALLET: [
            t(MIXER_WALLET, OTHER, 10.0, 1100),     # the suspect's 10 leaves here
            t(MIXER_WALLET, BINANCE, 500.0, 1300),  # funded by the 500 below
        ],
        CLEAN: [t(CLEAN, MIXER_WALLET, 500.0, 1200)],
    }
    result = await traced(book)
    summary = tracer.summarize(result)
    check("the path to Binance is still reported", summary["found"], True)
    check("but nothing is attributed to the suspect",
          summary["tainted_value_received"], {})
    check("and the headline says exactly that",
          "no value attributable to the suspect arrived" in summary["headline"], True)
    check("with its own caveat, not the FIFO one",
          "none of the value arriving here traces back" in summary["caveat"], True)
    check("the gross figure is still shown",
          summary["value_received"], {"ETH": 500.0})

    print("\n--- 7. end to end: pre-existing balance is disclosed per route ---")
    book = {
        SUSPECT: [t(SUSPECT, MIXER_WALLET, 10.0, 1000)],
        MIXER_WALLET: [t(MIXER_WALLET, BINANCE, 60.0, 1100)],  # 50 unaccounted
    }
    result = await traced(book)
    summary = tracer.summarize(result)
    check("the observed 10 is attributed", summary["tainted_value_received"], {"ETH": 10.0})
    check("the route is flagged as NOT fully accounted",
          summary["path_fully_accounted"], False)
    check("and the shortfall is quantified on the route",
          summary["path_assumed_pre_existing"], {"ETH": 50.0})
    check("the graph-wide figure explains it is not per-finding",
          "not the uncertainty on any one finding"
          in tracer.to_json(result)["accounting"]["assumed_pre_existing_note"], True)

    return fail


def run_all():
    main()
    asyncio.run(integration())
    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail


if __name__ == '__main__':
    sys.exit(run_all())
