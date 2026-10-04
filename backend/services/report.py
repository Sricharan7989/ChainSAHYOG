"""
PDF report generation — the document an investigator actually files.

WHY A PDF AND NOT A SCREENSHOT
------------------------------
The finding has to leave this tool and travel into a process built on paper:
attached to a SAHYOG request, handed to a supervisor, disclosed to a defence
lawyer. That means it must be self-contained and self-justifying. Anyone who
opens it months later, with no access to this machine, has to be able to see
what was claimed, what it rests on, and how certain it was.

So the report carries the reasoning, not just the conclusion: the full
confidence arithmetic, the hop-by-hop path with transaction hashes anyone can
verify on a block explorer, and an explicit statement of the method's limits.
A report that printed "Binance, 88%" and nothing else would be unusable as
evidence and misleading as intelligence.
"""

from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Muted, printable palette. A report that comes out of a station printer in
# greyscale still has to be readable, so meaning never rests on colour alone.
INK = colors.HexColor("#0f172a")
SOFT = colors.HexColor("#475569")
FAINT = colors.HexColor("#94a3b8")
LINE = colors.HexColor("#cbd5e1")
GOOD = colors.HexColor("#15803d")
WARN = colors.HexColor("#c2410c")
DANGER = colors.HexColor("#b91c1c")
BAND = colors.HexColor("#f1f5f9")


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontSize=17, leading=21,
            textColor=INK, alignment=TA_LEFT, spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"], fontSize=9, textColor=FAINT, spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontSize=10.5, leading=13, textColor=INK,
            spaceBefore=13, spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontSize=9.5, leading=13, textColor=INK,
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"], fontSize=8, leading=11, textColor=SOFT,
        ),
        "mono": ParagraphStyle(
            "mono", parent=base["Normal"], fontSize=7.5, leading=10,
            fontName="Courier", textColor=INK,
        ),
        "headline": ParagraphStyle(
            "headline", parent=base["Normal"], fontSize=14, leading=18,
            textColor=INK, spaceBefore=3, spaceAfter=3,
        ),
        "disclaimer": ParagraphStyle(
            "disclaimer", parent=base["Normal"], fontSize=7.5, leading=10.5, textColor=SOFT,
        ),
    }


def _hex(colour) -> str:
    """'#rrggbb' for inline <font color=...> markup - reportlab rejects it bare."""
    return "#" + colour.hexval()[2:]


def _fmt_eth(value) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "-"
    if v >= 1000:
        return f"{v:,.0f} ETH"
    if v >= 1:
        return f"{v:,.2f} ETH"
    return f"{v:.4f} ETH"


def _fmt_assets(totals, fallback=None) -> str:
    """
    Per-asset totals as one line: "12.5 ETH + 40,000 USDT".

    Falls back to the legacy scalar for payloads recorded before tokens existed.
    Assets are never summed: there is no price feed here, so a combined number
    would be invented.
    """
    if not isinstance(totals, dict) or not totals:
        return _fmt_eth(fallback) if fallback is not None else "—"
    parts = []
    for asset, amount in sorted(totals.items(), key=lambda kv: -kv[1]):
        if amount >= 1000:
            parts.append(f"{amount:,.0f} {asset}")
        elif amount >= 1:
            parts.append(f"{amount:,.2f} {asset}")
        else:
            parts.append(f"{amount:.4f} {asset}")
    return " + ".join(parts)


def _short(address: str) -> str:
    return f"{address[:10]}…{address[-8:]}" if address and len(address) > 20 else (address or "")


def _bare(node_id: str) -> str:
    """
    Strip the chain prefix from a graph node id.

    Once a trace crosses a chain, node ids look like "arbitrum:0xabc...". That
    prefix is internal addressing; an investigator needs the plain address to paste
    into an explorer, with the chain stated separately. Ids without a prefix are
    returned unchanged, so single-chain traces read exactly as they did before.
    """
    node_id = (node_id or "").strip()
    return node_id.split(":", 1)[1] if ":" in node_id else node_id


def _kv_table(rows: list[tuple[str, str]], styles: dict) -> Table:
    data = [[Paragraph(k, styles["small"]), Paragraph(v, styles["body"])] for k, v in rows]
    table = Table(data, colWidths=[38 * mm, 128 * mm])
    table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("LINEBELOW", (0, 0), (-1, -2), 0.25, LINE),
        ])
    )
    return table


def _rule() -> HRFlowable:
    return HRFlowable(width="100%", thickness=0.6, color=LINE, spaceBefore=6, spaceAfter=6)


def _path_section(payload: dict, styles: dict) -> list:
    """The hop-by-hop trail, with a verifiable transaction hash on every step."""
    summary = payload.get("summary", {})
    target = summary.get("address")

    attribution = next(
        (a for a in payload.get("attributions", []) if a.get("address") == target), None
    )
    path = (attribution or {}).get("path") or []
    if not path:
        return [Paragraph("No route could be reconstructed.", styles["body"])]

    nodes = {n["id"]: n for n in payload.get("nodes", [])}
    edges = {(e["source"], e["target"]): e for e in payload.get("edges", [])}
    primary = (payload.get("cross_chain") or {}).get("chains_traced") or []
    primary = primary[0] if primary else None

    taint_computed = bool((payload.get("accounting") or {}).get("rule"))
    head = ["Hop", "Role", "Address", "Value moved"]
    if taint_computed:
        head.append("Of which suspect's")
    head.append("Transaction")
    rows = [[Paragraph(f"<b>{h}</b>", styles["small"]) for h in head]]

    for index, address in enumerate(path):
        node = nodes.get(address, {})
        if index == 0:
            role = "Suspect wallet"
        elif node.get("entity_type") == "suspected_exchange":
            role = "Possible collection point"
        elif node.get("is_vasp"):
            role = node.get("label") or "Exchange"
        elif node.get("is_mixer"):
            role = f"{node.get('label')} (mixer)"
        elif node.get("is_bridge"):
            role = f"{node.get('label')} (bridge)"
        elif node.get("entity_type") == "sanctioned":
            role = f"{node.get('label')} (OFAC sanctioned)"
        else:
            role = "Intermediate wallet"

        edge = edges.get((path[index - 1], address)) if index > 0 else None
        assets = (edge.get("assets") or []) if edge else []

        # A chain crossing is not another transfer. Name the bridge it went through
        # and mark the address with its chain, so a reader who only knows Ethereum
        # can tell that the route leaves the chain they were looking at.
        if edge and edge.get("edge_type") == "cross_chain":
            handoff = (edge.get("handoff") or {})
            crossed_to = edge.get("to_chain") or node.get("chain") or "another chain"
            role = (
                f"Crossed to {crossed_to} via "
                f"{handoff.get('entity') or node.get('label') or 'a bridge'}"
            )
            score = handoff.get("confidence_score")
            if score is not None:
                role += f" (matched, {score}%)"

        # Chain-qualified node ids are an internal addressing scheme, not something
        # to paste into an explorer. Print the bare address and carry the chain in
        # the Role column instead.
        shown = node.get("address") or _bare(address)
        chain = node.get("chain")
        if chain and primary and chain != primary:
            shown = f"{shown}  [{chain}]"
        row = [
            Paragraph(str(index) if index else "—", styles["small"]),
            Paragraph(role, styles["body"]),
            Paragraph(shown, styles["mono"]),
            Paragraph(
                _fmt_assets({a["asset"]: a["value"] for a in assets},
                            edge.get("value_eth")) if edge else "—",
                styles["small"],
            ),
        ]
        if taint_computed:
            tainted = {
                a["asset"]: a.get("tainted_value", 0.0)
                for a in assets
                if a.get("tainted_value", 0.0) > 0
            }
            row.append(Paragraph(
                _fmt_assets(tainted) if tainted
                else ("—" if not edge else '<font color="#b91c1c">none</font>'),
                styles["small"],
            ))
        row.append(Paragraph(_short(edge["tx_hash"]) if edge else "—", styles["mono"]))
        rows.append(row)

    widths = (
        [10 * mm, 30 * mm, 50 * mm, 24 * mm, 24 * mm, 28 * mm]
        if taint_computed
        else [10 * mm, 34 * mm, 62 * mm, 26 * mm, 34 * mm]
    )
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, 0), BAND),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, LINE),
            ("LINEBELOW", (0, 1), (-1, -2), 0.25, LINE),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    return [table]


def _confidence_section(summary: dict, styles: dict) -> list:
    """
    The score AND the arithmetic behind it.

    Printing the number alone would make it unchallengeable, which is precisely
    what a figure used to justify a legal request must never be.
    """
    components = summary.get("confidence_components") or []
    score = summary.get("confidence_score", 0)

    if not components:
        return [Paragraph(f"Confidence: {score}%", styles["body"])]

    rows = [[Paragraph("<b>Factor</b>", styles["small"]),
             Paragraph("<b>Points</b>", styles["small"])]]
    for component in components:
        points = component.get("points", 0)
        colour = DANGER if points < 0 else GOOD
        rows.append([
            Paragraph(str(component.get("label", "")), styles["body"]),
            Paragraph(
                f'<font color="{_hex(colour)}">{points:+d}</font>', styles["body"]
            ),
        ])
    rows.append([
        Paragraph("<b>Confidence score</b>", styles["body"]),
        Paragraph(f"<b>{score} / 100</b>", styles["body"]),
    ])

    table = Table(rows, colWidths=[130 * mm, 36 * mm])
    table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, 0), BAND),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, LINE),
            ("LINEABOVE", (0, -1), (-1, -1), 0.6, LINE),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    return [table, Spacer(1, 4),
            Paragraph(
                "Scores are capped at 95. This tool never asserts certainty.",
                styles["small"],
            )]


def _cross_chain_section(payload: dict, styles: dict) -> list:
    """
    What the trace did about bridges, and how sure it is.

    This section exists to keep one specific failure out of the report: a reader
    seeing "Funds reached Binance" must be able to tell whether the whole route was
    observed on-chain, or whether part of it was carried across a chain boundary on
    the strength of an amount-and-time match. The two carry different weight in
    front of a court, and a report that blurs them is worse than no report.

    Every handoff is listed, including the ones we declined. A crossing that was
    ambiguous or unmatched is where the trail goes cold, and that is exactly the
    kind of fact an investigator needs before deciding to widen the search.
    """
    cross = payload.get("cross_chain") or {}
    handoffs = cross.get("handoffs") or []
    if not handoffs:
        return []

    out = [Paragraph("Cross-chain movement", styles["h2"])]
    chains = cross.get("chains_traced") or []
    if len(chains) > 1:
        out.append(Paragraph(
            "This route leaves the chain it started on. Chains examined: "
            + ", ".join(chains) + ".",
            styles["small"],
        ))
    out.append(Paragraph(
        "A chain crossing is not directly observable. The deposit is on record on "
        "one chain; the arrival of the same value on another is matched by amount, "
        "timing, recipient address and payout contract. Each crossing carries its "
        "own confidence score, reported separately and never merged into the "
        "on-chain confidence above.",
        styles["small"],
    ))
    out.append(Spacer(1, 6))

    # Labels decide whether a chain could yield an exchange finding at all. Say so
    # before the findings, not in a footnote.
    coverage = cross.get("label_coverage") or {}
    unlabelled = [
        slug for slug, info in coverage.items()
        if isinstance(info, dict) and not info.get("identification_possible")
    ]
    if unlabelled:
        out.append(Paragraph(
            "<b>Coverage limit:</b> we hold no entity labels for "
            + ", ".join(unlabelled)
            + ". Exchanges there could not be recognised by name, so a finding on "
            "this route may understate where the money went.",
            styles["small"],
        ))
        out.append(Spacer(1, 6))

    labels = {
        "matched": "Followed",
        "ambiguous": "Ambiguous — not followed",
        "no_match": "No match — not followed",
        "hop_cap_reached": "Stopped at the crossing limit",
        "unsupported": "Recognised bridge, deliberately not followed",
        "not_registered": "Bridge not in our registry",
        "destination_unavailable": "Destination chain unreadable",
    }
    for handoff in handoffs:
        state = handoff.get("status", "")
        deposit = handoff.get("deposit") or {}
        bridge = handoff.get("bridge") or {}
        entity = (
            deposit.get("entity")
            or bridge.get("entity")
            or "Bridge"
        )
        from_chain = deposit.get("chain") or ""
        to_chain = deposit.get("to_chain") or ""
        out.append(Paragraph(
            f'<b>{entity}</b> '
            f'({from_chain} → {to_chain or "?"}) — '
            f'{labels.get(state, state)}',
            styles["body"],
        ))
        if handoff.get("reason"):
            out.append(Paragraph(handoff["reason"], styles["small"]))

        chosen = handoff.get("chosen")
        if chosen:
            # Which checks the match passed on. Named explicitly, because "85/100"
            # on its own is a number with nothing behind it.
            evidence = handoff.get("evidence") or {}
            checks = [
                name
                for name, ok in (
                    ("same recipient address", evidence.get("destination_address_matched")),
                    ("paid by a known bridge payout contract",
                     evidence.get("credit_from_known_bridge_contract")),
                    ("amount within the fee tolerance", True),
                    (f"arrived {chosen.get('lag_sec')}s after the deposit", True),
                ) if ok
            ]
            tainted = handoff.get("tainted_value") or chosen.get("tainted_value") or 0.0
            out.append(Paragraph(
                f'Arrived as {_fmt_assets({chosen.get("asset", ""): chosen.get("value", 0.0)})}; '
                f'matched {handoff.get("confidence_score") or chosen.get("score", "?")}/100 on '
                + ", ".join(checks) + ". "
                + (
                    "Of that, "
                    + _fmt_assets({chosen.get("asset", ""): tainted})
                    + " is attributed to the suspect."
                    if tainted > 0
                    else "None of it is attributed to the suspect."
                ),
                styles["small"],
            ))
            out.append(Paragraph(
                f'Payout transaction: {chosen.get("tx_hash", "")}',
                styles["mono"],
            ))

        # Show every candidate for a refused crossing, so the decision can be
        # challenged on the evidence rather than taken on trust.
        others = [
            c for c in (handoff.get("candidates") or [])
            if not chosen or c.get("tx_hash") != chosen.get("tx_hash")
        ]
        if others and not handoff.get("matched"):
            out.append(Spacer(1, 3))
            out.append(Paragraph("Candidates considered:", styles["small"]))
            for candidate in others:
                out.append(Paragraph(
                    f'· {_fmt_assets({candidate.get("asset", ""): candidate.get("value", 0.0)})} '
                    f'from {_short(candidate.get("from_addr", ""))}, '
                    f'{candidate.get("lag_sec", "?")}s later, '
                    f'score {candidate.get("score", "?")}/100, '
                    f'tx {_short(candidate.get("tx_hash", ""))}',
                    styles["mono"],
                ))
        out.append(Spacer(1, 8))

    return out


def _risk_section(payload: dict, styles: dict) -> list:
    # Absent and empty are different statements. A payload with no `risk_flags`
    # key was never screened, and saying "none were identified" over it would
    # certify a trail nobody examined. An empty list means the screen ran, but
    # it can only recognise addresses in our label set - so it is reported as
    # "none of our labelled risk entities", never as a clean trail.
    if "risk_flags" not in payload:
        return [Paragraph(
            "Risk-label screening was not performed for this result: the recorded "
            "trace predates it. This report makes no statement either way about "
            "mixers, bridges, scam or sanctioned addresses on the route.",
            styles["body"],
        )]
    flags = payload.get("risk_flags") or []
    if not flags:
        return [Paragraph(
            "No address in our label set for mixers, bridges, scams or sanctions "
            "appeared in this trace. Only labelled addresses can be flagged; an "
            "unlabelled mixer or sanctioned wallet would not appear here.",
            styles["body"],
        )]

    rows = [[Paragraph(f"<b>{h}</b>", styles["small"])
             for h in ["Severity", "Entity", "On path", "Hop", "Value received"]]]
    for flag in flags:
        severity = flag.get("severity", "")
        colour = DANGER if severity == "critical" else WARN if severity == "high" else SOFT
        rows.append([
            Paragraph(
                f'<font color="{_hex(colour)}"><b>{severity.upper()}</b></font>',
                styles["small"],
            ),
            Paragraph(str(flag.get("entity", "")), styles["body"]),
            Paragraph("Yes" if flag.get("on_primary_path") else "No", styles["small"]),
            Paragraph(str(flag.get("hop_distance", "")), styles["small"]),
            Paragraph(_fmt_assets(flag.get("value_received"),
                                  flag.get("value_received_eth")), styles["small"]),
        ])

    table = Table(rows, colWidths=[20 * mm, 76 * mm, 18 * mm, 12 * mm, 40 * mm], repeatRows=1)
    table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, 0), BAND),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, LINE),
            ("LINEBELOW", (0, 1), (-1, -2), 0.25, LINE),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ])
    )

    notes = [Spacer(1, 5)]
    for flag in flags:
        if flag.get("on_primary_path"):
            notes.append(Paragraph(f"• {flag.get('note', '')}", styles["small"]))
    return [table, *notes]


def _typology_section(payload: dict, styles: dict) -> list:
    """
    Matched laundering typologies, each with its explanation and its numbers.

    WHY THE FULL EXPLANATION IS PRINTED, not a code. The point of this section is
    that an investigator can lift a paragraph into a case file and a magistrate can
    read it without knowing what "peel chain" means. A table of typology names and
    scores would be useless for that, and worse, it would read as a verdict.

    Every entry therefore carries the measurements that triggered it and the
    thresholds it was judged against, so the reasoning is auditable and a reader
    who thinks our bar is too low can say exactly where.
    """
    found = payload.get("typologies") or []
    summary = payload.get("typology_summary") or {}
    # A recording made before the detectors existed has neither key. Reporting
    # "no typology met its threshold" over it would state a result for an
    # analysis that never ran - the same false negative the panel used to show.
    if not found and "typology_summary" not in payload and "typologies" not in payload:
        return [
            Paragraph("Laundering typologies", styles["h2"]),
            Paragraph(
                "No typology analysis was performed for this result: the recorded "
                "trace predates the laundering detectors. This is not a finding "
                "that the movement was ordinary.",
                styles["body"],
            ),
        ]
    if not found:
        return [
            Paragraph("Laundering typologies", styles["h2"]),
            Paragraph(
                "No laundering typology met its threshold on this trace. The rules "
                "are deliberately strict - a wrongly asserted pattern in a police "
                "report is more damaging than a missed one - so this is not a "
                "finding that the movement was ordinary, only that no pattern was "
                "unambiguous enough to assert.",
                styles["body"],
            ),
        ]

    story = [Paragraph("Laundering typologies", styles["h2"])]
    story.append(Paragraph(
        f"<b>{summary.get('count', len(found))} pattern(s) matched.</b> "
        f"{summary.get('caveat', '')}",
        styles["small"],
    ))
    if summary.get("suppressed"):
        story.append(Paragraph(
            f"The {summary['count']} strongest are shown; "
            f"{summary['suppressed']} further match(es) of the same kinds are not "
            f"listed individually.",
            styles["small"],
        ))
    if summary.get("scope"):
        story.append(Paragraph(summary["scope"], styles["small"]))
    story.append(Spacer(1, 4))

    for entry in found:
        strength = entry.get("strength", 0)
        colour = DANGER if strength >= 80 else WARN if strength >= 60 else SOFT
        heading = (
            f'<font color="{_hex(colour)}"><b>{entry.get("name", "")}</b></font> '
            f'· strength {strength}/100'
        )
        if entry.get("corroborating_only"):
            heading += ' · <i>corroborating signal only, not a finding on its own</i>'
        if entry.get("asset"):
            heading += f' · {entry["asset"]}'

        measurements = ", ".join(
            f"{k.replace('_', ' ')} {v}" for k, v in (entry.get("measurements") or {}).items()
        )
        thresholds = ", ".join(
            f"{k.replace('_', ' ')} {v}" for k, v in (entry.get("thresholds") or {}).items()
        )

        block = [
            Paragraph(heading, styles["body"]),
            Paragraph(entry.get("explanation", ""), styles["small"]),
            Paragraph(
                f'<font size="7">Measured: {measurements}. '
                f'Thresholds applied: {thresholds}. '
                f'Wallets involved: {len(entry.get("wallets") or [])}.</font>',
                styles["small"],
            ),
            Spacer(1, 6),
        ]
        story.append(KeepTogether(block))

    story.append(Paragraph(summary.get("thresholds_note", ""), styles["small"]))
    return story


def disclaimer(
    chain_name: str = "Ethereum", native: str = "ETH", accounting: dict | None = None
) -> str:
    """
    The basis-and-limitations paragraph, named for the chain actually traced.

    A function rather than a constant because this paragraph makes factual claims
    about WHICH network, WHICH assets and WHICH method were examined. A Polygon
    report stating "public Ethereum transaction records" would be wrong, in the one
    part of the document whose whole purpose is to be accurate about scope.

    The taint sentence is conditional for the same reason. It used to say flatly
    that no value-level taint tracking is performed. That was true; it is now
    wrong whenever the FIFO pass ran, and a disclaimer that understates the method
    is as much a defect as one that overstates it. Where the pass did run, the
    paragraph names the accounting rule instead - which is what makes the figures
    challengeable, and therefore usable in evidence.
    """
    ran = bool((accounting or {}).get("rule"))
    if ran:
        taint_sentence = (
            "Amounts attributed to the suspect are computed by FIFO accounting: "
            "every observed transfer is replayed in chronological order and each "
            "outgoing payment is drawn from the front of the wallet's queue of "
            "received funds. Coins are fungible, so no accounting rule is correct "
            "in a physical sense; a different rule - last-in-first-out, or "
            "pro-rata pooling - applied to the same transactions would attribute "
            "a different amount. Value a wallet sent that its observed inflows "
            "cannot account for is treated as untainted, which understates the "
            "attributed amount rather than inflating it. The gross figures and the "
            "attributed figures are both shown and are clearly distinguished."
        )
    else:
        taint_sentence = (
            "It does NOT perform value-level taint tracking: each wallet's large "
            "outgoing transfers are followed regardless of where that value came "
            "from, so a connected path is not proof that these specific funds "
            "arrived."
        )
    return (
        f"<b>Basis and limitations.</b> This report is derived entirely from "
        f"public {chain_name} transaction records. No cryptography was broken, no "
        f"private data was accessed, and no individual was identified by this "
        f"tool. It establishes that a chain of transfers connects the suspect "
        f"address to a wallet attributed to the named entity. {taint_sentence} "
        f"It does NOT establish who controlled any intermediate wallet. "
        f"Attribution of the endpoint rests on the method stated above and carries "
        f"the confidence score shown, which is never certainty. Native {native} "
        f"transfers and allowlisted ERC-20 tokens are followed; internal contract "
        f"transfers are not, and attribution does not survive a conversion from "
        f"one asset to another, so the trail may continue beyond what is shown. "
        f"Identity can only be established by the named exchange, from its own "
        f"KYC records, in response to a lawful request."
    )


def build_report(payload: dict) -> bytes:
    """
    Render a completed trace into a PDF and return the raw bytes.

    Takes the same JSON dict the /trace endpoint serves, so the report can be
    generated from a live trace or a cached replay with no difference in output.
    """
    styles = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title="Cryptocurrency Attribution Report",
        author="VASP Attribution Engine",
    )

    summary = payload.get("summary", {})
    stats = payload.get("stats", {})
    params = payload.get("params", {})
    generated = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")

    story: list = []

    # --- Header ---------------------------------------------------------
    story.append(Paragraph("Cryptocurrency Attribution Report", styles["title"]))
    story.append(Paragraph(
        f"Wallet-to-VASP tracing on {params.get('chain_name') or 'Ethereum'} · "
        f"prepared for lawful request via SAHYOG / I4C",
        styles["subtitle"],
    ))
    story.append(_rule())

    source = payload.get("source", "live")
    source_text = "Live blockchain query"
    if source == "cache":
        recorded = payload.get("recorded_at", "unknown time")
        source_text = f"Recorded trace (captured {recorded})"

    chain_name = params.get("chain_name") or "Ethereum"
    chain_id = params.get("chain_id", 1)
    native = params.get("native_symbol") or "ETH"

    story.append(_kv_table([
        ("Suspect address", f'<font face="Courier" size="8">{payload.get("start_address", "")}</font>'),
        ("Network", f"{chain_name} (chain id {chain_id}), native token {native}"),
        ("Report generated", generated),
        ("Data source", f"{chain_name} via Etherscan V2 · {source_text}"),
        ("Trace depth", f'{params.get("max_depth", "?")} hops '
                        f'(dust threshold {params.get("dust_threshold_eth", "?")} {native})'),
        ("Wallets examined", f'{stats.get("nodes", 0)} wallets, {stats.get("edges", 0)} transfers'),
    ], styles))

    # --- Finding --------------------------------------------------------
    story.append(Paragraph("Finding", styles["h2"]))

    if summary.get("found"):
        hop_text = (
            f'{summary.get("hop_distance")} hop'
            f'{"" if summary.get("hop_distance") == 1 else "s"} from the suspect '
            f'address, at {summary.get("confidence_score")}% confidence.'
        )
        attributed = summary.get("tainted_value_display")
        if summary.get("taint_computed") and attributed:
            # Lead with the attributed value: it is the finding, and the hop count
            # was always the weaker half of the claim.
            story.append(Paragraph(
                f'<b>{attributed} of the suspect\'s funds reached '
                f'{summary.get("exchange")}</b>, {hop_text}',
                styles["headline"],
            ))
        elif summary.get("taint_computed"):
            story.append(Paragraph(
                f'<b>Transaction path connects to {summary.get("exchange")}</b>, '
                f'{hop_text} <font color="#b91c1c">No value attributable to the '
                f'suspect arrived under FIFO accounting.</font>',
                styles["headline"],
            ))
        else:
            story.append(Paragraph(
                f'<b>Transaction path connects to {summary.get("exchange")}</b>, '
                f'{hop_text}',
                styles["headline"],
            ))
        # Immediately under the claim, not down in the disclaimer: the point is
        # that a reader cannot take the headline without this qualification.
        if summary.get("caveat"):
            story.append(Paragraph(f'<b>{summary["caveat"]}</b>', styles["small"]))
        story.append(Spacer(1, 3))

        rows = [
            ("Exchange", str(summary.get("exchange", ""))),
            ("Exchange wallet",
             f'<font face="Courier" size="8">{summary.get("address", "")}</font>'),
        ]
        if summary.get("taint_computed"):
            fraction = summary.get("tainted_inflow_fraction") or {}
            share = ", ".join(
                f"{value * 100:.2f}% of the {asset} it received"
                for asset, value in sorted(fraction.items())
            )
            rows.append((
                "Attributable to the suspect",
                f'<b>{attributed or "none"}</b>'
                + (f' <font size="7">({share}, on observed transfers)</font>'
                   if share else ""),
            ))
            rows.append((
                "Accounting rule",
                'FIFO - funds leave a wallet in the order they arrived. '
                '<font size="7">A different rule would attribute a different '
                'amount; see Basis and limitations.</font>',
            ))
            if not summary.get("path_fully_accounted", True):
                rows.append((
                    "Uncertainty on this route",
                    f'{summary.get("path_assumed_pre_existing_display")} of the '
                    f'value moved on this route could not be accounted for from '
                    f'observed inflows and was treated as NOT the suspect\'s. '
                    f'<font size="7">The attributed figure above may therefore be '
                    f'understated.</font>',
                ))
            else:
                rows.append((
                    "Uncertainty on this route",
                    "None: every transfer on this route was accounted for from "
                    "observed inflows.",
                ))
            if summary.get("inflow_note"):
                rows.append(("Note on the share figure", summary["inflow_note"]))
        rows.append((
            "Gross value on traced edges",
            f'{_fmt_assets(summary.get("value_received"), summary.get("value_received_eth"))}'
            f' <font size="7">(everything that entered this wallet along traced'
            f' transfers, whatever its origin)</font>',
        ))
        rows.append((
            "Identification method",
            "Direct match against known exchange wallets"
            if summary.get("method") == "known_label"
            else "Deposit-consolidation pattern (unconfirmed)",
        ))
        story.append(_kv_table(rows, styles))
    elif summary.get("lead"):
        story.append(Paragraph(
            f'<b>No named exchange within {params.get("max_depth")} hops.</b> '
            f'A transaction path connects to a possible collection point '
            f'{summary.get("hop_distance")} hops away at '
            f'{summary.get("confidence_score")}% confidence. '
            f'<font color="#b91c1c">This is an UNCONFIRMED lead, not an '
            f'identified exchange.</font>',
            styles["headline"],
        ))
        story.append(Spacer(1, 3))
        story.append(_kv_table([
            ("Address of interest",
             f'<font face="Courier" size="8">{summary.get("address", "")}</font>'),
            ("Value traced in", _fmt_assets(summary.get("value_received"),
                                            summary.get("value_received_eth"))),
            ("Caution", "A criminal re-pooling their own split funds produces the "
                        "same fan-in pattern as an exchange sweeping customer "
                        "deposits. Verify independently before acting."),
        ], styles))
    else:
        story.append(Paragraph(
            f'<b>No transaction path to a known exchange within '
            f'{params.get("max_depth")} hops of the suspect address.</b>',
            styles["headline"],
        ))

    # --- Confidence -----------------------------------------------------
    if summary.get("found") or summary.get("lead"):
        story.append(Paragraph("Confidence assessment", styles["h2"]))
        story.extend(_confidence_section(summary, styles))

    # --- Path -----------------------------------------------------------
    story.append(Paragraph("Traced path", styles["h2"]))
    story.extend(_path_section(payload, styles))

    # --- Risk flags -----------------------------------------------------
    story.append(Paragraph("Risk flags", styles["h2"]))
    story.extend(_risk_section(payload, styles))

    # --- Laundering typologies ------------------------------------------
    # A SECTION OF ITS OWN, deliberately not merged into risk flags above. A risk
    # flag says what a wallet IS, on the authority of a published label; a
    # typology says what the movement LOOKS LIKE, on the authority of our own
    # pattern rules. Printing them together would lend the inference the label's
    # credibility, which is exactly the confusion a defence lawyer should win.
    story.extend(_typology_section(payload, styles))

    # --- Entity clusters -------------------------------------------------
    clusters = payload.get("clusters") or []
    if clusters:
        story.append(Paragraph("Entity clusters", styles["h2"]))
        story.append(Paragraph(
            "Wallets grouped by the business behind them. A lawful request is "
            "served on the entity, citing every address below. Hop distance is "
            "the distance to the first member reached; clustering does not change "
            "it.",
            styles["small"],
        ))
        story.append(Spacer(1, 4))

        head = ("Entity", "Type", "Wallets", "Hop", "Received")
        rows = [[Paragraph(f"<b>{h}</b>", styles["small"]) for h in head]]
        for cluster in clusters:
            label = str(cluster.get("entity", ""))
            if not cluster.get("named", True):
                label += " <font size=\"7\">(unnamed - inferred)</font>"
            rows.append([
                Paragraph(label, styles["body"]),
                Paragraph(str(cluster.get("entity_type", "")), styles["small"]),
                Paragraph(str(cluster.get("member_count", 0)), styles["small"]),
                Paragraph(str(cluster.get("hop_distance", "")), styles["small"]),
                Paragraph(_fmt_assets(cluster.get("value_received"),
                                      cluster.get("value_received_eth")), styles["small"]),
            ])
        table = Table(rows, colWidths=[64 * mm, 30 * mm, 16 * mm, 12 * mm, 44 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, 0), BAND),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, LINE),
            ("LINEBELOW", (0, 1), (-1, -2), 0.25, LINE),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(table)

        # Member addresses, so the request can cite them and anyone can verify.
        for cluster in clusters:
            if cluster.get("member_count", 0) < 1:
                continue
            story.append(Spacer(1, 5))
            story.append(Paragraph(
                f'<b>{cluster.get("entity", "")}</b> — '
                f'{cluster.get("member_count", 0)} wallet(s), hop '
                f'{cluster.get("hop_distance", "")}',
                styles["small"],
            ))
            hops = cluster.get("member_hops") or {}
            for member in cluster.get("members", []):
                story.append(Paragraph(
                    f'hop {hops.get(member, "?")} &nbsp; {_bare(member)}',
                    styles["mono"],
                ))

    # --- Cross-chain movement --------------------------------------------
    story.extend(_cross_chain_section(payload, styles))

    # --- Why the trace stopped ------------------------------------------
    termination = summary.get("termination") or payload.get("termination") or {}
    if termination:
        story.append(Paragraph("Why the trace stopped", styles["h2"]))
        story.append(Paragraph(f'<b>{termination.get("label", "")}</b>', styles["body"]))
        if termination.get("detail"):
            story.append(Paragraph(termination["detail"], styles["small"]))

    # --- Untraced token activity ----------------------------------------
    token_note = payload.get("token_warnings") or {}
    if isinstance(token_note, dict) and token_note.get("skipped_transfers"):
        story.append(Paragraph("Tokens not followed", styles["h2"]))
        story.append(Paragraph(
            f"Transfers of {', '.join(token_note.get('followed_assets', []))} were "
            f"traced. {token_note['skipped_transfers']} transfer(s) of "
            f"{token_note.get('distinct_tokens', 0)} other token(s) were not: "
            f"{token_note.get('reason', '')}",
            styles["body"],
        ))
        # An impostor row must be labelled in the report itself. A bare skipped
        # "USDT" would read to the recipient as money this trace failed to
        # follow, when it is a token falsely using that name - refused because
        # its contract address is not the real one on this chain.
        if token_note.get("impersonation_note"):
            story.append(Paragraph(token_note["impersonation_note"], styles["small"]))
        rows = [[Paragraph(f"<b>{h}</b>", styles["small"]) for h in ("Token", "Transfers")]]
        for entry in token_note.get("top_skipped", []):
            asset = str(entry.get("asset", ""))
            if entry.get("impersonating"):
                asset += " (impostor - not the real contract)"
            rows.append([
                Paragraph(asset, styles["body"]),
                Paragraph(str(entry.get("transfers", "")), styles["small"]),
            ])
        table = Table(rows, colWidths=[120 * mm, 46 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, 0), BAND),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, LINE),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(table)

    # --- Recommended action ---------------------------------------------
    action = summary.get("recommended_action", "")
    if action:
        story.append(Paragraph("Recommended action", styles["h2"]))
        story.append(KeepTogether([
            Paragraph(action, styles["body"]),
        ]))

    # --- Disclaimer -----------------------------------------------------
    story.append(Spacer(1, 10))
    story.append(_rule())
    story.append(Paragraph(
        disclaimer(chain_name, native, payload.get("accounting")),
        styles["disclaimer"],
    ))

    def _footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(FAINT)
        canvas.drawString(
            22 * mm, 11 * mm,
            f"VASP Attribution Engine · {payload.get('start_address', '')[:18]}… · {generated}",
        )
        canvas.drawRightString(A4[0] - 22 * mm, 11 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def filename_for(address: str) -> str:
    """Stable, sortable filename an investigator can file without renaming."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return f"attribution-report-{address[:10]}-{stamp}.pdf"
