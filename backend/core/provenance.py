"""
Where a label comes from, and how strongly that source supports it.

WHY THIS EXISTS. "Funds reached Binance" rests entirely on a label saying an
address is Binance's. A court will ask who said so. "Binance published this
address itself and signed a message proving control" and "a block explorer
labelled it, relayed by a third-party pack" are both true kinds of answer, and
they are not worth the same. So every label row carries:

    citation        - the actual provenance CHAIN, in words: who published the
                      fact, and through whom we received it. Never a tidier
                      origin than the real one, never "public labels", never an
                      internal file name.
    evidence_tier   - one of TIERS below, strongest first.
    redistributable - whether the source lets us ship the row in the
                      committed data/labels.json. False only for something we
                      genuinely may not redistribute (e.g. a scrape we made
                      ourselves); those rows live in the gitignored
                      data/labels.local.json, merged by the loader.
    provenance      - the structured list behind the citation, one entry per
                      independent source that carries this address.
"""

# Strongest first. The order is the point: the annexure and the panel show the
# tier so a reader can see at a glance what a name rests on.
TIERS: dict[str, str] = {
    "self_published_signed": (
        "self-published and signed: the entity published this address itself, with a "
        "signature proving it controls the address"
    ),
    "self_published": (
        "self-published: the entity published this address itself (its own transparency, "
        "reserve or documentation page)"
    ),
    "court_record": (
        "court record: an indictment, forfeiture complaint or regulator action names the "
        "address as this entity's"
    ),
    "government_list": "government list: a published government list (OFAC SDN) names the address",
    "third_party_pack": (
        "third-party pack: a published attribution dataset (GraphSense TagPacks) names the "
        "address; the pack states its own upstream source"
    ),
    "inferred": (
        "inferred: this tool inferred the attribution (same address on another chain, or a "
        "behavioural pattern); no published source names it on this chain"
    ),
}

TIER_SHORT: dict[str, str] = {
    "self_published_signed": "Self-published, signed",
    "self_published": "Self-published",
    "court_record": "Court record",
    "government_list": "Government list",
    "third_party_pack": "Third-party pack",
    "inferred": "Inferred",
}


def tier_rank(tier: str | None) -> int:
    """0 for the strongest tier; unknown tiers sort last."""
    order = list(TIERS)
    return order.index(tier) if tier in order else len(order)


def describe(meta: dict | None) -> dict:
    """The provenance fields a finding carries to the panel, annexure and PDF."""
    meta = meta or {}
    tier = meta.get("evidence_tier")
    return {
        "citation": meta.get("citation"),
        "evidence_tier": tier,
        "evidence_tier_label": TIER_SHORT.get(tier),
        "evidence_tier_text": TIERS.get(tier),
    }
