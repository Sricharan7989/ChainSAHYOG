"""
The PDF must describe the trace that was on screen.

/report re-ran the whole trace live whenever the request was not in auto mode,
so a report requested straight after a live trace took minutes and could print
figures that differ from what the investigator had just read. These checks make
the tracer explode if it is called at all, then ask for the report in every mode:
the only acceptable source is the in-memory result of the same trace.

Run from backend/:  python -m tests.test_routes
"""
import json
import sys

import app as app_pkg  # noqa: E402,F401
from fastapi.testclient import TestClient  # noqa: E402

from app import config, routes  # noqa: E402
from core import tracer  # noqa: E402

fail = 0
ADDR = "0x098b716b8aaf21512996dc57eb0615e2383e2f96"


def check(name, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got!r}" + ("" if ok else f", want {want!r}"))


def main():
    payload = json.loads((config.DATA_DIR / "cache" / f"{ADDR}.json").read_text(encoding="utf-8"))
    payload["source"] = "live"
    payload["params"]["max_depth"] = 3
    payload["params"]["dust_threshold_eth"] = 0.01

    async def must_not_run(*a, **k):
        raise AssertionError("the tracer was called: the report re-walked the chain")

    real_trace = tracer.trace
    real_has_key = config.has_etherscan_key
    tracer.trace = must_not_run
    config.has_etherscan_key = lambda: True
    # Keyed by (chain, address, as-of height); None = the default, head-pinned trace.
    routes._RECENT[("ethereum", ADDR, None)] = payload
    client = TestClient(app_pkg.create_app(), raise_server_exceptions=False)
    try:
        print("--- the report reuses the on-screen trace in every mode ---")
        for mode in ("live", "auto", "cache"):
            r = client.get("/report", params={"address": ADDR, "max_depth": 3,
                                              "dust_threshold": 0.01, "mode": mode})
            check(f"mode={mode}: served without re-tracing", r.status_code, 200)
            check(f"mode={mode}: it is a PDF", r.headers.get("content-type"), "application/pdf")

        print("\n--- a different depth is a different trace, and is NOT served from memory ---")
        r = client.get("/report", params={"address": ADDR, "max_depth": 4,
                                          "dust_threshold": 0.01, "mode": "live"})
        check("depth 4 does not reuse the depth-3 result", r.status_code, 500)
        r = client.get("/report", params={"address": ADDR, "max_depth": 3,
                                          "dust_threshold": 0.5, "mode": "live"})
        check("a different dust threshold does not reuse it either", r.status_code, 500)
    finally:
        tracer.trace = real_trace
        config.has_etherscan_key = real_has_key
        routes._RECENT.pop(("ethereum", ADDR), None)

    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail

def test_suite():
    """
    The pytest entry point. Each suite is a script of named checks that prints
    PASS/FAIL per check and returns its failure count; pytest runs the whole
    script once and fails if any check failed. Run it directly for the per-check
    listing:  python -m tests.test_routes
    """
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
