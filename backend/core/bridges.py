"""
Cross-chain bridge handoff: deciding whether value that left over a bridge is the
same value arriving on the other side.

WHY THIS MODULE IS SEPARATE FROM EVERYTHING ELSE IN THE TOOL.

Every other number this project reports is an OBSERVATION. "Binance received
2.4 ETH from 0xabc" is a transaction on a chain we can read; it is either true or
it is not. A cross-chain handoff cannot be like that. The deposit is visible on
Ethereum and the credit is visible on Arbitrum, but NOTHING in either chain's
public data says the second is the counterpart of the first. They are two
transactions that look alike. Our evidence is circumstantial:

    - the credit lands at the SAME address that deposited (strong: a bridge pays
      out to the address that locked the funds);
    - the amount is close to the deposit, less the bridge's fee (weaker);
    - it arrives within the window the bridge is documented to take (weak);
    - it comes from a contract the registry knows to be part of that bridge
      (strong, but only if we happen to recognise the payout path).

Two people bridging 10 ETH in the same minute is not a rare event, and that
example is indistinguishable from one criminal bridging twice. So this module
never returns a bare "yes". It returns a set of candidates, each with its own
score and the evidence behind it, plus an explicit status:

    matched     - one candidate is clearly better than the rest.
    ambiguous   - two or more are equally plausible. We report ALL of them and
                  stop. Picking one silently would put a coin toss in a police
                  report.
    no_match    - nothing on the destination chain looks like this deposit.
                  This is a real, reportable finding: the trace stops honestly
                  rather than inventing a continuation.
    history_not_reached
                - the destination-chain history we could fetch does not reach back
                  to the deposit, so a match was never looked for. Not a no_match.
    unsupported - a bridge we recognise but deliberately do not follow, with the
                  reason (see config.BRIDGE_UNSUPPORTED).
    not_registered / hop_cap_reached / destination_unavailable
                - we could not even attempt it, and we say which of these it was.

WHY THE SCORE IS NOT THE CONFIDENCE SCORE. core/scoring.py measures how solid a
VASP attribution is; a handoff can never be folded into it, because an exchange
reached "via a bridge we inferred" is a weaker finding than one reached by
observed transfers, and averaging the two would hide that. The handoff carries its
own score, capped below certainty (see config.BRIDGE_MATCH_MAX_SCORE), and the
report prints it next to the evidence rather than inside the headline number.

WHY MATCHING IS PURE. This module does no I/O. The tracer fetches the
destination-chain transfers and hands them in, which keeps every rule below
testable without a network or an API key - and a rule that cannot be tested is a
rule that will be wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app import config
from core import addresses

# How the candidate values compare, in points. These three weights sum to 100
# before the cap, and are the whole scoring model - kept here, in one place, so a
# reviewer can see exactly what a score means.
VALUE_POINTS = 60
TIME_POINTS = 25
CREDIT_SOURCE_POINTS = 15

# A route the registry marks as fee-free (fee_tolerance 0) still compares floats
# derived from integer wei, so "exact" means equal to within this relative margin
# rather than bit-for-bit.
EXACT_MATCH_EPSILON = 1e-9


@dataclass
class Deposit:
    """
    Value observed leaving a wallet for a registered bridge on its own chain.

    This side is fully observed - it is a transaction we can read - which is why
    the deposit is never treated as uncertain and only the credit is.
    """

    wallet: str  # address that sent to the bridge; the credit should land here
    bridge: str  # bridge contract address on the source chain
    chain: str  # source chain slug
    to_chain: str  # destination chain slug
    entity: str  # how the report names the bridge
    asset: str  # symbol that left, e.g. ETH
    dest_asset: str  # symbol that should arrive, e.g. POL across the Polygon bridge
    value: float
    timestamp: int
    tx_hash: str = ""


@dataclass
class Candidate:
    """One destination-chain transfer that could be this deposit's other half."""

    tx_hash: str
    from_addr: str
    to_addr: str
    asset: str
    value: float
    timestamp: int
    lag_sec: int = 0
    value_delta: float = 0.0  # absolute difference between deposit and credit
    value_delta_ratio: float = 0.0  # that difference as a fraction of the deposit
    from_known_credit_source: bool = False
    score: int = 0
    components: dict = field(default_factory=dict)

    def to_payload(self) -> dict:
        """The candidate as it appears in the API payload and the PDF."""
        return {
            "tx_hash": self.tx_hash,
            "from_addr": self.from_addr,
            "to_addr": self.to_addr,
            "asset": self.asset,
            "value": self.value,
            "timestamp": self.timestamp,
            "lag_sec": self.lag_sec,
            "value_delta": self.value_delta,
            "value_delta_ratio": self.value_delta_ratio,
            "from_known_credit_source": self.from_known_credit_source,
            "score": self.score,
            "components": dict(self.components),
        }


@dataclass
class BridgeMatch:
    """
    The outcome of trying to carry one deposit across a bridge.

    `status` is the thing the report leads with; `candidates` is always the full
    evidence, including in the no_match case where it is empty, so that a reader
    can see what was looked for and did not turn up.
    """

    status: str
    reason: str
    deposit: Deposit | None = None
    chosen: Candidate | None = None
    candidates: list = field(default_factory=list)
    spec: dict | None = None
    # Of the amount that arrived, how much is attributed to the suspect. Filled in
    # by the tracer, which is the only component that knows what fraction of the
    # original deposit was the suspect's money. Kept here so the report can say how
    # much of the crossed value is actually under investigation - a crossing can be
    # genuine and still carry none of the suspect's funds.
    tainted_value: float = 0.0
    # Which bridge this is about, for outcomes that never built a Deposit (a
    # bridge with no registered route). Without it the report could only say
    # "Bridge ? -> ?", which names nothing an investigator can look up.
    bridge_entity: str = ""
    bridge_address: str = ""
    bridge_chain: str = ""

    @property
    def matched(self) -> bool:
        return self.status == "matched"

    def to_payload(self) -> dict:
        """
        The handoff as it appears in the API payload and the PDF.

        Every field a reader needs to disagree with us is included: the value
        difference, the time lag, which contracts paid out, and the score. A
        handoff reported without its evidence is indistinguishable from a fact.
        """
        deposit = self.deposit
        payload = {
            "status": self.status,
            "matched": self.matched,
            "reason": self.reason,
            "confidence_score": self.chosen.score if self.chosen else None,
            # How much of the crossed value is the suspect's money, on the chosen
            # candidate. Zero is meaningful and must survive: a bridge can be
            # matched correctly while carrying none of the funds under investigation.
            "tainted_value": round(self.tainted_value, 8),
            "is_inference": True,
            "inference_note": (
                "This is an inference, not an observation. The deposit is "
                "recorded on chain; the arrival of the same value on the "
                "destination chain is matched by amount, timing and destination "
                "address, and no public data links the two transactions."
            ),
            "deposit": None
            if deposit is None
            else {
                "wallet": deposit.wallet,
                "bridge": deposit.bridge,
                "chain": deposit.chain,
                "to_chain": deposit.to_chain,
                "entity": deposit.entity,
                "asset": deposit.asset,
                "dest_asset": deposit.dest_asset,
                "value": deposit.value,
                "timestamp": deposit.timestamp,
                "tx_hash": deposit.tx_hash,
            },
            "chosen": self.chosen.to_payload() if self.chosen else None,
            "candidates": [c.to_payload() for c in self.candidates],
            "evidence": self.evidence(),
        }
        if not self.spec and (self.bridge_entity or self.bridge_address):
            payload["bridge"] = {
                "entity": self.bridge_entity or "Unnamed bridge",
                "address": self.bridge_address,
                "chain": self.bridge_chain,
                "registered": False,
            }
        if self.spec:
            payload["bridge"] = {
                "entity": self.spec.get("entity", ""),
                "how_it_appears": self.spec.get("how_it_appears", ""),
                "verified_from": self.spec.get("verified_from", ""),
                "window_sec": self.spec.get("window_sec", config.BRIDGE_TIME_WINDOW_SEC),
                "fee_tolerance": tolerance_for(self.spec),
            }
        return payload

    def evidence(self) -> dict:
        """
        Why we believe (or do not believe) the handoff, in plain terms.

        A confidence score nobody can interrogate is not much better than no
        score at all. Each line here corresponds to one part of the score.
        """
        deposit = self.deposit
        out = {
            "destination_address_matched": bool(self.chosen),
            "value_delta": self.chosen.value_delta if self.chosen else None,
            "value_delta_ratio": self.chosen.value_delta_ratio if self.chosen else None,
            "lag_sec": self.chosen.lag_sec if self.chosen else None,
            "credit_from_known_bridge_contract": (
                self.chosen.from_known_credit_source if self.chosen else None
            ),
            "asset_renamed_across_bridge": bool(
                deposit and deposit.asset != deposit.dest_asset
            ),
            "candidates_examined": len(self.candidates),
        }
        if deposit:
            out["deposit_asset"] = deposit.asset
            out["credit_asset_expected"] = deposit.dest_asset
            out["fee_tolerance"] = tolerance_for(self.spec or {})
            out["time_window_sec"] = (
                self.spec.get("window_sec", config.BRIDGE_TIME_WINDOW_SEC)
                if self.spec
                else config.BRIDGE_TIME_WINDOW_SEC
            )
        return out


def lookup(chain_slug: str, address: str) -> dict | None:
    """
    The registry entry for a bridge address on a chain, or None.

    None means the tracer found something labelled `bridge` but we have no
    recorded route for it. That is reported as such - it never means "not a
    bridge".
    """
    return config.bridge_lookup(chain_slug, address)


def _window_for(spec: dict) -> int:
    return int(spec.get("window_sec") or config.BRIDGE_TIME_WINDOW_SEC)


def tolerance_for(spec: dict) -> float:
    """
    The fee tolerance for this route: the registry entry's own, else the default.

    Per route because bridges differ: Polygon PoS credits the exact amount, so a
    2% band there would only admit false rivals, while a fee-charging bridge needs
    the slack. Zero means exact (see EXACT_MATCH_EPSILON).
    """
    own = spec.get("fee_tolerance")
    return max(0.0, float(config.BRIDGE_FEE_TOLERANCE if own is None else own))


def _min_amount_for(spec: dict) -> float:
    return float(spec.get("min_amount") or config.BRIDGE_MIN_DEPOSIT)


def _credit_sources(spec: dict) -> set:
    """Contracts that pay out on the destination chain, keyed by that chain's rule."""
    chain = spec.get("to_chain")
    return {addresses.try_normalize(s, chain) or (s or "").strip() for s in spec.get("credit_sources", ())}


def dest_asset_for(spec: dict, asset: str) -> str:
    """
    The symbol the same value is credited under on the destination chain.

    Not cosmetic: bridging native ETH to Polygon credits native POL, so matching
    on the source symbol would reject a handoff that actually happened. An asset
    the registry has no mapping for passes through unchanged, which is the
    optimistic choice - we would rather offer a candidate with a weaker score
    than discard a real handoff over a missing table row.
    """
    mapping = spec.get("asset_map") or {}
    return mapping.get((asset or "").upper(), asset)


def score_candidate(deposit: Deposit, credit, spec: dict) -> Candidate:
    """
    Score one destination-chain transfer against one deposit.

    The three components are deliberately weighted by how much they really tell
    us. Arriving at the address that deposited is the strongest signal, because
    that is what the bridge is built to do. A close amount and a plausible delay
    are weak on their own - plenty of unrelated activity looks like that. Only
    two withdrawals of the same size in the same window are genuinely
    indistinguishable, and that case is handled as ambiguous rather than scored.

    The total is capped at config.BRIDGE_MATCH_MAX_SCORE. This is an inference
    and no amount of circumstantial agreement should let it print as certainty.
    """
    window = max(1, _window_for(spec))
    tolerance = tolerance_for(spec)

    delta = abs(float(credit.value) - float(deposit.value))
    ratio = (delta / float(deposit.value)) if deposit.value > 0 else 1.0
    lag = int(credit.timestamp) - int(deposit.timestamp)
    from_known = (
        addresses.try_normalize(credit.from_addr, spec.get("to_chain")) or ""
    ) in _credit_sources(spec)

    # Value: full marks for an exact amount, tapering to zero at the fee
    # tolerance. A candidate outside tolerance is never scored at all.
    if tolerance <= 0:
        value_points = VALUE_POINTS if ratio <= EXACT_MATCH_EPSILON else 0.0
    else:
        value_points = VALUE_POINTS * max(0.0, 1.0 - (ratio / tolerance))

    # Time: full marks for arriving immediately, tapering to zero at the window.
    time_points = TIME_POINTS * max(0.0, 1.0 - (abs(lag) / float(window)))

    source_points = CREDIT_SOURCE_POINTS if from_known else 0.0

    total = int(round(value_points + time_points + source_points))
    total = min(total, int(config.BRIDGE_MATCH_MAX_SCORE))

    return Candidate(
        tx_hash=credit.hash,
        from_addr=credit.from_addr,
        to_addr=credit.to_addr,
        asset=credit.asset,
        value=float(credit.value),
        timestamp=int(credit.timestamp),
        lag_sec=lag,
        value_delta=delta,
        value_delta_ratio=ratio,
        from_known_credit_source=from_known,
        score=total,
        components={
            "value": int(round(value_points)),
            "time": int(round(time_points)),
            "credit_source": int(round(source_points)),
        },
    )


def match_candidates(deposit: Deposit, transfers: list, spec: dict) -> list:
    """
    Every destination-chain transfer that could be this deposit arriving.

    Four filters, each of which removes false matches rather than true ones:

      same address   - the bridge pays out to whoever locked the funds.
      same asset     - after the registry's rename (ETH -> POL across Polygon).
      within fee     - smaller than the deposit by no more than the tolerance.
      within window  - inside the documented time for THIS direction.

    A credit earlier than its deposit is rejected rather than credited as a
    negative lag: the destination chain cannot mint value from a lock that has
    not happened yet, so such a transfer is by definition not this deposit.
    """
    window = max(1, _window_for(spec))
    tolerance = max(tolerance_for(spec), EXACT_MATCH_EPSILON)
    min_amount = _min_amount_for(spec)

    if deposit.value < min_amount:
        return []

    dest_chain = spec.get("to_chain")
    wallet = addresses.try_normalize(deposit.wallet, dest_chain)
    want_asset = (dest_asset_for(spec, deposit.asset) or "").strip().lower()

    out = []
    for credit in transfers:
        if wallet is None or addresses.try_normalize(credit.to_addr, dest_chain) != wallet:
            continue
        if want_asset and (credit.asset or "").strip().lower() != want_asset:
            continue
        lag = int(credit.timestamp) - int(deposit.timestamp)
        if lag < 0 or lag > window:
            continue
        delta = abs(float(credit.value) - float(deposit.value))
        if deposit.value > 0 and (delta / float(deposit.value)) > tolerance:
            continue
        if float(credit.value) < min_amount:
            continue
        out.append(score_candidate(deposit, credit, spec))

    # Best first, so callers read the leader before the also-rans, and the order
    # is stable for equal scores (by timestamp, then hash) - two runs on the same
    # data must not disagree about which candidate "won".
    out.sort(key=lambda c: (-c.score, c.timestamp, c.tx_hash))
    return out


def resolve(candidates: list, deposit: Deposit | None = None, spec: dict | None = None) -> BridgeMatch:
    """
    Turn candidates into a decision, honestly.

    THE RULE: we follow a crossing only when exactly ONE credit on the
    destination chain falls inside the fee tolerance and the time window. If two
    or more do, the result is ambiguous, every candidate is listed, and the trace
    stops - whatever their scores.

    Why not let the score pick the winner: when credits are the same size, the
    score differs only by time lag and payout source, and neither says which
    withdrawal is the same money. A credit 100 seconds after the deposit and one
    1,700 seconds after are both ordinary bridge delays; ranking the first above
    the second would put a coin toss in a police report and call it a finding.
    The score still ranks the list, so a reader sees the strongest first, but it
    never resolves a tie on its own.
    """
    entity = (spec or {}).get("entity", "the bridge")
    if deposit is not None:
        entity = deposit.entity or entity

    if not candidates:
        return BridgeMatch(
            status="no_match",
            reason=(
                f"No transfer to this address on {deposit.to_chain.upper() if deposit else 'the destination chain'} "
                f"matched the {deposit.value:.6g} {deposit.asset if deposit else ''} deposited to "
                f"{entity} within the documented bridge delay. The deposit is on record; the "
                "money could not be followed past this point."
            ).replace("  ", " "),
            deposit=deposit,
            spec=spec,
        )

    if len(candidates) > 1:
        return BridgeMatch(
            status="ambiguous",
            reason=(
                f"{len(candidates)} transfers on the destination chain each fall within the "
                f"fee tolerance and time window of this deposit (scores "
                f"{', '.join(str(c.score) for c in candidates)}). Time lag and payout "
                "source cannot tell same-sized withdrawals apart, so none is followed "
                "and all are listed."
            ),
            deposit=deposit,
            chosen=None,
            candidates=candidates,
            spec=spec,
        )

    best = candidates[0]
    if best.score < int(config.BRIDGE_MATCH_MIN_SCORE):
        return BridgeMatch(
            status="no_match",
            reason=(
                f"The closest candidate on the destination chain scored {best.score}/100, below the "
                f"{int(config.BRIDGE_MATCH_MIN_SCORE)} needed to claim a match. It is reported "
                "below as a lead rather than treated as the same money."
            ),
            deposit=deposit,
            candidates=candidates,
            spec=spec,
        )

    return BridgeMatch(
        status="matched",
        reason=(
            f"{best.value:.6g} {best.asset} arrived at the same address on the destination chain "
            f"{best.lag_sec} seconds after the deposit, from "
            f"{best.from_addr}, scoring {best.score}/100."
        ),
        deposit=deposit,
        chosen=best,
        candidates=candidates,
        spec=spec,
    )


def unmatched(chain_slug: str, address: str, entity: str = "") -> BridgeMatch:
    """
    A bridge we recognised as a bridge but do not follow.

    Two different states, kept apart: a bridge we deliberately do not support,
    with a stated reason (config.BRIDGE_UNSUPPORTED), and one we simply have no
    route for. Both stop the trace honestly; only the first is a decision.
    """
    reason = config.bridge_unsupported_reason(chain_slug, address)
    who = dict(bridge_entity=entity, bridge_address=address, bridge_chain=chain_slug)
    if reason:
        return BridgeMatch(status="unsupported", reason=reason, spec=None, **who)
    return BridgeMatch(
        status="not_registered",
        reason=(
            f"{entity or address} is labelled a bridge, but its route is not registered in this "
            f"tool, so no handoff was attempted: we do not know which chain it leads to or how its "
            f"payouts appear there. The trace stops at it on {chain_slug} rather than guessing a "
            "destination. This is a gap in our registry, not a claim that the funds did not move."
        ),
        spec=None,
        **who,
    )


def history_not_reached(deposit: Deposit, oldest: int | None, rows: int, spec: dict | None = None) -> BridgeMatch:
    """
    The fetch window on the destination chain ends after the deposit was made.

    A busy wallet's most recent transfers can all post-date a deposit that is
    weeks old, and the matching credit then sits outside what we fetched. Saying
    "no match" here would be a false negative presented as a finding; the honest
    statement is that we could not look that far back.
    """
    when = (
        datetime.fromtimestamp(oldest, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if oldest
        else "an unknown date"
    )
    return BridgeMatch(
        status="history_not_reached",
        reason=(
            f"The {deposit.to_chain} history fetched for this wallet covers only its most recent "
            f"{rows} transfers, reaching back to {when}; the deposit was made before that, so a "
            "matching withdrawal could not be looked for. This is not a finding that none exists."
        ),
        deposit=deposit,
        spec=spec,
    )


def hop_cap_reached(hops_used: int, limit: int, deposit: Deposit | None = None) -> BridgeMatch:
    """A deposit we found but declined to follow, because we are out of crossings."""
    return BridgeMatch(
        status="hop_cap_reached",
        reason=(
            f"This trace has already crossed {hops_used} bridge(s) and the limit is {limit}. "
            "Continuing would multiply the API calls and the graph without making the finding "
            "more reliable, so the trace stops here on purpose."
        ),
        deposit=deposit,
    )


def destination_unavailable(chain_slug: str, deposit: Deposit | None = None) -> BridgeMatch:
    """The bridge is known, but we cannot read the chain it leads to."""
    return BridgeMatch(
        status="destination_unavailable",
        reason=(
            f"The route leads to {chain_slug}, which this build cannot read yet. The bridge "
            "crossing is reported, but nothing beyond it was traced."
        ),
        deposit=deposit,
    )