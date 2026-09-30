"""
Value-level taint tracking by FIFO accounting.

WHAT PROBLEM THIS SOLVES
------------------------
Until now the tracer proved CONNECTIVITY: a chain of transfers links the suspect
to an exchange. That is a real finding, but it is weaker than it looks. When a
wallet receives 198 ETH from the suspect and later sends 17,969 ETH onward, the
old output happily reported the 17,969 as "value received" at the next hop. Those
are almost certainly not the same coins. The wallet was simply busy.

Taint tracking answers the narrower, far more useful question: of the money that
arrived at this exchange, how much is traceable to the suspect's funds?

THE ACCOUNTING RULE: FIFO
-------------------------
Coins are fungible, so no rule can be "correct" in a physical sense - a wallet
does not label its satoshis. What we can do is apply ONE stated rule
consistently and say which rule it was. We use first-in-first-out: funds leave a
wallet in the order they arrived.

    receives 10 tainted at t1
    receives 90 clean   at t2
    sends    50         at t3   ->  the first 10 out are tainted, the next 40 clean

This is the rule used in asset-tracing case law for mixed accounts (the
"first-in-first-out" approach to following money through a bank account) and it
is the easiest to explain to a court, which matters more here than elegance.
Alternatives exist - last-in-first-out, or pro-rata "pooling", where the 50 out
would carry 10/100 = 10% taint and so 5 tainted units. They give DIFFERENT
numbers from the same transactions. That is why every figure this module
produces must be reported alongside the name of the rule that produced it.

ORDERING, AND WHY IT IS NOT BFS ORDER
-------------------------------------
FIFO is meaningless without a total order on events, and the order must be TIME,
not the order the tracer happened to discover wallets. The discovery walk is a
breadth-first search: it visits hop 1, then hop 2. But a wallet at hop 2 may
have received funds from a hop-3 wallet earlier in real time. Propagating taint
in BFS order would draw from a queue that had not been filled yet.

So this module ignores the walk order entirely. It takes every transfer the walk
fetched, puts them in one list, sorts them chronologically, and replays them.
Cycles and re-convergence - which laundering routes are full of - then need no
special handling: they are just events at later timestamps.

THE TIE-BREAK (documented because it changes the answer)
-------------------------------------------------------
Many transfers share a timestamp: a block has one timestamp for every
transaction in it, and one transaction can carry several token transfers. FIFO
would otherwise be non-deterministic, and the same input could produce two
different reports. The order is therefore:

    1. timestamp     (unix seconds, from the block)
    2. block number  (a later block is never earlier, even if clocks tie)
    3. transaction index within the block  (the chain's own ordering)
    4. transaction hash        (lexicographic - stable, arbitrary, deterministic)
    5. asset, sender, recipient, value     (separates token transfers in one tx)

Steps 1-3 are real chain ordering. Steps 4-5 are arbitrary but FIXED: they exist
only so that two events the chain itself does not order cannot swap places
between runs. Where the tie-break decides the split, the answer is an artefact of
step 4, so the caller reports how much value that affected.

THE PRE-EXISTING BALANCE PROBLEM
--------------------------------
A wallet may hold funds from before our observation window, or from inflows past
the per-wallet row cap. When it sends more than the inflows we observed can
account for, the shortfall has to be treated as something. We treat it as
UNTAINTED, which is the conservative choice: it never invents a link to the
suspect. It does mean taint can be understated, so the shortfall is counted and
reported as an explicit uncertainty rather than hidden.

WHAT IS STILL NOT MODELLED
--------------------------
Internal transactions (value moved by contract execution) are not fetched, so a
wallet whose funds left via a contract call looks like it still holds them. A
swap that converts ETH to USDT appears as one debit and an unrelated credit in a
different asset: taint does NOT cross assets here. Both understate taint rather
than overstate it.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

# How the numbers below were produced, in one line, for the payload and the PDF.
# Shipped as data rather than prose in a template so the API, the panel and the
# report cannot drift from each other or from the code.
RULE = "FIFO (first in, first out): funds leave a wallet in the order they arrived."

RULE_DETAIL = (
    "Amounts attributed to the suspect are computed by replaying every observed "
    "transfer in chronological order and drawing each outgoing payment from the "
    "front of the wallet's queue of received funds. Ties are broken by block, "
    "then transaction index, then transaction hash. Value a wallet sent that its "
    "observed inflows cannot account for is treated as untainted. A different "
    "accounting rule - last-in-first-out, or pro-rata pooling - would produce "
    "different figures from the same transactions."
)


@dataclass
class AssetFlow:
    """Observed movement of one asset across one edge, with its tainted share."""

    value: float = 0.0
    tainted: float = 0.0
    # Part of `value` that was only payable because we assumed an unobserved
    # pre-existing balance. Carries no taint, and is the uncertainty on this edge.
    assumed_pre_existing: float = 0.0
    tx_count: int = 0

    @property
    def tainted_fraction(self) -> float:
        return (self.tainted / self.value) if self.value > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "value": round(self.value, 8),
            "tainted_value": round(self.tainted, 8),
            "tainted_fraction": round(self.tainted_fraction, 6),
            "assumed_pre_existing": round(self.assumed_pre_existing, 8),
            "tx_count": self.tx_count,
        }


@dataclass
class NodeFlow:
    """One wallet's observed inflow of one asset, and how much of it is tainted."""

    received: float = 0.0
    tainted_received: float = 0.0
    sent: float = 0.0
    tainted_sent: float = 0.0
    assumed_pre_existing: float = 0.0

    @property
    def tainted_fraction(self) -> float:
        """Share of this wallet's OBSERVED inflow that traces to the suspect."""
        return (self.tainted_received / self.received) if self.received > 0 else 0.0


@dataclass
class TaintResult:
    """
    Everything the FIFO replay concluded, keyed for the tracer to attach.

    `edges` is keyed (from, to, asset) and `nodes` (address, asset) - the same
    granularity the rest of the pipeline already uses, so nothing has to be
    re-aggregated downstream.
    """

    edges: dict[tuple[str, str, str], AssetFlow] = field(default_factory=dict)
    nodes: dict[tuple[str, str], NodeFlow] = field(default_factory=dict)
    # Wallets whose full transfer history we pulled. Only for these is the
    # "fraction of inflow" figure computed over complete data.
    observed: set[str] = field(default_factory=set)
    events_replayed: int = 0
    # Total value that was only payable under the pre-existing-balance
    # assumption, per asset. The headline uncertainty.
    assumed_pre_existing: dict[str, float] = field(default_factory=dict)
    # Value whose FIFO position was decided by the arbitrary part of the
    # tie-break (hash order), per asset. Where this is large, the split is an
    # artefact and should be treated as approximate.
    tie_broken_value: dict[str, float] = field(default_factory=dict)

    def edge(self, from_addr: str, to_addr: str, asset: str) -> AssetFlow | None:
        return self.edges.get((from_addr, to_addr, asset))

    def tainted_into(self, address: str) -> dict[str, float]:
        """Per-asset tainted value that reached this wallet. Non-zero only."""
        out: dict[str, float] = {}
        for (addr, asset), flow in self.nodes.items():
            if addr == address and flow.tainted_received > 0:
                out[asset] = round(flow.tainted_received, 8)
        return out

    def inflow_fractions(self, address: str) -> dict[str, float]:
        """Per-asset share of this wallet's observed inflow that is tainted."""
        out: dict[str, float] = {}
        for (addr, asset), flow in self.nodes.items():
            if addr == address and flow.received > 0:
                out[asset] = round(flow.tainted_fraction, 6)
        return out

    def fully_observed(self, address: str) -> bool:
        """
        Did we pull this wallet's own history, or only see it from outside?

        Matters for the inflow fraction: for a wallet we never fetched - an
        exchange at the boundary of the trace, typically - we know what the trace
        sent it but not what else it received, so "80% of its inflow was tainted"
        would be measured against a denominator we do not have.
        """
        return address in self.observed


@dataclass(frozen=True)
class _Event:
    """One transfer, reduced to what the replay needs."""

    timestamp: int
    block: int
    tx_index: int
    tx_hash: str
    asset: str
    from_addr: str
    to_addr: str
    value: float

    def sort_key(self) -> tuple:
        # See "THE TIE-BREAK" in the module docstring. Every component is needed
        # for a total order; the last four are arbitrary but fixed.
        return (
            self.timestamp,
            self.block,
            self.tx_index,
            self.tx_hash,
            self.asset,
            self.from_addr,
            self.to_addr,
            self.value,
        )

    def chain_key(self) -> tuple:
        """The part of the order the blockchain itself decides."""
        return (self.timestamp, self.block, self.tx_index)


def _build_events(fetched: dict[str, list]) -> list[_Event]:
    """
    One event per real transfer, from the per-wallet fetches.

    DEDUPLICATION. A transfer between two fetched wallets appears twice - once in
    the sender's history and once in the recipient's. Counting it twice would
    double the money. Each transfer is therefore attributed to exactly ONE owner:
    the sender if we fetched the sender, otherwise the recipient.

    Why an owner rule and not a set of unique keys: two identical token transfers
    can legitimately occur in a single transaction (same hash, sender, recipient,
    asset and amount), and de-duplicating by value would silently delete one of
    them. The owner rule keeps genuine repeats and drops only the mirrored copy.
    """
    events: list[_Event] = []
    for owner, transfers in fetched.items():
        for t in transfers:
            canonical = t.from_addr if t.from_addr in fetched else t.to_addr
            if canonical != owner:
                continue  # the other side of this transfer owns it
            events.append(
                _Event(
                    timestamp=t.timestamp,
                    block=t.block,
                    tx_index=getattr(t, "tx_index", 0),
                    tx_hash=t.hash,
                    asset=t.asset,
                    from_addr=t.from_addr,
                    to_addr=t.to_addr,
                    value=t.value,
                )
            )
    events.sort(key=_Event.sort_key)
    return events


def _draw(queue: deque[list[float]], amount: float) -> tuple[float, float]:
    """
    Take `amount` off the front of a FIFO queue of [size, tainted] lots.

    Returns (tainted_drawn, shortfall). The shortfall is the part of `amount`
    the queue could not cover - the pre-existing balance we never observed - and
    it carries no taint.

    Each lot is consumed proportionally: taking half a lot takes half its taint.
    Within a lot there is no ordering to appeal to, so proportional is the only
    coherent choice, and for a lot created by a single transfer it is exact.
    """
    remaining = amount
    tainted = 0.0
    while remaining > 1e-18 and queue:
        lot = queue[0]
        size, lot_tainted = lot[0], lot[1]
        if size <= remaining + 1e-18:
            tainted += lot_tainted
            remaining -= size
            queue.popleft()
        else:
            share = remaining / size
            tainted += lot_tainted * share
            lot[0] = size - remaining
            lot[1] = lot_tainted * (1.0 - share)
            remaining = 0.0
    shortfall = max(0.0, remaining)
    return tainted, shortfall


def compute_taint(fetched: dict[str, list], start_address: str) -> TaintResult:
    """
    Replay every observed transfer in time order and attribute value to the suspect.

    `fetched` maps each wallet whose history we pulled to its transfers, BOTH
    directions - incoming rows are what make the FIFO queue orderable, and they
    cost nothing extra because Etherscan's txlist returns both directions in the
    same call we were already making.

    THE SEED. Everything the suspect's own wallet sends is treated as 100%
    tainted. This is a definition, not a measurement: the investigation declares
    those funds to be the subject, and the question asked of every later wallet is
    "how much of what you passed on came from there". The suspect's own inflows
    are therefore not examined - tracing where the suspect got the money is
    backwards from what an investigator needs, as the tracer's own direction
    argument explains.
    """
    start = (start_address or "").lower()
    result = TaintResult(observed=set(fetched))
    events = _build_events(fetched)
    result.events_replayed = len(events)

    # (address, asset) -> queue of [size, tainted] lots, oldest first.
    ledgers: dict[tuple[str, str], deque[list[float]]] = {}

    ambiguous = _ambiguous_events(events)

    def node(address: str, asset: str) -> NodeFlow:
        return result.nodes.setdefault((address, asset), NodeFlow())

    for index, event in enumerate(events):
        asset = event.asset
        sender_key = (event.from_addr, asset)

        if event.from_addr == start:
            # The taint source. The suspect can always pay, and everything it
            # pays is the money under investigation.
            tainted_out, shortfall = event.value, 0.0
        else:
            queue = ledgers.setdefault(sender_key, deque())
            tainted_out, shortfall = _draw(queue, event.value)

        # Credit the recipient with what arrived, carrying its taint forward.
        ledgers.setdefault((event.to_addr, asset), deque()).append(
            [event.value, tainted_out]
        )

        edge = result.edges.setdefault(
            (event.from_addr, event.to_addr, asset), AssetFlow()
        )
        edge.value += event.value
        edge.tainted += tainted_out
        edge.assumed_pre_existing += shortfall
        edge.tx_count += 1

        sender = node(event.from_addr, asset)
        sender.sent += event.value
        sender.tainted_sent += tainted_out
        sender.assumed_pre_existing += shortfall

        recipient = node(event.to_addr, asset)
        recipient.received += event.value
        recipient.tainted_received += tainted_out

        if shortfall > 0:
            result.assumed_pre_existing[asset] = (
                result.assumed_pre_existing.get(asset, 0.0) + shortfall
            )

        if index in ambiguous:
            result.tie_broken_value[asset] = (
                result.tie_broken_value.get(asset, 0.0) + event.value
            )

    return result


def _ambiguous_events(events: list[_Event]) -> set[int]:
    """
    Which events the blockchain itself does not order relative to a sibling.

    An event's FIFO position matters only against other events touching the SAME
    wallet-and-asset queue. When two such events share the chain's entire
    ordering key - timestamp, block and transaction index - the chain expresses
    no preference between them and our hash comparison picks one. Both are
    returned, whether they are credits or debits:

      * two CREDITS tie      -> the order of the lots in the queue is arbitrary,
                                which is what decides the tainted share drawn later;
      * two DEBITS tie       -> which payment drew from the front first is arbitrary;
      * a credit and a debit -> whether the funds had arrived before they left is
                                arbitrary, the most consequential case of the three.

    This measures ORDERING AMBIGUITY, not error. It is an upper bound on the
    value the arbitrary tie-break could have affected - in most ties the outcome
    is identical either way - and it is reported so a reader can see where a split
    rests on our convention rather than on the chain.
    """
    groups: dict[tuple, list[int]] = {}
    for index, event in enumerate(events):
        # Both endpoints: the event moves through the sender's queue and into the
        # recipient's, so it can be ordered ambiguously in either ledger.
        for wallet in (event.from_addr, event.to_addr):
            groups.setdefault((event.chain_key(), wallet, event.asset), []).append(index)

    ambiguous: set[int] = set()
    for indices in groups.values():
        if len(indices) > 1:
            ambiguous.update(indices)
    return ambiguous


def summarise(result: TaintResult, start_address: str) -> dict:
    """
    The payload block describing the taint pass, including its own caveats.

    Shipped with every trace so no consumer has to restate the accounting rule
    or guess at the uncertainty; the panel and the PDF both read this.
    """
    return {
        "rule": "fifo",
        "rule_label": RULE,
        "rule_detail": RULE_DETAIL,
        "events_replayed": result.events_replayed,
        "wallets_observed": len(result.observed),
        "assumed_pre_existing": {
            asset: round(value, 8)
            for asset, value in sorted(result.assumed_pre_existing.items())
            if value > 0
        },
        "assumed_pre_existing_note": (
            "Summed across every wallet in the trace, not the uncertainty on any "
            "one finding. A wallet that spent more than the inflows we observed "
            "must have held funds from before the observation window; that "
            "shortfall is treated as untainted, which understates taint rather "
            "than inventing it. For the figure that applies to a specific "
            "finding, see path_assumed_pre_existing on that finding."
        ),
        "tie_broken_value": {
            asset: round(value, 8)
            for asset, value in sorted(result.tie_broken_value.items())
            if value > 0
        },
        "tie_break_rule": (
            "timestamp, then block number, then transaction index, then "
            "transaction hash"
        ),
        "tie_broken_value_note": (
            "Value moved by transfers the blockchain does not order relative to a "
            "sibling touching the same wallet and asset - same timestamp, block "
            "and transaction index - where our hash comparison chose the order. "
            "An upper bound on what the convention could have affected, not an "
            "error estimate: in most such ties the outcome is the same either way."
        ),
        "start_address": (start_address or "").lower(),
    }
