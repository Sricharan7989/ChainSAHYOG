"""Verification of scoring.py and its wiring into the tracer."""
import asyncio
import sys


# Run from backend/:  python -m tests.<name>
# `import app` first: app/__init__ imports the services package, so importing
# a service module before the app package would hit a partially initialised
# import. Nothing else in these suites depends on import order.
import app  # noqa: E402,F401
from core import scoring  # noqa: E402
from core import tracer  # noqa: E402
from services.etherscan import Transfer  # noqa: E402

BINANCE = "0x28c6c06298d514db089934071355e5743bf21d60"
COINBASE = "0x71660c4005ba85c37ccec55d0c4493e66fe775d3"
TORNADO = "0xa160cdab225685da1d56aa342ad8841c3b53f291"
BRIDGE = "0x8315177ab297ba92a06054ce80a67ed4dbd7ed3a"

fail = 0


def check(name, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got!r}" + ("" if ok else f", want {want!r}"))


def A(n):
    return "0x" + f"{n:040x}"


def tx(frm, to, val, h="0xh"):
    return Transfer(hash=h, from_addr=frm, to_addr=to, value=val, timestamp=1700000000, block=1)


class Stub:
    def __init__(self, method, hops, crossed=()):
        self.method = method
        self.hop_distance = hops
        self.path_risk_types = set(crossed)


print("--- the weight table ---")
print(f"  known_label={scoring.METHOD_POINTS['known_label']}  "
      f"consolidation={scoring.METHOD_POINTS['consolidation']}  "
      f"hop_max={scoring.HOP_MAX_POINTS} decay={scoring.HOP_DECAY}  "
      f"clean=+{scoring.CLEAN_PATH_POINTS}  mixer={scoring.MIXER_PENALTY}  "
      f"bridge={scoring.BRIDGE_PENALTY}  cap={scoring.MAX_SCORE}")

print("\n--- arithmetic is transparent and adds up ---")
for label, stub, expected in [
    ("label, 1 hop, clean", Stub("known_label", 1), 50 + 30 + 15),
    ("label, 3 hops, clean", Stub("known_label", 3), 50 + 16 + 15),
    ("label, 5 hops, clean", Stub("known_label", 5), 50 + 2 + 15),
    ("consolidation, 2 hops, clean", Stub("consolidation", 2), 22 + 23 + 15),
    ("label, 2 hops, MIXER", Stub("known_label", 2, {"mixer"}), 50 + 23 - 30),
    ("label, 2 hops, BRIDGE", Stub("known_label", 2, {"bridge"}), 50 + 23 - 12),
    ("label, 2 hops, both", Stub("known_label", 2, {"mixer", "bridge"}), 50 + 23 - 30 - 12),
    ("consolidation, 4 hops, mixer", Stub("consolidation", 4, {"mixer"}), 22 + 9 - 30),
]:
    result = scoring.compute_confidence(stub)
    summed = sum(c.points for c in result.components)
    clamped = max(scoring.MIN_SCORE, min(scoring.MAX_SCORE, expected))
    check(f"{label} = {clamped}", result.score, clamped)
    check(f"  components sum to raw total", summed, expected)

print("\n--- the ceiling and floor hold ---")
best = scoring.compute_confidence(Stub("known_label", 0))
check("best possible case never hits 100", best.score <= scoring.MAX_SCORE, True)
check("best case is exactly the ceiling", best.score, 95)
check("weights are calibrated so the ceiling is reachable, never exceeded",
      sum(c.points for c in best.components), scoring.MAX_SCORE)
worst = scoring.compute_confidence(Stub("consolidation", 6, {"mixer", "bridge"}))
check("worst case never goes below floor", worst.score >= scoring.MIN_SCORE, True)

print("\n--- ordering properties an investigator would expect ---")
near = scoring.compute_confidence(Stub("known_label", 1)).score
far = scoring.compute_confidence(Stub("known_label", 4)).score
check("closer scores higher than farther", near > far, True)
labelled = scoring.compute_confidence(Stub("known_label", 2)).score
guessed = scoring.compute_confidence(Stub("consolidation", 2)).score
check("label match outscores consolidation", labelled > guessed, True)
clean = scoring.compute_confidence(Stub("known_label", 2)).score
dirty = scoring.compute_confidence(Stub("known_label", 2, {"mixer"})).score
check("mixer on path is a significant penalty", clean - dirty, 45)

print("\n--- breakdown is human readable ---")
demo = scoring.compute_confidence(Stub("known_label", 3))
print(f"  \"{demo.breakdown}\"")
check("breakdown names the method", "direct label match (+50)" in demo.breakdown, True)
check("breakdown names hop count", "3 hops from suspect (+16)" in demo.breakdown, True)
check("breakdown names clean path", "no mixer or bridge on path (+15)" in demo.breakdown, True)
mixed = scoring.compute_confidence(Stub("known_label", 2, {"mixer"}))
print(f"  \"{mixed.breakdown}\"")
check("penalty shown with sign", "(-30)" in mixed.breakdown, True)

print("\n--- risk tagging ---")
check("mixer severity", scoring.risk_severity("mixer"), "high")
check("bridge severity", scoring.risk_severity("bridge"), "medium")
check("scam severity", scoring.risk_severity("scam"), "critical")
check("sanctioned severity", scoring.risk_severity("sanctioned"), "critical")
check("exchange is not a risk", scoring.risk_severity("exchange"), None)
check("unknown type is not a risk", scoring.risk_severity("whatever"), None)


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


async def main():
    print("\n--- wired into the tracer ---")
    # clean route: suspect -> A1 -> A2 -> Binance
    book = {
        A(0): [tx(A(0), A(1), 10.0)],
        A(1): [tx(A(1), A(2), 9.0)],
        A(2): [tx(A(2), BINANCE, 8.0)],
    }
    r = await tracer.trace(A(0), max_depth=4, client=FakeClient(book))
    a = r.attributions[0]
    check("score present on attribution", a.confidence_score, 81)
    check("breakdown present", a.confidence_breakdown.startswith("direct label match (+50)"), True)
    check("0-1 confidence kept in step", a.confidence, 0.81)
    check("path reconstructed", a.path, [A(0), A(1), A(2), BINANCE])
    check("no risk types crossed", a.path_risk_types, set())
    check("json carries breakdown", "confidence_breakdown" in a.to_dict(), True)
    check("summary carries score", tracer.summarize(r)["confidence_score"], 81)
    check("summary carries breakdown", "direct label match" in tracer.summarize(r)["confidence_breakdown"], True)

    # route THROUGH a mixer to an exchange: penalty must apply
    book2 = {
        A(0): [tx(A(0), TORNADO, 100.0)],
        TORNADO: [tx(TORNADO, BINANCE, 90.0)],
    }
    r2 = await tracer.trace(A(0), max_depth=4, client=FakeClient(book2))
    # the mixer terminates the branch, so Binance is NOT reached through it
    check("mixer stops the branch", [x.entity for x in r2.exchanges], [])
    check("mixer raises a risk flag", len(r2.risk_flags), 1)
    flag = r2.risk_flags[0]
    check("risk type", flag.risk_type, "mixer")
    check("risk severity", flag.severity, "high")
    check("risk flag on primary path", flag.on_primary_path, True)
    check("risk note is plain language", "severs the link" in flag.note, True)

    # a bridge and an exchange on separate branches
    book3 = {
        A(0): [tx(A(0), A(1), 10.0), tx(A(0), BRIDGE, 5.0)],
        A(1): [tx(A(1), COINBASE, 9.0)],
    }
    r3 = await tracer.trace(A(0), max_depth=4, client=FakeClient(book3))
    types = {f.risk_type for f in r3.risk_flags}
    check("bridge flagged", types, {"bridge"})
    bridge_flag = next(f for f in r3.risk_flags if f.risk_type == "bridge")
    check("bridge NOT on the path to the exchange", bridge_flag.on_primary_path, False)
    coinbase = next(x for x in r3.exchanges if x.entity == "Coinbase")
    check("clean branch keeps clean-path bonus", "no mixer or bridge on path" in coinbase.confidence_breakdown, True)

    j = tracer.to_json(r3)
    check("json exposes risk_flags", len(j["risk_flags"]), 1)
    check("risk_flags carry severity", j["risk_flags"][0]["severity"], "medium")

    print("\n--- inferred bridge crossings are scored by their own strength ---")
    from types import SimpleNamespace as NS

    def attr(handoffs, hops=4):
        return NS(method="known_label", hop_distance=hops, path_risk_types={"bridge"},
                  handoff_scores=handoffs)

    weak = scoring.compute_confidence(attr([62]))
    strong = scoring.compute_confidence(attr([85]))
    # Worked example: label match (+50), 4 hops (+9), crossing at 62 -> -10 = 49;
    # at 85 -> -4 = 55. Neither exceeds its handoff score, so no cap applies.
    check("a 62 handoff, label match, 4 hops", weak.score, 49)
    check("an 85 handoff, same route", strong.score, 55)
    check("so the two are not scored alike", weak.score < strong.score, True)
    check("an inferred route never earns the clean-path bonus",
          any("no mixer or bridge" in c.label for c in strong.components), False)
    check("and is not also charged the flat bridge penalty",
          any(c.label.startswith("bridge on path") for c in strong.components), False)
    capped = scoring.compute_confidence(attr([62], hops=1))
    check("a strong route after a weak crossing is held at the handoff score", capped.score, 62)
    check("the cap is recorded", capped.handoff_cap, 62)
    check("and the breakdown says so", "held at 62" in capped.breakdown, True)
    check("two crossings are held at the weaker one",
          scoring.compute_confidence(attr([85, 62], hops=1)).score, 62)
    observed = scoring.compute_confidence(
        NS(method="known_label", hop_distance=4, path_risk_types=set(), handoff_scores=[])
    )
    check("an observed same-chain route is unchanged", observed.score, 74)
    check("and is never handoff-capped", observed.handoff_cap, None)

    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail

def test_suite():
    """
    The pytest entry point. Each suite is a script of named checks that prints
    PASS/FAIL per check and returns its failure count; pytest runs the whole
    script once and fails if any check failed. Run it directly for the per-check
    listing:  python -m tests.test_scoring
    """
    assert asyncio.run(main()) == 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
