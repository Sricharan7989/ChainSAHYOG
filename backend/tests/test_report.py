"""
The PDF must not blur an observed transfer and an inferred chain crossing.

A report that says "Funds reached Binance" reads the same whether the whole route
was observed on-chain or whether a leg of it was carried across a bridge on the
strength of an amount-and-time match. Those two carry very different weight in front
of a court, so the difference has to be visible in the document itself - not just in
the JSON.

These tests read the generated PDF back as text and assert on what a reader would
actually see. Extracting the text rather than inspecting the payload is deliberate:
the payload already carries the bridge section (test_cross_chain checks that), so
testing it again here would prove nothing. What can break is the report quietly
dropping it, or rendering a crossing as an ordinary hop.

Run from backend/:  python -m tests.test_report
"""
import asyncio
import sys
import tempfile
from pathlib import Path

import app  # noqa: E402,F401
from core import tracer  # noqa: E402
from services import report  # noqa: E402
from tests import test_cross_chain as cc  # noqa: E402

fail = 0


def check(name, got, want):
    global fail
    if got != want:
        fail += 1
    print(f"{'PASS' if got == want else 'FAIL'}  {name}" + ("" if got == want else f": got {got!r}, want {want!r}"))


def pdf_text(payload) -> str:
    """
    Render the report and read it back as a reader would.

    Whitespace is collapsed to single spaces. PDF extraction breaks lines wherever
    the text happens to fit the column, so a phrase like "fee tolerance" can come
    back as "fee\ntolerance" - which is a fact about the text layout, not about the
    report. Comparing against normalised text keeps these assertions about the
    content rather than about where reportlab happened to wrap.
    """
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - only in a bare environment
        print("SKIP  pypdf not installed; cannot read the PDF back")
        return ""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "report.pdf"
        path.write_bytes(report.build_report(payload))
        raw = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return " ".join(raw.split())


def matched_payload():
    books = {
        cc.ETH: {
            cc.SUSPECT: [cc.tx(cc.SUSPECT, cc.BRIDGE, 10.0, "0xdeposit", ts=1700000000)]
        }
    }
    books.update(
        cc.arb_book([cc.tx(cc.L2_GATEWAY, cc.SUSPECT, 9.98, "0xcredit", ts=1700000060)])
    )
    result, _ = cc.traced(books)
    return tracer.to_json(result)


def single_chain_payload():
    books = {
        cc.ETH: {
            cc.SUSPECT: [
                cc.tx(cc.SUSPECT, "0x" + "f" * 40, 10.0, "0xsingle", ts=1700000000)
            ]
        }
    }
    result, _ = cc.traced(books)
    return tracer.to_json(result)


def main():
    text = pdf_text(matched_payload())
    if not text:
        return 0

    print("--- the crossing is stated as an inference, not as an observation ---")
    check("a cross-chain section exists", "Cross-chain movement" in text, True)
    check("it says the crossing is inferred", "not directly observable" in text, True)
    check("it says the score is kept separate", "never merged into" in text, True)
    check("it names both chains examined",
          "ethereum, arbitrum" in text, True)

    print("\n--- the evidence is shown, so the decision can be challenged ---")
    check("the bridge is named", "Arbitrum Bridge" in text, True)
    check("the score is printed", "85/100" in text, True)
    check("the recipient-address check is named",
          "same recipient address" in text, True)
    check("the fee check is named", "fee tolerance" in text, True)
    check("the time lag is given", "60s after the deposit" in text, True)
    check("the payout tx is citable", "0xcredit" in text, True)
    check("the tainted share is quantified",
          "attributed to the suspect" in text, True)

    print("\n--- a chain-qualified node id never reaches the reader ---")
    # "arbitrum:0xaaa..." is internal addressing. An investigator needs the bare
    # address to paste into an explorer; the chain is stated separately.
    check("no prefixed node id is printed", "arbitrum:0x" in text, False)

    print("\n--- the path marks the crossing as a crossing ---")
    check("the crossing step is labelled", "Crossed to" in text, True)
    check("it names the destination chain", "Crossed to arbitrum" in text, True)

    print("\n--- a refused crossing is reported, not hidden ---")
    books = {
        cc.ETH: {
            cc.SUSPECT: [cc.tx(cc.SUSPECT, cc.BRIDGE, 10.0, "0xdeposit", ts=1700000000)]
        }
    }
    books.update(
        cc.arb_book([
            cc.tx(cc.L2_GATEWAY, cc.SUSPECT, 9.98, "0xcreditA", ts=1700000060),
            cc.tx(cc.L2_GATEWAY, cc.SUSPECT, 9.98, "0xcreditB", ts=1700000120),
        ])
    )
    ambiguous, _ = cc.traced(books)
    amb_text = pdf_text(tracer.to_json(ambiguous))
    check("an ambiguous crossing still appears", "Cross-chain movement" in amb_text, True)
    check("it is labelled as not followed", "not followed" in amb_text, True)
    check("and the candidates are listed", "Candidates considered" in amb_text, True)
    check("both candidates are shown",
          "0xcreditA" in amb_text and "0xcreditB" in amb_text, True)
    check("it does not claim a confidence for an ambiguous match",
          "matched None/100" in amb_text, False)

    print("\n--- a trace with no bridge is unchanged ---")
    plain = pdf_text(single_chain_payload())
    check("no cross-chain section is invented",
          "Cross-chain movement" in plain, False)
    check("and the ordinary report still renders", len(plain) > 400, True)

    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail


if __name__ == "__main__":
    sys.exit(main())