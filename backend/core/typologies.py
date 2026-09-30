"""
Laundering typology detection: pattern rules over the graph we already have.

WHAT THIS IS FOR
----------------
The tracer answers "where did the money go". These rules answer "what does the
movement look like" - and the shapes of laundering are recognisable even when
every wallet involved is anonymous. A peel chain, a fan-out into equal slices, a
wallet that held value for ninety seconds: those are behaviours, not identities,
so they can be seen without knowing who anyone is. For an investigator they do
two jobs. They justify the trace in a case file in words a magistrate can read,
and they distinguish a suspicious route from a merely long one.

HOW EACH RULE IS BUILT, AND THE RULE ABOUT BOOLEANS
---------------------------------------------------
Each detector is a separate function returning `Detection` objects, never a bare
True. A bare boolean is useless here: an investigator cannot put "peel_chain:
true" in a case file, cannot check it, and cannot defend it when challenged. So
every detection carries the wallets and hops involved, the measurements that made
it fire, the thresholds it was judged against, and a plain-language explanation.

WHY THE THRESHOLDS ARE STRICT
-----------------------------
A typology is an accusation wearing the clothes of an observation. A wrong "this
is a peel chain" in a police report discredits the document and the officer
carrying it; a missed one costs a single lead. The asymmetry is enormous, so
every default in config.py sits where the pattern has to be close to unambiguous.
Two further guards matter as much as the numbers:

  * LABELLED BUSINESSES ARE EXEMPT from the wallet-level rules. An exchange hot
    wallet fanning value out into thousands of similar withdrawals is not
    structuring, it is an exchange. Left in, that single case would produce more
    false positives than every other source combined.
  * ROUND AMOUNTS CANNOT FIRE ALONE. Round numbers are ordinary. The detector
    only speaks when another typology already matched the same wallets.

WHAT THESE RULES CANNOT DO
--------------------------
They see structure, never intent. A business with automated treasury sweeps
produces layering's exact signature. Everything here is a reason to look, never a
conclusion, and strength is capped below certainty for that reason.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from app import config
from core import taint as taint_engine


@dataclass
class Detection:
    """
    One matched typology, in a form an investigator can put in a case file.

    `explanation` is the sentence that goes in the file. `measurements` and
    `thresholds` are what make it challengeable: a reader who thinks our bar is
    too low can see the actual numbers and say so, which is the difference
    between a finding and an assertion.
    """

    typology: str          # machine key, e.g. "peel_chain"
    name: str              # what an investigator calls it
    strength: int          # 0-100, capped below certainty
    wallets: list[str]     # every wallet the pattern involves, in order
    hops: list[dict]       # the specific transfers, as {from, to, asset, value}
    explanation: str
    measurements: dict = field(default_factory=dict)
    thresholds: dict = field(default_factory=dict)
    asset: str | None = None
    # True where this detection is only reported because another one matched the
    # same wallets. Round amounts are the only such rule today.
    corroborating_only: bool = False

    def to_dict(self) -> dict:
        return {
            "typology": self.typology,
            "name": self.name,
            "strength": self.strength,
            "wallets": self.wallets,
            "hops": self.hops,
            "explanation": self.explanation,
            "measurements": self.measurements,
            "thresholds": self.thresholds,
            "asset": self.asset,
            "corroborating_only": self.corroborating_only,
        }


# --------------------------------------------------------------------------- #
# A view of the flow, built once and shared by every detector.                #
# --------------------------------------------------------------------------- #


@dataclass
class FlowView:
    """
    Per-wallet, per-asset movement, derived from the transfers already fetched.

    Built from `taint.build_events` rather than from the graph store, for two
    reasons. The events carry individual transfer timestamps, which dwell time
    needs and which the store's aggregated edges have lost. And sharing the
    builder means the typologies and the taint figures cannot disagree about what
    a transfer was or how duplicates were removed.
    """

    # (wallet, asset) -> outgoing transfers, chronological
    out_by: dict[tuple[str, str], list] = field(default_factory=dict)
    # (wallet, asset) -> incoming transfers, chronological
    in_by: dict[tuple[str, str], list] = field(default_factory=dict)
    # wallet -> entity_type from the label set, or None
    entity_types: dict[str, str | None] = field(default_factory=dict)
    observed: set[str] = field(default_factory=set)
    assets: set[str] = field(default_factory=set)
    # Wallets the FIFO pass attributed suspect funds to, plus the suspect itself.
    # An empty set means no taint pass ran, which DISABLES the relevance filter
    # rather than silently suppressing everything.
    tainted: set[str] = field(default_factory=set)

    def sent(self, wallet: str, asset: str) -> float:
        return sum(e.value for e in self.out_by.get((wallet, asset), ()))

    def received(self, wallet: str, asset: str) -> float:
        return sum(e.value for e in self.in_by.get((wallet, asset), ()))

    def is_exempt(self, wallet: str) -> bool:
        """A labelled business whose ordinary operation looks like these patterns."""
        return (
            self.entity_types.get(wallet) or ""
        ) in config.TYPOLOGY_EXEMPT_ENTITY_TYPES

    def is_relevant(self, wallet: str) -> bool:
        """
        Does this wallet handle the suspect's money?

        A trace fetches each wallet's ENTIRE recent history, so most transfers it
        sees belong to strangers. Describing their behaviour is not wrong, but it
        is not the investigation either: on the live demo it buried the findings
        that mattered under 120 detections about unrelated traffic. Where the taint
        pass has run, only wallets it attributed suspect value to are described.
        """
        if not config.TYPOLOGY_TAINTED_ONLY or not self.tainted:
            return True
        return wallet in self.tainted

    def considers(self, wallet: str) -> bool:
        """The two gates every wallet-level detector applies before anything else."""
        return not self.is_exempt(wallet) and self.is_relevant(wallet)

    def material(self, value: float, asset: str) -> bool:
        """
        Is this amount large enough to be worth an investigator's attention?

        Scaled off the asset's own dust threshold so one rule works across assets:
        the live demo otherwise reported a 0.0008 WETH "pass-through", which is
        airdrop residue, not laundering.
        """
        floor = config.dust_threshold_for(asset) * config.TYPOLOGY_MIN_VALUE_MULTIPLE
        return value >= floor

    def recipients(self, wallet: str, asset: str) -> dict[str, float]:
        """Per-recipient totals of one asset out of one wallet."""
        totals: dict[str, float] = {}
        for e in self.out_by.get((wallet, asset), ()):
            totals[e.to_addr] = totals.get(e.to_addr, 0.0) + e.value
        return totals

    def senders(self, wallet: str, asset: str) -> dict[str, float]:
        totals: dict[str, float] = {}
        for e in self.in_by.get((wallet, asset), ()):
            totals[e.from_addr] = totals.get(e.from_addr, 0.0) + e.value
        return totals


def build_flow_view(fetched: dict[str, list], store, taint=None, start=None) -> FlowView:
    """Index every observed transfer by wallet, direction and asset."""
    view = FlowView(observed=set(fetched))
    if taint is not None:
        # Precomputed once. Asking the taint result per wallet would be quadratic.
        view.tainted = {
            address
            for (address, _asset), flow in taint.nodes.items()
            if flow.tainted_received > 0
        }
        if start:
            view.tainted.add(start.lower())
    for event in taint_engine.build_events(fetched):
        view.assets.add(event.asset)
        view.out_by.setdefault((event.from_addr, event.asset), []).append(event)
        view.in_by.setdefault((event.to_addr, event.asset), []).append(event)

    if store is not None:
        for address, data in store.wallets():
            view.entity_types[address] = data.get("entity_type")
    return view


def _strength(ratio: float, floor: float = 0.0) -> int:
    """
    Scale a "how far past the threshold" ratio into a capped strength.

    Never reaches 100: a pattern rule cannot establish intent, and a report that
    says 100% about a behavioural inference is lying about what it knows.
    """
    scaled = max(0.0, min(1.0, ratio))
    value = int(round(floor + (config.TYPOLOGY_STRENGTH_CAP - floor) * scaled))
    return min(value, config.TYPOLOGY_STRENGTH_CAP)


def _short(address: str) -> str:
    return f"{address[:10]}…{address[-6:]}" if len(address) > 20 else address


def _fmt(value: float, asset: str) -> str:
    if value >= 1000:
        return f"{value:,.0f} {asset}"
    return f"{value:,.4f}".rstrip("0").rstrip(".") + f" {asset}"


def _median_dwell(view: FlowView, wallet: str, asset: str) -> float | None:
    """
    Typical time this wallet held the asset before passing it on.

    For each outgoing transfer, how long since the most recent arrival before it.
    The MEDIAN, not the minimum: one fast forward proves nothing, and the minimum
    would let a single quick payment characterise a wallet that otherwise sat on
    funds for weeks. None when no outgoing transfer had a prior arrival at all -
    which means the wallet spent a balance we never saw arrive, and the caller
    must not read that as "held briefly".
    """
    incoming = view.in_by.get((wallet, asset), [])
    outgoing = view.out_by.get((wallet, asset), [])
    if not incoming or not outgoing:
        return None

    dwells: list[float] = []
    for out in outgoing:
        prior = [i for i in incoming if i.timestamp <= out.timestamp]
        if prior:
            dwells.append(float(out.timestamp - prior[-1].timestamp))
    return statistics.median(dwells) if dwells else None


# --------------------------------------------------------------------------- #
# 1. Peel chain                                                               #
# --------------------------------------------------------------------------- #


def detect_peel_chain(view: FlowView) -> list[Detection]:
    """
    A chain of wallets each forwarding the bulk onward while peeling a slice off.

    THE SHAPE. The launderer moves the principal down a line of fresh wallets,
    and at each step splits a small amount towards somewhere it can be cashed
    out. The main flow survives; the peels are the withdrawals. Seen one hop at a
    time it looks like an ordinary payment with change. Seen as a chain, the
    repetition is the signature - which is why a single dominant forward is not
    enough to fire and the links have to be consecutive.

    Each link requires, in one asset: one recipient taking at least
    PEEL_DOMINANT_SHARE of what left the wallet, and at least
    PEEL_MIN_SIDE_OUTPUTS other recipients each taking no more than
    PEEL_MAX_SIDE_SHARE. A pure forward with no peel is layering, not peeling,
    and is reported by that detector instead.
    """
    detections: list[Detection] = []
    seen_links: set[tuple[str, str, str]] = set()

    for (wallet, asset) in sorted(view.out_by):
        if (wallet, asset, "start") in seen_links:
            continue
        chain = _walk_peel_chain(view, wallet, asset)
        if len(chain) < config.PEEL_MIN_LINKS:
            continue

        # Do not re-report a chain we already covered from an earlier wallet.
        key = (chain[0]["from"], chain[-1]["to"], asset)
        if key in seen_links:
            continue
        seen_links.add(key)

        wallets = [chain[0]["from"]] + [link["to"] for link in chain]
        shares = [link["dominant_share"] for link in chain]
        peeled = sum(link["peeled_value"] for link in chain)
        total_side = sum(link["side_outputs"] for link in chain)

        # Strength grows with chain length past the minimum and with how
        # consistently dominant each forward was.
        length_ratio = (len(chain) - config.PEEL_MIN_LINKS) / 3.0
        dominance = (min(shares) - config.PEEL_DOMINANT_SHARE) / (
            1.0 - config.PEEL_DOMINANT_SHARE
        )
        detections.append(
            Detection(
                typology="peel_chain",
                name="Peel chain",
                strength=_strength(0.55 + 0.25 * length_ratio + 0.20 * dominance, floor=40),
                wallets=wallets,
                hops=[
                    {
                        "from": link["from"],
                        "to": link["to"],
                        "asset": asset,
                        "value": round(link["dominant_value"], 8),
                        "peeled_value": round(link["peeled_value"], 8),
                        "side_outputs": link["side_outputs"],
                    }
                    for link in chain
                ],
                asset=asset,
                explanation=(
                    f"{len(chain)} consecutive transfers of {asset} move the bulk of "
                    f"the balance from one wallet to the next, starting at "
                    f"{_short(wallets[0])} and ending at {_short(wallets[-1])}. At "
                    f"every step between {int(min(shares) * 100)}% and "
                    f"{int(max(shares) * 100)}% of the value leaving the wallet goes "
                    f"to a single next wallet, while {total_side} smaller transfer(s) "
                    f"totalling {_fmt(peeled, asset)} are split off along the way. "
                    f"That repeated shape - forward the principal, peel a slice - is "
                    f"characteristic of a wallet chain built to move funds while "
                    f"withdrawing them in portions. It is a pattern in the "
                    f"transfers only, and does not establish who controls any of "
                    f"these wallets or what the smaller transfers were for."
                ),
                measurements={
                    "links": len(chain),
                    "min_dominant_share": round(min(shares), 4),
                    "max_dominant_share": round(max(shares), 4),
                    "total_peeled_value": round(peeled, 8),
                    "side_output_count": total_side,
                },
                thresholds={
                    "min_links": config.PEEL_MIN_LINKS,
                    "dominant_share": config.PEEL_DOMINANT_SHARE,
                    "max_side_share": config.PEEL_MAX_SIDE_SHARE,
                    "min_side_outputs": config.PEEL_MIN_SIDE_OUTPUTS,
                    "min_value_multiple_of_dust": config.TYPOLOGY_MIN_VALUE_MULTIPLE,
                },
            )
        )
    return detections


def _peel_link(view: FlowView, wallet: str, asset: str) -> dict | None:
    """One peel step out of this wallet, or None if it is not one."""
    if not view.considers(wallet):
        return None
    recipients = view.recipients(wallet, asset)
    if len(recipients) < 1 + config.PEEL_MIN_SIDE_OUTPUTS:
        return None
    total = sum(recipients.values())
    if total <= 0:
        return None

    ranked = sorted(recipients.items(), key=lambda kv: -kv[1])
    dominant_addr, dominant_value = ranked[0]
    share = dominant_value / total
    if share < config.PEEL_DOMINANT_SHARE:
        return None

    if not view.material(dominant_value, asset):
        return None

    sides = [(a, v) for a, v in ranked[1:] if v / total <= config.PEEL_MAX_SIDE_SHARE]
    if len(sides) < config.PEEL_MIN_SIDE_OUTPUTS:
        return None
    # Every non-dominant output must be small; one medium output means this is a
    # split, not a peel.
    if len(sides) != len(ranked) - 1:
        return None

    return {
        "from": wallet,
        "to": dominant_addr,
        "dominant_share": share,
        "dominant_value": dominant_value,
        "peeled_value": sum(v for _, v in sides),
        "side_outputs": len(sides),
    }


def _walk_peel_chain(view: FlowView, wallet: str, asset: str) -> list[dict]:
    """Follow dominant forwards while each step is a peel. Cycle-safe."""
    chain: list[dict] = []
    seen = {wallet}
    current = wallet
    while True:
        link = _peel_link(view, current, asset)
        if link is None or link["to"] in seen:
            break
        chain.append(link)
        seen.add(link["to"])
        current = link["to"]
    return chain


# --------------------------------------------------------------------------- #
# 2. Layering                                                                 #
# --------------------------------------------------------------------------- #


def detect_layering(view: FlowView) -> list[Detection]:
    """
    A chain of wallets that each held the funds briefly and forwarded nearly all.

    THE SHAPE. Distance for its own sake. Each wallet receives, waits a few
    minutes, and sends on essentially the whole amount; nothing is bought, nothing
    is kept. The absence of any economic purpose is the point - the hops exist to
    put ground between the source and the destination.

    Distinct from a peel chain in what is KEPT: layering keeps nothing
    (LAYERING_MIN_FORWARD_RATIO, 0.95 by default), peeling deliberately keeps a
    slice. Both can legitimately match the same wallets, and both are reported,
    because they are different observations about the same transfers.
    """
    detections: list[Detection] = []
    reported: set[tuple[str, str]] = set()

    for (wallet, asset) in sorted(view.in_by):
        chain = _walk_layering_chain(view, wallet, asset)
        if len(chain) < config.LAYERING_MIN_LINKS:
            continue
        wallets = [chain[0]["from"]] + [link["to"] for link in chain]
        key = (wallets[0], wallets[-1])
        if key in reported:
            continue
        reported.add(key)

        dwells = [link["dwell_sec"] for link in chain]
        ratios = [link["forward_ratio"] for link in chain]
        worst_dwell = max(dwells)

        detections.append(
            Detection(
                typology="layering",
                name="Layering",
                strength=_strength(
                    0.5 + 0.5 * (1.0 - worst_dwell / max(config.LAYERING_MAX_DWELL_SEC, 1)),
                    floor=35,
                ),
                wallets=wallets,
                hops=[
                    {
                        "from": link["from"],
                        "to": link["to"],
                        "asset": asset,
                        "value": round(link["value"], 8),
                        "dwell_sec": int(link["dwell_sec"]),
                        "forward_ratio": round(link["forward_ratio"], 4),
                    }
                    for link in chain
                ],
                asset=asset,
                explanation=(
                    f"{asset} passes through {len(chain)} wallets in sequence from "
                    f"{_short(wallets[0])} to {_short(wallets[-1])}, and each wallet "
                    f"in between forwards at least "
                    f"{int(min(ratios) * 100)}% of what it received after holding it "
                    f"for a median of {_duration(statistics.median(dwells))} (longest "
                    f"{_duration(worst_dwell)}). None of these wallets retains a "
                    f"meaningful balance or appears to transact for any other "
                    f"purpose, which is consistent with hops added to lengthen the "
                    f"trail rather than to move value to a destination. An automated "
                    f"treasury or sweeping service can produce the same pattern, so "
                    f"this describes the shape of the movement, not its purpose."
                ),
                measurements={
                    "links": len(chain),
                    "median_dwell_sec": int(statistics.median(dwells)),
                    "max_dwell_sec": int(worst_dwell),
                    "min_forward_ratio": round(min(ratios), 4),
                },
                thresholds={
                    "min_links": config.LAYERING_MIN_LINKS,
                    "max_dwell_sec": config.LAYERING_MAX_DWELL_SEC,
                    "min_forward_ratio": config.LAYERING_MIN_FORWARD_RATIO,
                    "max_forward_ratio": config.LAYERING_MAX_FORWARD_RATIO,
                    "min_value_multiple_of_dust": config.TYPOLOGY_MIN_VALUE_MULTIPLE,
                },
            )
        )
    return detections


def _layering_link(view: FlowView, wallet: str, asset: str) -> dict | None:
    """Did this wallet receive, hold briefly, and forward nearly everything?"""
    if not view.considers(wallet):
        return None
    received = view.received(wallet, asset)
    sent = view.sent(wallet, asset)
    if received <= 0 or sent <= 0:
        return None
    if not view.material(received, asset):
        return None
    ratio = sent / received
    # A CEILING AS WELL AS A FLOOR. Sending much more than we saw arrive means the
    # funding came from before our observation window, so this wallet is not
    # demonstrably forwarding the value we traced - see PASS_THROUGH_MAX_FORWARD.
    if not config.LAYERING_MIN_FORWARD_RATIO <= ratio <= config.LAYERING_MAX_FORWARD_RATIO:
        return None

    dwell = _median_dwell(view, wallet, asset)
    # A zero-second dwell means in and out in the same block: a swap or a contract
    # call, not a wallet that held custody of anything.
    if dwell is None or not 1 <= dwell <= config.LAYERING_MAX_DWELL_SEC:
        return None

    recipients = view.recipients(wallet, asset)
    if not recipients:
        return None
    nxt, value = max(recipients.items(), key=lambda kv: kv[1])
    return {
        "from": wallet,
        "to": nxt,
        "value": value,
        "dwell_sec": dwell,
        "forward_ratio": ratio,
    }


def _walk_layering_chain(view: FlowView, wallet: str, asset: str) -> list[dict]:
    chain: list[dict] = []
    seen = {wallet}
    current = wallet
    while True:
        link = _layering_link(view, current, asset)
        if link is None or link["to"] in seen:
            break
        chain.append(link)
        seen.add(link["to"])
        current = link["to"]
    return chain


def _duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 90:
        return f"{seconds} seconds"
    if seconds < 5400:
        return f"{seconds // 60} minutes"
    if seconds < 172800:
        return f"{seconds // 3600} hours"
    return f"{seconds // 86400} days"


# --------------------------------------------------------------------------- #
# 3. Structuring / smurfing                                                   #
# --------------------------------------------------------------------------- #


def _similar_group(amounts: list[float], max_cv: float) -> list[float]:
    """
    The largest set of amounts tight enough to look deliberately equal.

    Anchored on the median and widened until the coefficient of variation would
    break the bar. Using the median rather than the mean matters: one enormous
    outgoing transfer would drag a mean far enough to swallow everything else.
    """
    if len(amounts) < 2:
        return []
    ordered = sorted(amounts)
    median = statistics.median(ordered)
    if median <= 0:
        return []
    # Candidates closest to the median first.
    by_distance = sorted(ordered, key=lambda v: abs(v - median))
    group: list[float] = []
    for value in by_distance:
        trial = group + [value]
        if len(trial) < 2:
            group = trial
            continue
        mean = statistics.fmean(trial)
        if mean <= 0:
            continue
        cv = statistics.pstdev(trial) / mean
        if cv <= max_cv:
            group = trial
        # Do not break: a later, closer value may still fit.
    return group


def detect_structuring(view: FlowView) -> list[Detection]:
    """
    Value split into, or gathered from, many deliberately similar amounts.

    THE SHAPE. Splitting one sum into many near-identical pieces (smurfing), or
    collecting many near-identical pieces into one (a collection account). Both
    are attempts to stay below a threshold somebody is watching, or to spread
    value across enough accounts that no single one looks notable.

    SIMILARITY CARRIES THE RULE, NOT COUNT. "Many outputs" describes every active
    wallet on the chain. Many outputs that are all within a few percent of each
    other is a different claim. Labelled exchanges, mixers and bridges are
    excluded: paying out thousands of similar withdrawals is what they do.
    """
    detections: list[Detection] = []

    for (wallet, asset) in sorted(set(view.out_by) | set(view.in_by)):
        if not view.considers(wallet):
            continue

        for direction, minimum in (
            ("out", config.STRUCTURING_MIN_OUTPUTS),
            ("in", config.STRUCTURING_MIN_INPUTS),
        ):
            counterparties = (
                view.recipients(wallet, asset)
                if direction == "out"
                else view.senders(wallet, asset)
            )
            if len(counterparties) < minimum:
                continue
            group = _similar_group(list(counterparties.values()), config.STRUCTURING_MAX_CV)
            if len(group) < minimum:
                continue

            mean = statistics.fmean(group)
            # Six near-identical dust payments are airdrop spam, not structuring.
            if not view.material(mean, asset):
                continue
            cv = statistics.pstdev(group) / mean if mean else 1.0
            members = sorted(
                (a for a, v in counterparties.items() if v in group or _close(v, group)),
                key=lambda a: -counterparties[a],
            )[: len(group)]

            fan_out = direction == "out"
            detections.append(
                Detection(
                    typology="structuring_fan_out" if fan_out else "structuring_fan_in",
                    name="Structuring (split into equal parts)"
                    if fan_out
                    else "Structuring (collection of equal parts)",
                    strength=_strength(
                        0.45
                        + 0.35 * min(1.0, (len(group) - minimum) / 6.0)
                        + 0.20 * (1.0 - cv / max(config.STRUCTURING_MAX_CV, 1e-9)),
                        floor=35,
                    ),
                    wallets=[wallet] + members,
                    hops=[
                        {
                            "from": wallet if fan_out else other,
                            "to": other if fan_out else wallet,
                            "asset": asset,
                            "value": round(counterparties[other], 8),
                        }
                        for other in members
                    ],
                    asset=asset,
                    explanation=(
                        (
                            f"{_short(wallet)} sent {asset} to {len(group)} different "
                            f"wallets in amounts that are all close to "
                            f"{_fmt(mean, asset)}"
                        )
                        if fan_out
                        else (
                            f"{len(group)} different wallets each sent close to "
                            f"{_fmt(mean, asset)} of {asset} to {_short(wallet)}"
                        )
                    )
                    + (
                        f" - they vary by only {cv * 100:.1f}% around that figure. "
                        f"Amounts that uniform are chosen, not incidental: value is "
                        f"being deliberately broken into equal parts"
                        + (
                            ", which is done to keep individual transfers below a "
                            "reporting or monitoring threshold and to spread them "
                            "across accounts."
                            if fan_out
                            else ", then gathered into one account, which is how "
                            "funds distributed for that purpose are brought back "
                            "together."
                        )
                        + " Regular scheduled payments of a fixed size can look "
                        "identical, and this wallet is not a labelled business, so "
                        "the purpose of the payments is not established here."
                    ),
                    measurements={
                        "direction": "fan_out" if fan_out else "fan_in",
                        "similar_count": len(group),
                        "counterparty_count": len(counterparties),
                        "mean_amount": round(mean, 8),
                        "coefficient_of_variation": round(cv, 4),
                    },
                    thresholds={
                        "min_counterparties": minimum,
                        "max_coefficient_of_variation": config.STRUCTURING_MAX_CV,
                        "min_value_multiple_of_dust": config.TYPOLOGY_MIN_VALUE_MULTIPLE,
                    },
                )
            )
    return detections


def _close(value: float, group: list[float]) -> bool:
    return any(abs(value - g) <= 1e-12 for g in group)


# --------------------------------------------------------------------------- #
# 4. Rapid pass-through                                                       #
# --------------------------------------------------------------------------- #


def detect_pass_through(view: FlowView) -> list[Detection]:
    """
    A single wallet that received value and sent it straight back out.

    THE SHAPE. A conduit. Value arrives and leaves inside a short window, and
    almost nothing stays. Distinct from layering, which is a claim about a CHAIN:
    this is a claim about one wallet, so it still fires at the edge of the trace
    where the next wallet was never expanded and no chain can be seen.
    """
    detections: list[Detection] = []

    for (wallet, asset) in sorted(view.in_by):
        if not view.considers(wallet):
            continue
        received = view.received(wallet, asset)
        sent = view.sent(wallet, asset)
        if received <= 0 or sent <= 0:
            continue
        if not view.material(received, asset):
            continue
        forward_ratio = sent / received
        # BOTH BOUNDS MATTER. Below the floor the wallet kept the money and is a
        # destination, not a conduit. Above the ceiling it sent far more than we
        # saw arrive, so most of its outflow was funded before our observation
        # window began - calling that a conduit for the traced value is
        # unsupported, and on the live demo it produced claims of "forwarded
        # 31,809% of what it received", which is not a sentence that belongs in a
        # police report.
        if not (
            config.PASS_THROUGH_MIN_FORWARD
            <= forward_ratio
            <= config.PASS_THROUGH_MAX_FORWARD
        ):
            continue

        dwell = _median_dwell(view, wallet, asset)
        # Reject a zero-second dwell: in and out in one block is a swap or a
        # contract call, not custody passing through a wallet.
        if dwell is None or not 1 <= dwell <= config.PASS_THROUGH_MAX_WINDOW_SEC:
            continue

        incoming = view.in_by[(wallet, asset)]
        outgoing = view.out_by.get((wallet, asset), [])
        window = max(0, outgoing[-1].timestamp - incoming[0].timestamp)

        detections.append(
            Detection(
                typology="rapid_pass_through",
                name="Rapid pass-through",
                strength=_strength(
                    0.45
                    + 0.35 * (1.0 - dwell / max(config.PASS_THROUGH_MAX_WINDOW_SEC, 1))
                    + 0.20 * min(1.0, forward_ratio),
                    floor=30,
                ),
                wallets=[wallet],
                hops=[
                    {
                        "from": e.from_addr,
                        "to": e.to_addr,
                        "asset": asset,
                        "value": round(e.value, 8),
                        "timestamp": e.timestamp,
                    }
                    for e in (incoming[:3] + outgoing[:3])
                ],
                asset=asset,
                explanation=(
                    f"{_short(wallet)} received {_fmt(received, asset)} and forwarded "
                    f"{_fmt(sent, asset)} of it - {int(forward_ratio * 100)}% - "
                    f"holding the funds for a median of {_duration(dwell)}, with the "
                    f"whole movement in and out completed inside "
                    f"{_duration(window)}. A wallet that keeps nothing and forwards "
                    f"almost immediately is acting as a conduit rather than as a "
                    f"destination, so the funds' owner is more likely to be found "
                    f"further along the chain than here. This says nothing about who "
                    f"operates the wallet; automated forwarding services behave the "
                    f"same way."
                ),
                measurements={
                    "received": round(received, 8),
                    "sent": round(sent, 8),
                    "forward_ratio": round(forward_ratio, 4),
                    "median_dwell_sec": int(dwell),
                    "window_sec": int(window),
                },
                thresholds={
                    "max_window_sec": config.PASS_THROUGH_MAX_WINDOW_SEC,
                    "min_forward_ratio": config.PASS_THROUGH_MIN_FORWARD,
                    # Load-bearing too, so it is listed: without the ceiling this
                    # rule fired on wallets funded before our observation window.
                    "max_forward_ratio": config.PASS_THROUGH_MAX_FORWARD,
                    "min_value_multiple_of_dust": config.TYPOLOGY_MIN_VALUE_MULTIPLE,
                },
            )
        )
    return detections


# --------------------------------------------------------------------------- #
# 5. Round amounts - corroborating only                                       #
# --------------------------------------------------------------------------- #


def _significant_digits(value: float) -> int:
    """
    How many significant digits a positive amount carries.

    Trailing zeros are NOT significant, on either side of the point: 500 carries
    one significant digit (5x10^2), not three, and 1,000 carries one. Counting
    them would have meant no whole round number ever qualified as round, which is
    the opposite of what this detector is for. 1,250 carries three and 100.5 four,
    so genuinely computed-looking amounts still score high.
    """
    if value <= 0:
        return 99
    digits = f"{value:.8f}".replace(".", "").strip("0")
    return len(digits) if digits else 1


def detect_round_amounts(view: FlowView) -> list[Detection]:
    """
    Transfers in suspiciously round numbers.

    DELIBERATELY WEAK, AND STRUCTURALLY PREVENTED FROM FIRING ALONE. People send
    1 ETH and 1,000 USDT all the time; round amounts alone say nothing at all.
    What they add is corroboration: value moving in flat, round figures suggests
    amounts chosen by a person or a script rather than amounts arising from
    commerce, and that is worth a line in a case file ONLY next to a pattern that
    already stands on its own. `detect_all` drops every detection from here that
    does not share wallets with another typology, and each is marked
    `corroborating_only` so no consumer can present it as a finding by itself.
    """
    detections: list[Detection] = []

    for (wallet, asset), outgoing in sorted(view.out_by.items()):
        if not view.considers(wallet):
            continue
        if len(outgoing) < config.ROUND_AMOUNT_MIN_COUNT:
            continue
        round_ones = [
            e
            for e in outgoing
            if _significant_digits(e.value) <= config.ROUND_AMOUNT_MAX_SIG_DIGITS
        ]
        if len(round_ones) < config.ROUND_AMOUNT_MIN_COUNT:
            continue
        share = len(round_ones) / len(outgoing)
        if share < config.ROUND_AMOUNT_MIN_SHARE:
            continue

        values = sorted({e.value for e in round_ones})
        detections.append(
            Detection(
                typology="round_amounts",
                name="Round-value transfers",
                strength=_strength(0.25 + 0.35 * share, floor=15),
                wallets=[wallet] + sorted({e.to_addr for e in round_ones}),
                hops=[
                    {
                        "from": e.from_addr,
                        "to": e.to_addr,
                        "asset": asset,
                        "value": round(e.value, 8),
                    }
                    for e in round_ones[:8]
                ],
                asset=asset,
                corroborating_only=True,
                explanation=(
                    f"{len(round_ones)} of the {len(outgoing)} {asset} transfers out "
                    f"of {_short(wallet)} are flat round figures "
                    f"({', '.join(_fmt(v, asset) for v in values[:4])}"
                    f"{'…' if len(values) > 4 else ''}). Amounts like these are "
                    f"chosen rather than computed, which fits value being moved to "
                    f"order rather than paid for goods or services. On its own this "
                    f"means very little - round transfers are entirely normal - and "
                    f"it is recorded here only as corroboration for the other "
                    f"pattern(s) found on these wallets."
                ),
                measurements={
                    "round_transfers": len(round_ones),
                    "total_transfers": len(outgoing),
                    "round_share": round(share, 4),
                    "distinct_values": [round(v, 8) for v in values[:8]],
                },
                thresholds={
                    "max_significant_digits": config.ROUND_AMOUNT_MAX_SIG_DIGITS,
                    "min_count": config.ROUND_AMOUNT_MIN_COUNT,
                    "min_share": config.ROUND_AMOUNT_MIN_SHARE,
                },
            )
        )
    return detections


# --------------------------------------------------------------------------- #
# Entry point                                                                 #
# --------------------------------------------------------------------------- #

DETECTORS = (
    detect_peel_chain,
    detect_layering,
    detect_structuring,
    detect_pass_through,
)


def detect(fetched: dict[str, list], store=None, taint=None, start=None):
    """
    Run every detector and return (detections, suppressed_count), strongest first.

    `taint` restricts the detectors to wallets carrying the suspect's funds, which
    is what keeps the output about the investigation rather than about every
    stranger whose history the trace happened to fetch. Pass None to describe the
    whole fetched graph.

    Round amounts are handled last and separately: any such detection that does
    not share a wallet with a detection from another typology is DISCARDED, which
    is how "do not let it fire alone" is enforced in code rather than in a comment
    somebody can overlook.

    The suppressed count is returned rather than dropped so a capped list can
    never be mistaken for a complete one.
    """
    view = build_flow_view(fetched, store, taint=taint, start=start)

    detections: list[Detection] = []
    for detector in DETECTORS:
        detections.extend(detector(view))

    if detections:
        corroborated = {w for d in detections for w in d.wallets}
        for weak in detect_round_amounts(view):
            if corroborated.intersection(weak.wallets):
                detections.append(weak)

    detections.sort(key=lambda d: (-d.strength, d.typology, d.wallets[0]))
    suppressed = max(0, len(detections) - config.TYPOLOGY_MAX_REPORTED)
    return detections[: config.TYPOLOGY_MAX_REPORTED], suppressed


def summarise(detections: list[Detection], suppressed: int = 0) -> dict:
    """The payload block: what matched, and the caveat that governs all of it."""
    return {
        "count": len(detections),
        "suppressed": suppressed,
        "scope": (
            "Only wallets the FIFO taint pass attributed suspect funds to are "
            "described, so patterns in unrelated traffic through the same wallets "
            "are not reported."
            if config.TYPOLOGY_TAINTED_ONLY
            else "Every wallet in the fetched graph is described, whether or not it "
            "handled the suspect's funds."
        ),
        "typologies": sorted({d.typology for d in detections}),
        "strongest": detections[0].typology if detections else None,
        "caveat": (
            "Typologies are patterns in the transfer graph, not conclusions about "
            "intent. Each is a reason to investigate further and states the "
            "measurements and thresholds that produced it so they can be "
            "challenged. Legitimate automated activity can reproduce every pattern "
            "here, and strength is never reported as certainty."
        ),
        "thresholds_note": (
            "Thresholds are deliberately strict: a wrongly asserted typology in a "
            "police report is more damaging than a missed one. All of them are "
            "configurable - see the typology settings in config.py."
        ),
    }
