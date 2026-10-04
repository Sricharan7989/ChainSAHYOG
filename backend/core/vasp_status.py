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
    jurisdiction        - "india" | "foreign_fiu_registered" | "foreign" | "unknown".
                          Unknown is the default and is reported as such: the
                          investigator is told to establish it, not handed a guess.
                          "foreign_fiu_registered" is a foreign VASP registered
                          with FIU-IND as a PMLA reporting entity: it has Indian
                          AML obligations and a Principal Officer in India, so
                          plain MLAT is the wrong first recommendation for it.

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

# Foreign VASPs registered with FIU-IND as reporting entities under the PMLA.
#
# SOURCES. FIU-IND does not publish a list of registered VDA SPs. Its Annual
# Report 2024-25 (fiuindia.gov.in/pdfs/downloads/AnnualReport2024_25.pdf, p.64)
# states the COUNT: "As on 31.03.2025, 49 Virtual Digital Asset Service Providers
# were registered as reporting entities to FIU-India, of which 45 are onshore VDA
# SPs and 4 are offshore VDA SPs." The four names below are each sourced
# separately and account for exactly that count. Each had first been penalised
# by FIU-IND under Section 13 PMLA for operating unregistered (orders on
# fiuindia.gov.in/files/Compliance_Orders/orders.html).
#
# Anything not listed here is NOT asserted to be unregistered - only that we
# could not confirm a registration. Registration can lapse; re-check before use.
FIU_IND_REGISTERED: dict[str, dict] = {
    "KuCoin": {
        "registered": "May 2024",
        "source": "CoinDesk, 10 May 2024: Binance, KuCoin win registration from India's FIU; "
                  "FIU-IND penalty order 08/DIR/FIU-IND/2024 (Peken Global Ltd), 22 Mar 2024",
    },
    "Binance": {
        "registered": "May 2024; services resumed August 2024",
        "source": "CoinDesk, 10 May 2024; TechCrunch, 15 Aug 2024; FIU-IND penalty order "
                  "10/DIR/FIU-IND/2024, 19 Jun 2024",
    },
    "Bybit": {
        "registered": "February 2025",
        "source": "CoinDesk, 6 Feb 2025: Bybit receives India clearance after settling fine; "
                  "FIU-IND penalty order 15/DIR/FIU-IND/2024, 31 Jan 2025",
    },
    "Coinbase": {
        "registered": "March 2025",
        "source": "Coinbase blog, 11 Mar 2025: Coinbase secures registration in India; "
                  "FIU-IND order 16/DIR/FIU-IND/2024, 6 Mar 2025",
    },
}
FIU_IND_CHECKED = "2026-10-04"

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
        "jurisdiction": (
            "foreign_fiu_registered"
            if entity in FIU_IND_REGISTERED
            else JURISDICTION.get(entity, "unknown")
        ),
    }


def fiu_registration(entity: str) -> dict | None:
    """The FIU-IND registration record for a company, with its source, if confirmed."""
    record = FIU_IND_REGISTERED.get((entity or "").strip())
    return None if record is None else {**record, "checked": FIU_IND_CHECKED}


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
    if jurisdiction == "foreign_fiu_registered":
        return (
            f"{entity} is a foreign VASP registered with FIU-IND as a reporting entity under "
            "the PMLA, so it has Indian record-keeping obligations and a Principal Officer "
            f"responsible for compliance in India. Address the request for customer records{target} "
            "to that Principal Officer through its law-enforcement channel. Whether production "
            "can be compelled by a notice under Section 94 of the Bharatiya Nagarik Suraksha "
            "Sanhita, 2023, or MLAT is needed for records held abroad, is the investigating "
            "officer's decision; registration alone does not settle it."
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
