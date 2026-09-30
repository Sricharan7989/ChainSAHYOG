"""
Laundering typology tests, on synthetic graphs.

The three cases the feature was specified against:
  1. a clean peel chain, which must fire;
  2. a chain that is CLOSE but must not fire - the important one, because a
     wrongly asserted typology in a police report is worse than a missed one;
  3. a structuring fan-out.

Plus layering, rapid pass-through, the rule that round amounts can never fire on
their own, and the exemption that stops an exchange hot wallet being reported as
a structuring suspect.
"""
import sys

# Run from backend/:  python -m tests.test_typologies
import app  # noqa: E402,F401
from app import config  # noqa: E402
from core import typologies  # noqa: E402
from services.etherscan import Transfer  # noqa: E402

fail = 0
HOUR = 3600


def check(name, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got!r}" + ("" if ok else f", want {want!r}"))


def A(n):
    return "0x" + f"{n:040x}"


_clock = [1_700_000_000]


def t(frm, to, value, ts=None, asset="ETH", index=0):
    """One transfer. Timestamps advance automatically unless pinned."""
    if ts is None:
        _clock[0] += 60
        ts = _clock[0]
    return Transfer(
        hash=f"0x{frm[2:8]}{to[2:8]}{ts}{index}{value}",
        from_addr=frm, to_addr=to, value=value, timestamp=ts,
        block=ts - 1_700_000_000, asset=asset,
        contract=None if asset == "ETH" else "0x" + "f" * 40,
        decimals=18, tx_index=index,
    )


class FakeStore:
    """Only `wallets()` is used, to supply entity types for the exemptions."""

    def __init__(self, entity_types=None):
        self._types = entity_types or {}

    def wallets(self):
        return [(a, {"entity_type": e}) for a, e in self._types.items()]


def book_to_fetched(book):
    """
    Turn sender -> transfers into the per-wallet, both-directions shape the
    detectors take, exactly as the real client returns it.
    """
    wallets = set(book) | {t_.to_addr for ts in book.values() for t_ in ts}
    return {
        w: [t_ for t_ in book.get(w, [])]
        + [t_ for ts in book.values() for t_ in ts if t_.to_addr == w]
        for w in wallets
    }


def run(book, entity_types=None):
    """
    Detect over a synthetic book.

    `taint=None` so the relevance filter is off: these fixtures test the pattern
    rules themselves, and the filter (only describe wallets carrying the suspect's
    money) is exercised separately in case 7.
    """
    detections, _suppressed = typologies.detect(
        book_to_fetched(book), FakeStore(entity_types)
    )
    return detections


def of(detections, typology):
    return [d for d in detections if d.typology == typology]


def main():
    # ------------------------------------------------------------- case 1
    print("--- 1. a clean peel chain fires ---")
    # 4 wallets in a line. Each forwards ~90% onward and peels ~10% to a
    # different side wallet, which is the defining shape.
    book = {}
    principal = 100.0
    for hop in range(4):
        src, dst, side = A(hop), A(hop + 1), A(900 + hop)
        book[src] = [
            t(src, dst, principal * 0.9),
            t(src, side, principal * 0.1),
        ]
        principal *= 0.9
    peels = of(run(book), "peel_chain")
    check("a peel chain is detected", len(peels) >= 1, True)
    d = peels[0]
    check("it reports the links it found", d.measurements["links"] >= 3, True)
    check("it names every wallet in the chain, in order",
          d.wallets[:4], [A(0), A(1), A(2), A(3)])
    check("it carries per-hop detail, not a bare boolean",
          all({"from", "to", "value", "peeled_value"} <= set(h) for h in d.hops), True)
    check("it reports the peeled side outputs",
          d.measurements["side_output_count"] >= 3, True)
    check("strength is below certainty", d.strength <= config.TYPOLOGY_STRENGTH_CAP, True)
    check("the explanation is a sentence an investigator can file",
          len(d.explanation) > 200 and "peel" in d.explanation.lower(), True)
    check("the explanation refuses to claim control of the wallets",
          "does not establish who controls" in d.explanation, True)
    check("thresholds travel with it so they can be challenged",
          d.thresholds["dominant_share"], config.PEEL_DOMINANT_SHARE)

    # ------------------------------------------------------------- case 2
    print("\n--- 2. near misses must NOT fire ---")
    # (a) Dominant share too low: a 70/30 split is a split, not a peel.
    book = {}
    for hop in range(4):
        src = A(hop)
        book[src] = [t(src, A(hop + 1), 70.0), t(src, A(900 + hop), 30.0)]
    check("a 70/30 split is not called a peel chain",
          len(of(run(book), "peel_chain")), 0)

    # (b) Dominant forward but NOTHING peeled - that is a plain forward.
    book = {A(hop): [t(A(hop), A(hop + 1), 90.0)] for hop in range(4)}
    check("a pure forward with no peel is not a peel chain",
          len(of(run(book), "peel_chain")), 0)

    # (c) Right shape, but the chain is one link short of the minimum.
    book = {}
    for hop in range(config.PEEL_MIN_LINKS - 1):
        src = A(hop)
        book[src] = [t(src, A(hop + 1), 90.0), t(src, A(900 + hop), 10.0)]
    check("a chain shorter than the minimum does not fire",
          len(of(run(book), "peel_chain")), 0)

    # (d) A second, medium-sized output breaks the peel shape: 85/10/5 is a peel,
    #     85/10 plus a 40 is a distribution.
    book = {}
    for hop in range(4):
        src = A(hop)
        book[src] = [
            t(src, A(hop + 1), 85.0),
            t(src, A(900 + hop), 10.0),
            t(src, A(800 + hop), 40.0),   # too big to be a peel
        ]
    check("a medium third output means it is a distribution, not a peel",
          len(of(run(book), "peel_chain")), 0)

    # (e) Just under the structuring similarity bar.
    book = {A(0): [t(A(0), A(10 + i), 100.0 + i * 12.0) for i in range(8)]}
    check("outputs that merely look roughly similar do not fire",
          len(of(run(book), "structuring_fan_out")), 0)

    # ------------------------------------------------------------- case 3
    print("\n--- 3. a structuring fan-out fires ---")
    # 8 outputs all within a fraction of a percent of 500.
    book = {A(0): [t(A(0), A(10 + i), 500.0 + (i % 3) * 0.5) for i in range(8)]}
    fans = of(run(book), "structuring_fan_out")
    check("a fan-out into near-equal amounts is detected", len(fans), 1)
    f = fans[0]
    check("it counts the similar outputs", f.measurements["similar_count"] >= 6, True)
    check("the variation it measured is tiny",
          f.measurements["coefficient_of_variation"] <= config.STRUCTURING_MAX_CV, True)
    check("the source wallet leads the wallet list", f.wallets[0], A(0))
    check("every recipient is listed", len(f.wallets) >= 7, True)
    check("it explains why uniformity matters",
          "chosen, not incidental" in f.explanation, True)
    check("and admits a legitimate explanation exists",
          "scheduled payments" in f.explanation, True)

    # The mirror image: many similar inputs converging on one wallet.
    book = {A(10 + i): [t(A(10 + i), A(0), 250.0)] for i in range(7)}
    fan_in = of(run(book), "structuring_fan_in")
    check("a fan-in of near-equal amounts is detected", len(fan_in), 1)
    check("it is reported as collection, not splitting",
          fan_in[0].measurements["direction"], "fan_in")

    # A labelled exchange doing exactly this must NOT be reported.
    book = {A(0): [t(A(0), A(10 + i), 500.0) for i in range(8)]}
    check("an exchange hot wallet fanning out is not structuring",
          len(of(run(book, {A(0): "exchange"}), "structuring_fan_out")), 0)
    check("nor is a mixer",
          len(of(run(book, {A(0): "mixer"}), "structuring_fan_out")), 0)

    # ------------------------------------------------------------- case 4
    print("\n--- 4. layering and rapid pass-through ---")
    # A chain forwarding ~100% at each step, minutes apart.
    book = {}
    ts = 1_800_000_000
    for hop in range(4):
        book[A(hop)] = [t(A(hop), A(hop + 1), 50.0, ts=ts + hop * 300)]
    layers = of(run(book), "layering")
    check("rapid near-total forwarding down a chain is layering", len(layers) >= 1, True)
    check("it reports the dwell time it measured",
          layers[0].measurements["max_dwell_sec"] <= config.LAYERING_MAX_DWELL_SEC, True)
    check("and concedes an automated service looks the same",
          "treasury or sweeping service" in layers[0].explanation, True)

    # The same chain, but each wallet sits on the funds for a week.
    book = {}
    for hop in range(4):
        book[A(hop)] = [t(A(hop), A(hop + 1), 50.0, ts=ts + hop * 7 * 86400)]
    check("slow forwarding is NOT layering", len(of(run(book), "layering")), 0)

    # A single wallet, in and straight out - fires even with no chain to see.
    book = {
        A(0): [t(A(0), A(1), 40.0, ts=ts)],
        A(1): [t(A(1), A(2), 39.0, ts=ts + 120)],
    }
    through = of(run(book), "rapid_pass_through")
    check("a single conduit wallet is detected", len(through) >= 1, True)
    check("it names just that wallet", through[0].wallets, [A(1)])
    check("it reports how much was forwarded",
          through[0].measurements["forward_ratio"] >= config.PASS_THROUGH_MIN_FORWARD, True)

    # A wallet that KEEPS most of what it received is not a conduit.
    book = {
        A(0): [t(A(0), A(1), 100.0, ts=ts)],
        A(1): [t(A(1), A(2), 10.0, ts=ts + 120)],
    }
    check("a wallet that keeps the funds is not a pass-through",
          len(of(run(book), "rapid_pass_through")), 0)

    # ------------------------------------------------------------- case 5
    print("\n--- 5. round amounts cannot fire alone ---")
    # Round transfers and nothing else suspicious: must produce NOTHING.
    book = {A(0): [t(A(0), A(1), 10.0), t(A(0), A(2), 20.0), t(A(0), A(3), 50.0)]}
    alone = run(book)
    check("round amounts on their own report nothing at all",
          [d.typology for d in alone], [])

    # The same round amounts alongside a real pattern: now they corroborate.
    book = {A(0): [t(A(0), A(10 + i), 500.0) for i in range(8)]}
    with_pattern = run(book)
    rounds = of(with_pattern, "round_amounts")
    check("beside another typology they are reported", len(rounds), 1)
    check("and are marked as corroboration only", rounds[0].corroborating_only, True)
    check("with a strength well below the pattern they support",
          rounds[0].strength < max(d.strength for d in with_pattern if d.typology != "round_amounts"),
          True)
    check("the explanation says so itself",
          "on its own this means very little" in rounds[0].explanation.lower(), True)

    # ------------------------------------------------------------- case 6
    print("\n--- 6. ordering, serialisation and the payload summary ---")
    book = {}
    for hop in range(4):
        src = A(hop)
        book[src] = [t(src, A(hop + 1), 90.0), t(src, A(900 + hop), 10.0)]
    detections = run(book)
    check("strongest first", detections[0].strength, max(d.strength for d in detections))
    check("every detection serialises",
          all({"typology", "name", "strength", "wallets", "hops", "explanation",
               "measurements", "thresholds"} <= set(d.to_dict()) for d in detections), True)
    summary = typologies.summarise(detections)
    check("the summary counts them", summary["count"], len(detections))
    check("it names the typologies found", "peel_chain" in summary["typologies"], True)
    check("it carries the governing caveat",
          "not conclusions about intent" in summary["caveat"], True)
    check("and says the thresholds are configurable",
          "configurable" in summary["thresholds_note"], True)
    check("nothing claims certainty",
          all(d.strength <= config.TYPOLOGY_STRENGTH_CAP for d in detections), True)

    # An empty graph must be silent, not crash.
    check("no transfers -> no detections", typologies.detect({}, None), ([], 0))

    # ------------------------------------------------------------- case 7
    print("\n--- 7. the guards added after running this on real data ---")
    # (a) A wallet that sent far MORE than we saw arrive is not a pass-through.
    #     The live demo reported "forwarded 31,809% of what it received", which is
    #     an artefact of only observing a window of each wallet's history.
    book = {
        A(0): [t(A(0), A(1), 1.0, ts=ts)],
        A(1): [t(A(1), A(2), 300.0, ts=ts + 120)],   # funded before our window
    }
    check("sending far more than we observed arriving does not fire",
          len(of(run(book), "rapid_pass_through")), 0)

    # (b) Trivial amounts are not laundering, however good the shape looks.
    book = {
        A(0): [t(A(0), A(1), 0.0008, ts=ts)],
        A(1): [t(A(1), A(2), 0.0008, ts=ts + 120)],
    }
    check("a sub-dust pass-through is not reported",
          len(of(run(book), "rapid_pass_through")), 0)

    # (c) In and out in the SAME block is a swap or contract call, not custody.
    book = {
        A(0): [t(A(0), A(1), 40.0, ts=ts)],
        A(1): [t(A(1), A(2), 40.0, ts=ts)],  # same timestamp and block
    }
    check("a same-block in-and-out is not a pass-through",
          len(of(run(book), "rapid_pass_through")), 0)

    # (d) THE RELEVANCE FILTER. With a taint result, only wallets carrying the
    #     suspect's money are described - otherwise a trace reports patterns in
    #     strangers' traffic that happens to pass through the same wallets.
    from core import taint as taint_engine  # noqa: PLC0415

    book = {A(50): [t(A(50), A(60 + i), 500.0) for i in range(8)]}  # unrelated wallet
    fetched = book_to_fetched(book)
    empty_taint = taint_engine.compute_taint(fetched, A(0))  # suspect sent nothing
    filtered, _ = typologies.detect(fetched, FakeStore(), taint=empty_taint, start=A(0))
    check("patterns in traffic unrelated to the suspect are not reported",
          len(filtered), 0)
    unfiltered, _ = typologies.detect(fetched, FakeStore())
    check("the same graph without a taint pass is still described",
          len(of(unfiltered, "structuring_fan_out")), 1)

    # (e) The cap reports what it held back.
    saved = config.TYPOLOGY_MAX_REPORTED
    try:
        config.TYPOLOGY_MAX_REPORTED = 1
        book = {}
        for hop in range(4):
            src = A(hop)
            book[src] = [t(src, A(hop + 1), 90.0), t(src, A(900 + hop), 10.0)]
        capped, suppressed = typologies.detect(book_to_fetched(book), FakeStore())
        check("the cap limits the list", len(capped), 1)
        check("and the suppressed count is reported, not hidden", suppressed > 0, True)
        check("the summary carries it",
              typologies.summarise(capped, suppressed)["suppressed"], suppressed)
    finally:
        config.TYPOLOGY_MAX_REPORTED = saved

    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail


sys.exit(main())
