"""
Can a request actually be served on this VASP, and through which channel?

WHY THIS EXISTS. "Funds reached FTX" is a true finding and a useless
recommendation: FTX is in bankruptcy, and a records request goes to an estate,
not an operating exchange. A sanctioned or seized exchange is the same - the
endpoint is evidence, but it is not where the investigator should send a request.
And reaching Binance is not the same action as reaching an Indian exchange:
a foreign VASP is approached through its own law-enforcement channel, with MLAT
for formal evidence, not with a domestic summons.

So each exchange label carries:
    actionable          - False only where a specific bar is RECORDED below
                          (insolvent, sanctioned, seized). True means "no bar is
                          recorded here", not "verified operating", and says so.
    actionable_reason   - the bar, or that none is recorded.
    jurisdiction        - "india" | "foreign" | "unknown". Unknown is the default
                          and is reported as such: the investigator is told to
                          establish it, not handed a guess.

ONLY DOCUMENTED FACTS GO IN THE TABLES. A company missing from them is reported
as "no bar recorded" and "jurisdiction unknown" - never assumed either way.
"""

# Companies with a recorded bar to serving a request. Each reason is the fact
# an investigator would cite.
NOT_ACTIONABLE: dict[str, str] = {
    "FTX": (
        "insolvent: in US Chapter 11 bankruptcy since November 2022. Records are held "
        "by the bankruptcy estate, not an operating exchange"
    ),
    "Garantex": (
        "OFAC-sanctioned (April 2022) and its domains seized by US authorities in "
        "March 2025; not an operating exchange"
    ),
    "GARANTEX EUROPE OU": (
        "OFAC-sanctioned (April 2022) and its domains seized by US authorities in "
        "March 2025; not an operating exchange"
    ),
    "BTC-e": "seized and shut down by US authorities in July 2017",
    "Bitzlato": "seized and shut down by US and European authorities in January 2023",
    "Cryptopia": "in liquidation in New Zealand since May 2019",
}

# Where each company is reached from India. "foreign" means: the company's own
# law-enforcement request channel, and MLAT for evidence meant for court.
JURISDICTION: dict[str, str] = {
    # Indian VASPs (served with a BNSS 94 notice for customer records).
    "Coinswitch": "india",
    # Foreign VASPs.
    **{name: "foreign" for name in (
        "Binance", "Huobi", "Coinbase", "Kraken", "KuCoin", "OKX", "Bybit",
        "Bitfinex", "Gemini", "Gate.io", "Crypto.com", "Bitstamp", "Poloniex",
        "Upbit", "Bithumb", "MEXC", "Deribit", "SwissBorg", "BitMEX", "HitBTC",
        "Paribu", "Indodax", "Bittrex", "Luno", "Coinone", "Exmo", "WhiteBIT",
        "Bitkub", "MaiCoin", "Liquid", "ShapeShift", "Changelly", "FTX",
        "Garantex", "GARANTEX EUROPE OU", "BTC-e", "Bitzlato", "Cryptopia",
        "AscendEX", "BitMart", "Hotbit", "Hoo.com", "Tokocrypto", "XT.com",
    )},
}

NO_BAR_REASON = (
    "no insolvency, sanction or seizure is recorded for this company in our table; "
    "confirm it is operating before serving a request"
)


def status_for(entity: str) -> dict:
    """The actionable / jurisdiction fields for one company name."""
    entity = (entity or "").strip()
    bar = NOT_ACTIONABLE.get(entity)
    return {
        "actionable": bar is None,
        "actionable_reason": bar or NO_BAR_REASON,
        "jurisdiction": JURISDICTION.get(entity, "unknown"),
    }


def request_route(entity: str, jurisdiction: str, address: str = "") -> str:
    """
    The recommended lawful action for an ACTIONABLE VASP, by jurisdiction.

    Names the instrument and the channel, nothing more: section-level drafting is
    not this tool's job.
    """
    target = f" on deposits to {address}" if address else ""
    if jurisdiction == "india":
        return (
            f"Prepare a VASP request to {entity}: a notice under Section 94 of the "
            f"Bharatiya Nagarik Suraksha Sanhita, 2023 for production of customer "
            f"records{target}, covering the transactions in the traced path."
        )
    if jurisdiction == "foreign":
        return (
            f"{entity} is a foreign VASP. Request its customer records{target} through "
            f"{entity}'s own law-enforcement request channel; for evidence to be relied "
            "on in court, route a formal request through MLAT. A domestic BNSS 94 notice "
            "is not the instrument for a foreign entity."
        )
    return (
        f"Establish {entity}'s jurisdiction first. If it is an Indian VASP, a notice under "
        "Section 94 of the Bharatiya Nagarik Suraksha Sanhita, 2023 is the instrument for "
        f"production of customer records{target}; if it is foreign, use its law-enforcement "
        "request channel and MLAT."
    )
