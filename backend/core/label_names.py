"""
Investigator-facing entity names: the COMPANY, with the wallet's role kept apart.

WHY THIS EXISTS. Label sources name wallets, not companies. GraphSense writes
"binance reserve wallets ETH" and "swisborg reserve wallets"; Etherscan writes
"Coinbase: Miscellaneous" and "Poloniex: BAT". Those strings end up in a police
report as the entity a request is served on, and a request is served on a
company - Binance, SwissBorg - not on "reserve wallets ETH". They also split one
company into several clusters, because clustering groups by entity name.

So every label is reduced to:
    entity  - the company, in its own casing ("KuCoin", not "kucoin")
    role    - what this particular wallet is, where the source said ("ETH reserve
              wallet", "hot wallet", "Commerce"), or absent
and the source's original string is kept on the row as `source_name`, so nothing
the source said is lost and every change can be checked.

THE RULE FOR DOUBT: where a name does not make clear WHICH company holds the
wallet, it is left exactly as it is (see LEAVE_AS_IS, each with its reason). A
wrong company name in a request is worse than an untidy one.

Normalisation is an explicit table plus a few patterns, not a fuzzy matcher: an
investigator or reviewer can read every rule below.
"""

import re

# Names whose company is ambiguous, or which are deliberately distinct entities.
# Left untouched, on purpose.
LEAVE_AS_IS: dict[str, str] = {
    "Wintermute: Binance Deposit": (
        "Wintermute (a market maker) and Binance (the exchange holding the deposit "
        "address) are both named; which company a request belongs with depends on what "
        "is being asked, so the label is not rewritten."
    ),
    "Binance US": "BAM Trading Services (Binance.US) is a separate legal entity from Binance.",
    "Binance JEX": "JEX was a separately branded venue; not merged into Binance without evidence.",
    "Binance Charity": "A charitable foundation, not exchange infrastructure; company unclear.",
    "Exchange A": "A placeholder name in the source; the company is unknown.",
    "Gitcoin Grants: Tornado.cash": "A Gitcoin grant address, not a Tornado Cash contract.",
}

# Explicit rewrites: source name -> (entity, role or None, note or None).
EXPLICIT: dict[str, tuple[str, str | None, str | None]] = {
    "binance reserve wallets ETH": ("Binance", "ETH reserve wallet", None),
    "binance reserve wallets USDT": ("Binance", "USDT reserve wallet", None),
    "Binance: Eth2 Depositor": ("Binance", "Eth2 depositor", None),
    "Binance Pool": ("Binance", "mining pool", None),
    "bitfinex ETH/ERC20 hot wallet": ("Bitfinex", "ETH/ERC-20 hot wallet", None),
    "Bitkub Hot Wallet": ("Bitkub", "hot wallet", None),
    "Bybit reserve wallets": ("Bybit", "reserve wallet", None),
    "C2CX: Hot Wallet": ("C2CX", "hot wallet", None),
    "Coinbase: Coinbase Commerce": ("Coinbase", "Coinbase Commerce", None),
    "Coinbase: Commerce": ("Coinbase", "Coinbase Commerce", None),
    "Coinbase: Miscellaneous": ("Coinbase", None, None),
    "Coinbene: Cold Wallet": ("Coinbene", "cold wallet", None),
    "COSS.io: Warm Wallet": ("COSS.io", "warm wallet", None),
    "crypto.com ERC20 reserves": ("Crypto.com", "ERC-20 reserve wallet", None),
    "deribit reserves": ("Deribit", "reserve wallet", None),
    "FTX Exchange": ("FTX", None, None),
    "huobi reserve wallets ETH": ("Huobi", "ETH reserve wallet", None),
    "huobi reserve wallets SHIB": ("Huobi", "SHIB reserve wallet", None),
    "huobi reserve wallets XCN": ("Huobi", "XCN reserve wallet", None),
    "Kucoin": ("KuCoin", None, None),
    "kucoin reserve wallets": ("KuCoin", "reserve wallet", None),
    "kucoin USDC reserves": ("KuCoin", "USDC reserve wallet", None),
    "kucoin USDT reserves": ("KuCoin", "USDT reserve wallet", None),
    "MEXC: Mexc.com": ("MEXC", None, None),
    "Mexc.com": ("MEXC", None, None),
    # OKEx rebranded as OKX in January 2022; same company.
    "OKEx": ("OKX", None, "formerly OKEx"),
    "Panda.Exchange 1: Hot Wallet": ("Panda.Exchange", "hot wallet 1", None),
    "Panda.Exchange 2: Hot Wallet": ("Panda.Exchange", "hot wallet 2", None),
    # GraphSense's actor is "swissborg"; the label text misspells it.
    "swisborg reserve wallets": ("SwissBorg", "reserve wallet", None),
    "XT.com Hot Wallet": ("XT.com", "hot wallet", None),
    "tornado.cash": ("Tornado Cash", None, None),
    "Tornado Cash Proxy": ("Tornado Cash", "proxy", None),
    "Tornado Cash Router": ("Tornado Cash", "router", None),
}

# Pattern rules, applied only when no explicit rule or exclusion matched.
PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # "Poloniex: BAT" - Poloniex's wallet for one token.
    (re.compile(r"^Poloniex: (.+)$"), "Poloniex", "{0} wallet"),
    # "Tornado.Cash: 1,000 DAI" / "Tornado.Cash: Governance" - one Tornado contract.
    (re.compile(r"^Tornado\.Cash: (.+)$"), "Tornado Cash", "{0}"),
    # "Tornado Cash (1 ETH pool)"
    (re.compile(r"^Tornado Cash \((.+)\)$"), "Tornado Cash", "{0}"),
]


def normalise(name: str) -> tuple[str, str | None, str | None] | None:
    """
    (entity, role, note) for a source name, or None to leave it unchanged.

    None covers both "already clean" and "ambiguous - do not touch".
    """
    name = (name or "").strip()
    if not name or name in LEAVE_AS_IS:
        return None
    if name in EXPLICIT:
        return EXPLICIT[name]
    for pattern, entity, role in PATTERNS:
        m = pattern.match(name)
        if m:
            return entity, role.format(*m.groups()), None
    return None


def apply(meta: dict) -> bool:
    """
    Rewrite one label row in place. Returns True if it changed.

    The source's original string is preserved as `source_name` the first time a
    row is rewritten, so the change is reversible and auditable.
    """
    if meta.get("type") == "sanctioned":
        return False  # OFAC SDN names are the official listing; never rewritten
    result = normalise(meta.get("entity", ""))
    if result is None:
        return False
    entity, role, note = result
    meta.setdefault("source_name", meta.get("entity", ""))
    meta["entity"] = entity
    if role:
        meta["role"] = role
    if note:
        meta["name_note"] = note
    return True
