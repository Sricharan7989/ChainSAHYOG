"""
Entity resolution — collapsing many wallets into the one business behind them.

WHY THIS MATTERS
----------------
An exchange does not have "an address". Binance has thousands: hot wallets,
reserve wallets, and one deposit address per customer. Until now the tool matched
each address on its own, so a trace touching five Binance wallets produced five
separate findings that happened to share a name. That is not how an investigator
thinks, and it is not what gets served: a SAHYOG request goes to **Binance**, once,
citing every address involved. This module produces that single object.

TWO KINDS OF CLUSTER
--------------------
  * NAMED (method known_label): every traced wallet whose label resolves to the
    same entity. This is entity resolution over a curated list - a lookup, not an
    inference, so it inherits the label's confidence.

  * SUSPECTED (method consolidation): a hub wallet with unusual fan-in, plus the
    wallets sweeping into it. An exchange gives each customer their own deposit
    address and sweeps them into one place, so addresses that sweep into a common
    hub are plausibly deposit addresses of a single unnamed exchange. This is an
    INFERENCE and is never given a company name; it keeps the suspected_exchange
    type and the 67% confidence ceiling. A criminal consolidating their own split
    funds produces the identical shape, which is exactly why it stays unnamed.

THE HOP-DISTANCE RULE (and why)
-------------------------------
    A cluster's hop distance is the distance to the FIRST member actually
    reached: min(depth) over members present in this trace.

Three things follow, and all three are deliberate:

  1. Collapsing can never shorten the reported hop count. Each member keeps its
     own BFS depth; the cluster reports the smallest of those. That number is the
     same one the nearest per-address attribution already reported, so the
     headline "N hops" does not move when clustering is switched on.
  2. It can never lengthen it either. We take the minimum, not an average or the
     hub's depth.
  3. Only REACHED members count. A cluster does not borrow the depth of a
     Binance wallet that this trace never touched, which would invent proximity
     the evidence does not support.

Every cluster carries `hop_distance_rule` stating this, and `member_hops` giving
each member's own depth, so the number can be audited rather than trusted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core import identify

# Cluster types that represent "somewhere value can be cashed out", which is what
# an investigator acts on. Mixers and bridges are clustered too (an entity can
# own several pools) but they are not exit points.
VASP_TYPES = ("exchange", "suspected_exchange")

HOP_RULE = (
    "hop_distance is the distance to the first cluster member reached in this "
    "trace (minimum member depth). Clustering never shortens or lengthens the "
    "reported hop count, and unreached members of the same entity are ignored."
)


def _slug(text: str) -> str:
    """A stable, filesystem-and-URL-safe id fragment for an entity name."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "unknown"


@dataclass
class Cluster:
    """
    One real-world entity, and every wallet of it this trace touched.

    `cluster_id` is stable: derived from the entity name for a named cluster and
    from the hub address for a suspected one. The same trace re-run produces the
    same ids, so a report can cite one.
    """

    cluster_id: str
    entity: str
    entity_type: str
    method: str  # known_label | consolidation
    members: list[str] = field(default_factory=list)
    member_hops: dict[str, int] = field(default_factory=dict)
    hop_distance: int = 0
    value_received: dict = field(default_factory=dict)
    confidence_score: int = 0
    named: bool = True
    hub: str | None = None  # suspected clusters only: the wallet they sweep into

    @property
    def member_count(self) -> int:
        return len(self.members)

    @property
    def is_vasp(self) -> bool:
        return self.entity_type in VASP_TYPES

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "entity": self.entity,
            "entity_type": self.entity_type,
            "method": self.method,
            "named": self.named,
            "members": self.members,
            "member_count": self.member_count,
            "member_hops": self.member_hops,
            "hop_distance": self.hop_distance,
            "hop_distance_rule": HOP_RULE,
            "value_received": {k: round(v, 8) for k, v in self.value_received.items()},
            "confidence_score": self.confidence_score,
            "hub": self.hub,
        }


def _value_into(store, address: str) -> dict[str, float]:
    """Per-asset totals into one wallet. Assets are kept apart, never summed."""
    totals: dict[str, float] = {}
    for edge in store.incoming(address):
        for symbol, entry in (edge.get("assets") or {}).items():
            totals[symbol] = totals.get(symbol, 0.0) + entry.get("value", 0.0)
    return totals


def build_clusters(store, attributions, chain: str | None = None) -> list[Cluster]:
    """
    Group the identified wallets of a finished trace into entity clusters.

    Runs after the walk, on attributions that already carry their own hop
    distance and confidence, so clustering only aggregates - it never re-decides
    who a wallet belongs to.

    Returns clusters ordered the way an investigator reads them: nearest first,
    then most confident, then largest.
    """
    named: dict[str, Cluster] = {}
    suspected: dict[str, Cluster] = {}

    for attribution in attributions:
        # The graph key, which is the bare address on the chain the trace started
        # on and a chain-qualified one elsewhere. Once a trace crosses a chain the
        # same address exists as two separate wallets, and cluster membership has
        # to be decided per wallet, not per string.
        address = attribution.node_id or attribution.address
        depth = attribution.hop_distance

        if attribution.method == "consolidation":
            # The hub, plus the wallets sweeping into it: plausibly the deposit
            # addresses of one unnamed exchange. Senders come from the traced
            # graph, so this stays within what we actually observed.
            hub = address
            cluster_id = f"hub:{hub}"
            members = sorted({hub, *store.predecessors(hub)})
            cluster = suspected.setdefault(
                cluster_id,
                Cluster(
                    cluster_id=cluster_id,
                    entity=attribution.entity,
                    entity_type="suspected_exchange",
                    method="consolidation",
                    named=False,
                    hub=hub,
                    confidence_score=attribution.confidence_score,
                ),
            )
            for member in members:
                if member in cluster.members:
                    continue
                cluster.members.append(member)
                cluster.member_hops[member] = store.wallet(member).get("depth", depth)
                for symbol, amount in _value_into(store, member).items():
                    cluster.value_received[symbol] = (
                        cluster.value_received.get(symbol, 0.0) + amount
                    )
            continue

        # Named: every wallet resolving to the same entity on this chain.
        cluster_id = f"label:{_slug(attribution.entity)}"
        cluster = named.setdefault(
            cluster_id,
            Cluster(
                cluster_id=cluster_id,
                entity=attribution.entity,
                entity_type=attribution.entity_type,
                # Carried from the attribution: a cluster named only by
                # inferred labels must not present as a direct label match.
                method=attribution.method,
                named=True,
                confidence_score=attribution.confidence_score,
            ),
        )
        if attribution.method == "known_label":
            cluster.method = "known_label"  # one direct label is enough to name it directly
        if address not in cluster.members:
            cluster.members.append(address)
            cluster.member_hops[address] = depth
            for symbol, amount in _value_into(store, address).items():
                cluster.value_received[symbol] = (
                    cluster.value_received.get(symbol, 0.0) + amount
                )
        # Best confidence among members represents the cluster.
        cluster.confidence_score = max(cluster.confidence_score, attribution.confidence_score)

    clusters = list(named.values()) + list(suspected.values())

    for cluster in clusters:
        cluster.members.sort()
        # THE RULE: first member reached. See the module docstring.
        cluster.hop_distance = min(cluster.member_hops.values(), default=0)

    clusters.sort(
        key=lambda c: (c.hop_distance, -c.confidence_score,
                       -max(c.value_received.values(), default=0.0))
    )
    return clusters


def cluster_index(clusters: list[Cluster]) -> dict[str, str]:
    """address -> cluster_id, so each attribution can name the cluster it joins."""
    index: dict[str, str] = {}
    for cluster in clusters:
        for member in cluster.members:
            # A named cluster wins over a suspected one: a wallet we can name is
            # not also an anonymous deposit address.
            if member in index and cluster.method == "consolidation":
                continue
            index[member] = cluster.cluster_id
    return index
