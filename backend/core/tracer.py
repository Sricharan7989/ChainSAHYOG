"""
The tracing engine — follows stolen funds forward until they reach a VASP.

THE CORE INSIGHT THIS MODULE IMPLEMENTS
---------------------------------------
Criminals launder crypto by moving it through a chain of fresh, anonymous,
self-controlled "unhosted" wallets. Those wallets are brand new and carry no
identity, so trying to recognise THEM is hopeless. But crypto only becomes
spendable cash at a centralised exchange (a VASP), which performed KYC and
cannot hide: it is a large regulated business with a stable, recognisable
on-chain fingerprint.

So we do not try to identify the criminal. We follow the money THROUGH the
anonymous wallets until it arrives somewhere we recognise. This module walks
that trail and calls identify.py at every wallet it meets; the moment a wallet
is recognised as an exchange, that branch is finished - we have found the exit
point, and that is the actionable answer.

WHY WE FOLLOW OUTGOING EDGES
----------------------------
At every wallet we ask "where did the money go NEXT", never "where did it come
from". An edge is only added for a transaction where the current node is the
SENDER. Following incoming edges instead would walk backwards into the funds'
history - the victims, the earlier owners - which is the opposite of what an
investigator needs. They already know the suspect; what they need is the
downstream exit point where the funds hit a KYC'd business that can freeze them
and identify the account holder. The direction of traversal IS the product.

WHY WE CAP DEPTH (fan-out explosion)
------------------------------------
Ethereum wallets have unbounded out-degree. If each wallet sends to just 20
others, an uncapped forward walk touches 20 wallets at hop 1, 400 at hop 2,
8,000 at hop 3 and 160,000 at hop 4 - and a single exchange hot wallet alone can
send to tens of thousands of addresses, so in practice it is far worse than
that. Each wallet also costs an API call against a 5-calls/sec free tier, so an
uncapped trace does not merely get slow, it never finishes and gets the API key
rate-limited on the way.

Four limits keep this bounded, and each discards the LEAST informative work:
  * identification  - stop the moment a branch reaches an exchange, mixer or
                      bridge. This is the most valuable cap of the four: it
                      ends branches exactly where the answer is, and it stops
                      us from expanding the highest-degree wallets on the whole
                      chain, which is what exchange hot wallets are.
  * max_depth       - laundering chains are short in practice; the exit point is
                      usually within a few hops, and everything past that is
                      noise anyway.
  * dust_threshold  - tiny transfers are spam, gas dust and airdrop noise. The
                      stolen principal moves in meaningful amounts, so following
                      value below the threshold chases decoys, not the money.
  * MAX_EDGES_PER_NODE - per wallet, expand only the largest outgoing transfers.
                      If a wallet split funds 500 ways, the big branches are
                      where the principal went; the long tail is chaff.

WHAT THE WALK PROVES, AND WHAT THE TAINT PASS ADDS
-------------------------------------------------
The walk above proves CONNECTIVITY: transfers link the suspect to an exchange.
On its own that is weaker than it reads, because expanding a wallet follows its
large outgoing transfers regardless of where those particular coins came from.
A wallet that received 198 ETH from the suspect and later sent 17,969 ETH onward
was simply busy; the old output reported the 17,969 at the next hop.

So after the walk, `taint.compute_taint` replays every transfer we fetched in
chronological order under a stated accounting rule (FIFO) and works out how much
of each edge is attributable to the suspect's funds. That is a SEPARATE pass, not
a change to the walk: taint has to be computed in time order, and the walk visits
in breadth-first order, which is not the same thing. See core/taint.py.

Both figures are kept. `value_received` remains the gross amount an endpoint
received along traced edges; `tainted_value_received` is the part attributable to
the suspect. Reporting only the first overstates the case and reporting only the
second hides the context, so the output carries both and says which is which.

SCOPE (current stage)
---------------------
Native transfers and allowlisted ERC-20 tokens are traced. Internal transactions
(value moved by contract execution) are still NOT fetched, so a wallet that
forwarded funds through a contract call looks like it still holds them. Taint does
not cross assets: a swap from ETH to USDT breaks the chain of attribution.
"""

import time
from collections import deque
from dataclasses import dataclass, field

import networkx as nx

from app import config
from core import (
    bridges,
    clustering,
    identify,
    scoring,
    taint as taint_engine,
    typologies,
)
from services import graph_store
from services.etherscan import EtherscanClient, Transfer, get_client, normalize_address


@dataclass
class Hop:
    """
    One step of the money flow: funds moving from one wallet to the next.

    A Hop is an aggregate, not a single transaction. If a wallet paid the same
    recipient eleven times, that is one hop carrying the summed value - an
    investigator cares that the money went A -> B and how much, not that it was
    split across eleven transactions.
    """

    depth: int  # hops from the start address; the first hop out is depth 1
    from_addr: str
    to_addr: str
    value: float
    tx_count: int
    timestamp: int  # most recent transaction on this edge, unix epoch
    tx_hash: str  # the single largest transaction, as a citable example
    asset: str = "ETH"
    contract: str | None = None
    # Of `value`, how much is attributable to the suspect under FIFO accounting,
    # and how much was only payable by assuming an unobserved prior balance.
    # Filled in by the taint pass after the walk; 0.0 when taint was not computed.
    tainted_value: float = 0.0
    assumed_pre_existing: float = 0.0
    # Which chain this leg happened on, and whether it is an ordinary transfer or
    # a bridge crossing. `edge_type` is what lets the graph, the path view and
    # the PDF draw a chain crossing differently from a transfer, instead of the
    # crossing looking like any other hop.
    chain: str = ""
    edge_type: str = "transfer"  # transfer | cross_chain
    # For a cross_chain hop only: the bridges.BridgeMatch behind it. Kept on the
    # hop so the evidence travels with the fact rather than being looked up.
    handoff: object | None = None

    def to_dict(self) -> dict:
        return {
            "depth": self.depth,
            "from": self.from_addr,
            "to": self.to_addr,
            "value": round(self.value, 8),
            "asset": self.asset,
            "contract": self.contract,
            # Kept so older consumers still read a number; native only, and 0 for
            # a token hop - read `value` and `asset` instead.
            "value_eth": round(self.value, 8) if self.contract is None else 0.0,
            "tx_count": self.tx_count,
            "timestamp": self.timestamp,
            "tx_hash": self.tx_hash,
            # How much of this leg is the suspect's money under FIFO, and how
            # much of it rests on assuming an unobserved prior balance.
            "tainted_value": round(self.tainted_value, 8),
            "tainted_fraction": (
                round(self.tainted_value / self.value, 6) if self.value else 0.0
            ),
            "assumed_pre_existing": round(self.assumed_pre_existing, 8),
            "chain": self.chain,
            "edge_type": self.edge_type,
            # The full match evidence for a bridge crossing: value difference, lag,
            # which contract paid out, and the score. Absent on ordinary transfers.
            "handoff": self.handoff.to_payload() if self.handoff is not None else None,
        }


@dataclass
class Attribution:
    """
    A recognised endpoint: the answer the investigation is looking for.

    `hop_distance` is the headline number - "funds reached Binance 3 hops away".
    Because the walk is breadth-first, it is the SHORTEST path to that entity,
    not an artefact of traversal order. `method` and `confidence` travel with it
    so the claim can be weighed rather than taken on faith.
    """

    address: str
    entity: str
    entity_type: str  # exchange | suspected_exchange | mixer | bridge
    method: str
    confidence: float
    hop_distance: int
    evidence: str
    # Per-asset totals into this wallet. `value_received_eth` is kept as the
    # NATIVE portion only, so an older consumer reads a real number rather than
    # an ETH/USDT sum that means nothing.
    value_received: dict = field(default_factory=dict)
    value_received_eth: float = 0.0
    # Per-asset value attributable to the SUSPECT that reached this wallet, and
    # what share of the wallet's observed inflow that represents. The gross
    # `value_received` above answers "what landed here"; these answer "how much of
    # it was the suspect's money", which is the question a court cares about.
    tainted_value_received: dict = field(default_factory=dict)
    tainted_inflow_fraction: dict = field(default_factory=dict)
    # False when we never pulled this wallet's own history - an exchange at the
    # boundary of the trace, typically - so the inflow fraction above is measured
    # against only the part of its inflow the trace happened to see.
    inflow_fully_observed: bool = False

    # The shortest route from the suspect wallet to this address, and the label
    # types crossed along it. Both are filled in after the walk, because a path
    # is only knowable once the graph is complete. scoring.compute_confidence
    # reads `path_risk_types` to apply the mixer and bridge penalties.
    path: list[str] = field(default_factory=list)
    path_risk_types: set[str] = field(default_factory=set)
    confidence_score: int = 0  # 0-100, from scoring.py
    confidence_breakdown: str = ""
    confidence_components: list[dict] = field(default_factory=list)
    # Which entity cluster this wallet belongs to. Filled in after the walk by
    # core.clustering, so one Binance wallet points at the one Binance cluster.
    cluster_id: str | None = None
    # Which chain this endpoint is on, and which graph node it is stored under.
    # A cross-chain trace reaches the same address on two chains, where they are
    # two DIFFERENT wallets, so the node id is chain-qualified for anything off
    # the chain the investigation started on. `address` stays the bare address
    # for display and for looking the wallet up on an explorer.
    chain: str = ""
    node_id: str = ""

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            # The graph node this attribution refers to. Differs from `address` once
            # a trace crosses a chain, because the same address on two chains is
            # two different wallets. Consumers that walk `edges` need this to match
            # up; matching on `address` alone silently fails to find any route.
            "node_id": self.node_id,
            "entity": self.entity,
            "entity_type": self.entity_type,
            "method": self.method,
            "confidence": round(self.confidence, 2),
            "confidence_score": self.confidence_score,
            "confidence_breakdown": self.confidence_breakdown,
            "confidence_components": self.confidence_components,
            "hop_distance": self.hop_distance,
            "evidence": self.evidence,
            "value_received": {k: round(v, 8) for k, v in self.value_received.items()},
            "value_received_display": format_assets(self.value_received),
            "value_received_eth": round(self.value_received_eth, 6),
            # The suspect-attributable share, which is the figure a lawful request
            # should quote. Empty when the taint pass did not run or attributed
            # nothing to this wallet - `summary.taint_computed` tells them apart.
            "tainted_value_received": {
                k: round(v, 8) for k, v in self.tainted_value_received.items()
            },
            "tainted_value_display": (
                format_assets(self.tainted_value_received)
                if self.tainted_value_received
                else None
            ),
            "tainted_inflow_fraction": self.tainted_inflow_fraction,
            "inflow_fully_observed": self.inflow_fully_observed,
            "path": self.path,
            "crossed": sorted(self.path_risk_types),
            "cluster_id": self.cluster_id,
            "chain": self.chain,
        }


@dataclass
class RiskFlag:
    """
    A wallet on the money trail that carries a risk of its own.

    Distinct from an Attribution: an attribution answers "whose wallet is this",
    a risk flag answers "what is wrong with this wallet being on the path". A
    mixer is both - the exchange search stops there, AND it is a red flag.
    """

    address: str
    entity: str
    risk_type: str  # mixer | bridge | scam | sanctioned
    severity: str  # critical | high | medium
    hop_distance: int
    on_primary_path: bool
    value_received: dict
    value_received_eth: float
    note: str

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "entity": self.entity,
            "risk_type": self.risk_type,
            "severity": self.severity,
            "hop_distance": self.hop_distance,
            "on_primary_path": self.on_primary_path,
            "value_received": {k: round(v, 8) for k, v in self.value_received.items()},
            "value_received_display": format_assets(self.value_received),
            "value_received_eth": round(self.value_received_eth, 6),
            "note": self.note,
        }


@dataclass
class TraceResult:
    """
    What a trace produced: the money-flow graph, the hops, and the attributions.

    Unpacks like a tuple (`graph, hops = await trace(addr)`) and also carries the
    run statistics the UI shows and that tell us whether the caps were hit.
    """

    graph: nx.DiGraph
    hops: list[Hop]
    start_address: str
    max_depth: int
    dust_threshold: float
    attributions: list[Attribution] = field(default_factory=list)
    risk_flags: list[RiskFlag] = field(default_factory=list)
    truncated: bool = False  # a cap stopped the walk early
    notes: list[str] = field(default_factory=list)
    api_calls: int = 0
    cache_hits: int = 0
    elapsed_sec: float = 0.0
    backend: str = "memory"  # which graph store served this trace

    # Why the walk stopped where it did, and what we could not follow. Both
    # exist so that a trace which finds nothing still tells the investigator
    # something they can act on, instead of an empty graph and no explanation.
    termination: dict = field(default_factory=dict)
    token_warnings: dict = field(default_factory=dict)

    # Which network this trace ran on. Every consumer (panel, PDF, explorer
    # links) needs it, so it travels with the result rather than being inferred.
    chain: dict = field(default_factory=dict)

    # Entity clusters: the wallets of one business collapsed into one object,
    # which is what a lawful request is actually served against.
    clusters: list = field(default_factory=list)

    # The FIFO taint pass. None when it could not run (no transfers fetched), in
    # which case every consumer must fall back to connectivity-only wording.
    taint: object | None = None

    # Matched laundering typologies - peel chains, layering, structuring and so
    # on. Kept separate from `risk_flags`: a risk flag says WHAT a wallet is (a
    # mixer, a sanctioned address), a typology says what the MOVEMENT looks like.
    # Conflating them would let a pattern inference borrow the authority of a
    # published label.
    typologies: list = field(default_factory=list)
    # How many further matches the reporting cap held back, so a capped list is
    # never mistaken for a complete one.
    typologies_suppressed: int = 0

    # --- Cross-chain ---------------------------------------------------------
    # One entry per bridge deposit the tracer tried to carry across, in the order
    # it tried them. Includes the ones that failed: a handoff we declined to make
    # is evidence of where the trail goes cold, and hiding it would make a stop
    # look like it was the end of the road rather than a judgement we made.
    cross_chain_handoffs: list = field(default_factory=list)
    # Taint replay per chain, keyed by slug. `taint` above stays the chain the
    # investigation started on, so nothing existing has to change; a figure from
    # the destination chain is looked up here instead of summed into it.
    taint_chains: dict = field(default_factory=dict)
    # Which chains this trace actually read, and whether each has labels. Without
    # labels, identification cannot fire on a chain - so "no exchange found" there
    # means "we would not have recognised one", which is a different statement and
    # has to be reported as such rather than looking like an absence of activity.
    chains_traced: list = field(default_factory=list)
    label_coverage: dict = field(default_factory=dict)

    def __iter__(self):
        """So `graph, hops = result` works, as the engine's contract promises."""
        return iter((self.graph, self.hops))

    @property
    def exchanges(self) -> list[Attribution]:
        """Attributions that are actually actionable - a VASP that can be served."""
        return [
            a for a in self.attributions
            if a.entity_type in ("exchange", "suspected_exchange")
        ]

    @property
    def flags(self) -> list[Attribution]:
        """Obfuscation encountered on the way: mixers and cross-chain bridges."""
        return [a for a in self.attributions if a.entity_type in ("mixer", "bridge")]


def _mark_node(store, address: str, ident: identify.Identification) -> None:
    """Write an identification onto the wallet so the frontend can style and label it."""
    store.update_wallet(
        address,
        label=ident.entity,
        entity_type=ident.entity_type,
        method=ident.method,
        confidence=ident.confidence,
        is_vasp=ident.entity_type in ("exchange", "suspected_exchange"),
        is_mixer=ident.entity_type == "mixer",
        is_bridge=ident.entity_type == "bridge",
    )


def _native_total(totals: dict[str, float], chain: dict | None) -> float:
    """The native-token portion of a per-asset total, for the legacy scalar field."""
    symbol = (chain or {}).get("native", "ETH")
    return float(totals.get(symbol, totals.get("ETH", 0.0)))


def _value_received(store, address: str) -> dict[str, float]:
    """
    Per-asset totals that reached this address along traced edges.

    Returns {symbol: amount}. Deliberately not a single number: with several
    assets in play a scalar total would have no unit and no meaning.
    """
    totals: dict[str, float] = {}
    for edge in store.incoming(address):
        for symbol, entry in (edge.get("assets") or {}).items():
            totals[symbol] = totals.get(symbol, 0.0) + entry.get("value", 0.0)
    return totals


def _node_id(address: str, slug: str, primary_slug: str) -> str:
    """
    The graph key for a wallet on a chain.

    On the chain the investigation started on this is just the address, so every
    existing payload, recording and frontend lookup keeps working unchanged. On
    any other chain it is `chain:address`, because the same 20-byte address on
    two chains is two DIFFERENT wallets with two different balances and two
    different counterparties - and merging them would produce a graph that looks
    connected while describing nothing real.

    Addresses never contain a colon, so the prefix is unambiguous to split off.
    """
    if not slug or slug == primary_slug:
        return address
    return f"{slug}:{address}"


def _bare_address(node: str) -> str:
    """The wallet address behind a graph key, for display and explorer lookups."""
    return node.split(":", 1)[1] if ":" in node else node


@dataclass
class _WalkContext:
    """
    Everything a walk needs to carry across more than one chain.

    WHY THIS EXISTS. A trace that stops at a bridge used to be a single BFS over
    one chain. Following value across one means running a second BFS on a second
    chain and then combining two graphs, two taint replays and two sets of
    attributions into one report. This holds all of it.

    The one rule that keeps the combined result honest: state is kept PER CHAIN
    wherever it is chain-specific. `fetched_by_chain` and `taint` are keyed by
    slug, because an Ethereum taint figure and an Arbitrum taint figure measure
    different ledgers and must never be added together into one number.
    """

    store: object
    client: EtherscanClient
    max_depth: int
    dust_threshold: float
    primary_slug: str

    hops: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    # node_id -> Attribution. Keyed by node, not address: the same address on two
    # chains is two wallets and gets two entries.
    attributions: dict = field(default_factory=dict)
    stopped_at: dict = field(default_factory=dict)
    expanded: set = field(default_factory=set)

    # slug -> {address: [Transfer]}. Both directions per wallet, for taint.
    fetched_by_chain: dict = field(default_factory=dict)
    # slug -> [Seed]. Taint arriving over a bridge, injected before that chain's
    # replay. See core/taint.py Seed.
    seeds: dict = field(default_factory=dict)
    # slug -> TaintResult, one replay per chain.
    taint: dict = field(default_factory=dict)

    handoffs: list = field(default_factory=list)
    chains_traced: list = field(default_factory=list)
    suspect: str = ""
    cross_chain_hops: int = 0
    truncated: bool = False
    depth_capped: int = 0
    start_had_no_transfers: bool = False
    start_had_only_dust: bool = False

    def node(self, address: str, slug: str) -> str:
        return _node_id(address, slug, self.primary_slug)

    def chain_fetched(self, slug: str) -> dict:
        """The per-wallet transfer history for one chain, created on first use."""
        if slug not in self.chains_traced:
            self.chains_traced.append(slug)
        return self.fetched_by_chain.setdefault(slug, {})

    def record(
        self,
        node: str,
        address: str,
        slug: str,
        ident: "identify.Identification",
        depth: int,
    ) -> None:
        """Mark the wallet and log the attribution, keeping the shortest hop distance."""
        _mark_node(self.store, node, ident)
        if node in self.attributions:
            return
        self.attributions[node] = Attribution(
            address=address,
            entity=ident.entity,
            entity_type=ident.entity_type,
            method=ident.method,
            confidence=ident.confidence,
            hop_distance=depth,
            evidence=ident.evidence,
            chain=slug,
            node_id=node,
        )

    def taint_for(self, slug: str) -> object | None:
        """
        The FIFO replay for one chain, computed on first ask and cached.

        Seeded with the suspect's own address on the chain the investigation STARTED on,
        and with no unconditional source on every other chain. That asymmetry is
        deliberate. On the starting chain the rule "everything the suspect's wallet
        sends is tainted" is the premise of the whole investigation. On a
        destination chain the suspect's address is precisely the wallet the money
        arrived in, so applying that rule there would assert the suspect's funds on
        that chain with no bridge evidence at all, and at full value rather than
        net of the fee. So the only taint a destination chain can have is what a
        matched handoff explicitly seeded into it.
        """
        if slug in self.taint:
            return self.taint[slug]
        fetched = self.fetched_by_chain.get(slug) or {}
        if not fetched:
            return None
        is_primary = slug == self.primary_slug
        result = taint_engine.compute_taint(
            fetched,
            self.suspect,
            chain=slug,
            seeds=self.seeds.get(slug, ()),
            taint_source=self.suspect if is_primary else "",
        )
        self.taint[slug] = result
        return result

    def label_coverage(self) -> dict:
        """
        Per chain: how many labels we hold, and what that means for identification.

        Without labels a chain cannot yield an exchange finding, and "no exchange
        found" there means "we would not have recognised one" rather than "there
        was no exchange". Those are completely different statements and the report
        has to be able to tell them apart.
        """
        out = {}
        floor = config.MIN_LABELS_FOR_COVERAGE
        for slug in self.chains_traced:
            count = identify.label_count(chain=slug)
            # SPARSE IS TREATED AS NONE. A handful of labels on a chain is not
            # coverage: the chance that a trace reaches one of those exact wallets
            # is negligible, so "no exchange found" there means the same thing it
            # means with zero labels.
            covered = count >= floor
            if covered:
                note = None
            elif count == 0:
                note = (
                    f"No labels are held for {slug}, so an exchange reached on that "
                    "chain could not be recognised by name. A trace that finds nothing "
                    "there has not established that no exchange was involved."
                )
            else:
                note = (
                    f"Only {count} label{'s are' if count != 1 else ' is'} held for {slug}, "
                    f"fewer than the {floor} treated as coverage, so an exchange reached on "
                    "that chain would very likely not be recognised by name. A trace that "
                    "finds nothing there has not established that no exchange was involved."
                )
            out[slug] = {
                "labels": count,
                "coverage": "adequate" if covered else ("sparse" if count else "none"),
                "identification_possible": covered,
                "min_labels_for_coverage": floor,
                "note": note,
            }
        return out


async def _walk_leg(
    ctx: _WalkContext,
    chain: dict,
    start_address: str,
    start_depth: int,
    depth_budget: int,
    is_start: bool = False,
) -> None:
    """
    Walk forward from one wallet on one chain, breadth-first.

    Extracted so the cross-chain logic can run the identical walk on a second
    chain and have both lands in one graph. Every parameter that differs between
    a first leg and a later one is explicit: which chain, where to start, how deep
    it may go, and whether this wallet is the suspect.

    `depth_budget` is the REMAINING depth, not a fresh allowance. The crossing
    itself costs a hop, so a deposit found at depth 2 leaves two hops on the other
    side, and the hop count the report prints stays a true distance from the
    suspect rather than resetting at every chain boundary.
    """
    slug = chain["slug"]
    start_node = ctx.node(start_address, slug)
    fetched = ctx.chain_fetched(slug)
    queue: deque[tuple[str, int]] = deque([(start_node, start_depth)])

    ctx.store.add_wallet(
        start_node, depth=start_depth, is_start=is_start, chain=slug
    )

    # The leg's own starting wallet gets its label lookup immediately. On a first
    # leg this is the suspect, and being a known entity is worth saying even though
    # we expand it anyway.
    start_ident = identify.known_label_lookup(start_address, chain=slug)
    if start_ident is not None:
        ctx.record(start_node, start_address, slug, start_ident, start_depth)
        ctx.notes.append(
            f"The start address is itself a known entity ({start_ident.entity}); "
            f"tracing onward from it anyway."
        )

    while queue:
        node, depth = queue.popleft()
        address = _bare_address(node)

        if node in ctx.expanded:
            continue
        # Depth cap: this wallet is recorded in the graph, we just do not ask
        # where its money went next. This is the boundary of the trace.
        if depth >= depth_budget:
            ctx.depth_capped += 1
            continue
        if ctx.store.wallet_count() >= config.MAX_NODES_PER_TRACE:
            ctx.truncated = True
            ctx.notes.append(
                f"Stopped expanding at {config.MAX_NODES_PER_TRACE} wallets "
                f"(MAX_NODES_PER_TRACE). The graph is partial."
            )
            break

        # Re-check before spending an API call. Fan-in may have matured since
        # this wallet was queued, and if it is now recognisable the branch is
        # already answered - expanding an exchange hot wallet would be both
        # pointless and ruinously expensive.
        if depth > start_depth:
            ident = identify.identify(address, ctx.store, chain=slug, node=node)
            if ident is not None:
                ctx.record(node, address, slug, ident, depth)
                if identify.is_terminal(ident):
                    ctx.stopped_at[ident.entity_type] = (
                        ctx.stopped_at.get(ident.entity_type, 0) + 1
                    )
                    continue

        ctx.expanded.add(node)

        try:
            # BOTH directions, in the same API calls the walk always made. The
            # walk itself uses only the outgoing half; the incoming half is what
            # lets the taint pass order each wallet's balance. Fetching it here
            # rather than in a second sweep is what keeps taint free.
            fetched_transfers = await ctx.client.get_wallet_transfers(
                address, chain_id=chain["chain_id"]
            )
            fetched[address] = fetched_transfers
            transfers = [t for t in fetched_transfers if t.from_addr == address]
        except Exception as exc:  # noqa: BLE001 - one bad wallet must not kill the trace
            if is_start and node == ctx.node(ctx.suspect, slug):
                # No data for the suspect wallet means there is nothing to show.
                raise
            ctx.notes.append(f"Could not fetch {address} on {slug}: {exc}")
            continue

        # Aggregate first, THEN pick the biggest branches. Ranking raw
        # transactions would let one counterparty paid in 50 small slices lose
        # to a single larger one-off, even though it received far more overall.
        flows = _aggregate_by_recipient(transfers, ctx.dust_threshold)
        ranked = sorted(flows.values(), key=_flow_rank, reverse=True)

        if node == ctx.node(ctx.suspect, slug) and not ranked:
            # Distinguishing "sent nothing" from "sent only dust" matters: the
            # first is a dead end, the second is a threshold the investigator
            # can lower and re-run.
            ctx.start_had_no_transfers = not transfers
            ctx.start_had_only_dust = bool(transfers)

        if len(ranked) > config.MAX_EDGES_PER_NODE:
            ctx.truncated = True
            ctx.notes.append(
                f"{address} sent to {len(ranked)} recipients; expanded the "
                f"{config.MAX_EDGES_PER_NODE} largest by value."
            )
            ranked = ranked[: config.MAX_EDGES_PER_NODE]

        child_depth = depth + 1
        for flow in ranked:
            to_addr = flow["to"]
            child_node = ctx.node(to_addr, slug)

            if not ctx.store.has(child_node):
                ctx.store.add_wallet(
                    child_node, depth=child_depth, is_start=False, chain=slug
                )

            assets = {
                symbol: {k: v for k, v in entry.items() if not k.startswith("_")}
                for symbol, entry in flow["assets"].items()
            }
            primary = _primary_asset(flow["assets"]) or {}

            ctx.store.add_transfer(
                node,
                child_node,
                # Per-asset detail is the truth; the scalar fields below describe
                # the edge's PRIMARY asset only, for callers that need one number.
                assets=assets,
                value=primary.get("value", 0.0),
                asset=primary.get("asset", ""),
                tx_count=flow["tx_count"],
                timestamp=flow["timestamp"],
                tx_hash=primary.get("tx_hash", ""),
                depth=child_depth,
                chain=slug,
                edge_type="transfer",
            )

            # One hop row per asset moved: an ETH hop and a USDT hop between the
            # same pair are two different facts an investigator may cite.
            for entry in assets.values():
                ctx.hops.append(
                    Hop(
                        depth=child_depth,
                        from_addr=address,
                        to_addr=to_addr,
                        value=entry["value"],
                        asset=entry["asset"],
                        contract=entry.get("contract"),
                        tx_count=entry["tx_count"],
                        timestamp=entry["timestamp"],
                        tx_hash=entry["tx_hash"],
                        chain=slug,
                    )
                )

            # Label lookup the moment the wallet is discovered - it needs only
            # the address, so there is no reason to wait.
            child_ident = identify.known_label_lookup(to_addr, chain=slug)
            if child_ident is not None:
                ctx.record(child_node, to_addr, slug, child_ident, child_depth)
                if identify.is_terminal(child_ident):
                    ctx.stopped_at[child_ident.entity_type] = (
                        ctx.stopped_at.get(child_ident.entity_type, 0) + 1
                    )
                    # Branch complete: we found where this money came to rest.
                    continue

            if child_node not in ctx.expanded and child_depth < depth_budget:
                queue.append((child_node, child_depth))

    # Final consolidation sweep for this leg. Fan-in is only fully known once the
    # walk is over, so a wallet where several branches converged may become
    # recognisable here even though it looked ordinary every time we saw it
    # mid-walk. Scoped to the leg's own chain: fan-in measured on a merged
    # multi-chain graph would credit a wallet with senders it never had.
    for node, data in ctx.store.wallets():
        if data.get("chain") != slug:
            continue
        if node in ctx.attributions or (is_start and node == start_node):
            continue
        late = identify.consolidation_identify(
            _bare_address(node), ctx.store, node=node
        )  # chain-agnostic
        if late is not None:
            ctx.record(
                node, _bare_address(node), slug, late, data.get("depth", 0)
            )
            ctx.notes.append(
                f"{_bare_address(node)} was identified as a consolidation point only "
                f"after the {slug} walk completed; its onward transfers were still "
                f"followed."
            )


async def _follow_bridges(
    ctx: _WalkContext, chain: dict, suspect: str, depth_budget: int
) -> None:
    """
    Try to carry value across every bridge this chain's walk deposited into.

    Runs once per chain, after that chain's walk and its taint replay, because a
    handoff needs both: the deposit is an observation from the walk, and the share
    of it that was the suspect's money comes from the FIFO replay.

    EACH FAILURE IS RECORDED, NOT DROPPED. A bridge we declined to follow is
    evidence about where the trail goes cold. If the only outcomes the report can
    show are successful crossings, then a trace that stopped at a bridge looks
    exactly like a trace that never met one, and an investigator cannot tell
    whether we tried and declined or never looked.
    """
    slug = chain["slug"]

    # Deposits are INDIVIDUAL TRANSFERS to a bridge we hold a route for - not
    # hops. A hop is an aggregate: one real wallet made 38 separate deposits to
    # the Polygon bridge, and its hop carried their 184 ETH sum, the latest
    # timestamp and the largest hash. No credit on the destination chain can equal
    # a sum of 38 deposits, so matching the hop guaranteed a false "no match". A
    # bridge credits each deposit separately, so each deposit is matched on its
    # own amount and its own time.
    deposits: list[tuple[Hop, object]] = []
    # Tagged as a bridge, but no verified route on file. Collected separately so
    # the gap gets reported: a trail that goes cold at a bridge we do not know is
    # a data gap on our side, and saying nothing about it would read as "nothing
    # to follow here".
    unregistered: dict[str, Hop] = {}
    fetched = ctx.fetched_by_chain.get(slug) or {}
    for hop in ctx.hops:
        if hop.chain != slug or hop.edge_type != "transfer":
            continue
        if bridges.lookup(slug, hop.to_addr) is None:
            # The store is keyed by NODE ID, which is the bare address on the chain
            # the investigation started on and "<chain>:<address>" everywhere else.
            # A Hop records plain addresses, so off the starting chain a lookup by
            # hop.to_addr finds nothing and is_bridge would read False for every
            # destination-chain wallet - which would silently suppress the
            # unregistered-bridge report on exactly the legs where the trail goes
            # cold. Keyed by node id here, so one wallet is judged the same way on
            # every chain.
            _flags = ctx.store.wallet(ctx.node(hop.to_addr, slug))
            if _flags.get("is_bridge"):
                unregistered.setdefault(hop.to_addr, hop)
            continue
        floor = config.dust_threshold_for(hop.asset, ctx.dust_threshold)
        for transfer in fetched.get(hop.from_addr, ()):
            if (
                transfer.from_addr == hop.from_addr
                and transfer.to_addr == hop.to_addr
                and transfer.asset == hop.asset
                and transfer.value >= floor
            ):
                deposits.append((hop, transfer))

    for bridge_addr, hop in sorted(
        unregistered.items(), key=lambda kv: (-kv[1].value, kv[0])
    ):
        handoff = bridges.unmatched(slug, bridge_addr)
        ctx.handoffs.append(handoff)
        ctx.notes.append(
            f"{bridge_addr} is labelled a bridge on {slug} but is not followed: "
            + (
                "it is a recognised but unsupported route."
                if handoff.status == "unsupported"
                else "we hold no verified route for it."
            )
        )

    # WHICH DEPOSITS TO ATTEMPT. Each attempt costs a destination-chain walk, so
    # the count is capped - and the ones carrying the suspect's money go first.
    # Ranking by size alone would spend the budget on a large deposit that FIFO
    # says carried none of the suspect's funds, and skip the one that did.
    leg = ctx.taint_for(slug)

    def _deposit_taint(item) -> float:
        hop, transfer = item
        if leg is None:
            return 0.0
        return leg.transfer(transfer.hash, transfer.from_addr, transfer.to_addr, transfer.asset) or 0.0

    ranked = sorted(
        deposits,
        key=lambda item: (-_deposit_taint(item), -item[1].value, item[1].hash),
    )
    if len(ranked) > config.BRIDGE_MAX_DEPOSITS_PER_CHAIN:
        ctx.notes.append(
            f"{len(ranked)} individual bridge deposits were found on {slug}; "
            f"attempted the {config.BRIDGE_MAX_DEPOSITS_PER_CHAIN} carrying the most "
            "suspect-attributable value (then the largest). The others were not "
            "matched, so this is not a complete account of what crossed."
        )
        ranked = ranked[: config.BRIDGE_MAX_DEPOSITS_PER_CHAIN]

    for hop, transfer in ranked:
        spec = bridges.lookup(slug, hop.to_addr)
        if spec is None:
            # Tagged as a bridge but we hold no verified route for it. A real
            # state, and a gap in our data rather than in the money.
            ctx.handoffs.append(bridges.unmatched(slug, hop.to_addr))
            continue

        dest_slug = spec["to_chain"]
        dest_chain = config.chain_by_slug(dest_slug)
        deposit = bridges.Deposit(
            wallet=hop.from_addr,
            bridge=hop.to_addr,
            chain=slug,
            to_chain=dest_slug,
            entity=spec["entity"],
            asset=transfer.asset,
            dest_asset=bridges.dest_asset_for(spec, transfer.asset),
            value=transfer.value,
            timestamp=transfer.timestamp,
            tx_hash=transfer.hash,
        )

        if ctx.cross_chain_hops >= config.MAX_CROSS_CHAIN_HOPS:
            ctx.handoffs.append(
                bridges.hop_cap_reached(
                    ctx.cross_chain_hops, config.MAX_CROSS_CHAIN_HOPS, deposit
                )
            )
            continue

        if dest_chain is None:
            # We know the route but cannot read where it leads. Said plainly, so
            # this is not mistaken for money that stopped moving.
            ctx.handoffs.append(bridges.destination_unavailable(dest_slug, deposit))
            continue

        # The destination chain's view of this wallet: both directions, which is
        # also what the destination leg's taint replay needs, so this is not an
        # extra call the leg would have made anyway.
        try:
            dest_transfers = await ctx.client.get_wallet_transfers(
                hop.from_addr, chain_id=dest_chain["chain_id"]
            )
        except Exception as exc:  # noqa: BLE001 - one unreachable chain is not fatal
            ctx.notes.append(
                f"Could not read {dest_slug} history for {hop.from_addr} "
                f"(needed to match the {spec['entity']} deposit): {exc}"
            )
            ctx.handoffs.append(bridges.destination_unavailable(dest_slug, deposit))
            continue

        ctx.chain_fetched(dest_slug)[hop.from_addr] = dest_transfers

        candidates = bridges.match_candidates(deposit, dest_transfers, spec)
        match = bridges.resolve(candidates, deposit, spec)
        ctx.handoffs.append(match)

        if not match.matched:
            # ambiguous, no_match: we stop here on purpose. The reason and the
            # full candidate list travel in the payload so the decision is visible
            # and a reviewer can disagree with it.
            continue

        credit = match.chosen
        carried = _carried_taint(ctx, deposit, credit)
        # Set on the handoff itself so the report can state how much of the crossed
        # value is the suspect's, rather than only that a crossing happened.
        match.tainted_value = carried

        # Seed the destination chain's replay with the tainted share that actually
        # arrived. Scaled by the credit/deposit ratio, so a bridge fee reduces taint
        # rather than taint being conjured out of the difference.
        if carried > 0:
            # A new seed invalidates any replay already computed for that chain.
            # The replay is cached per chain, and a second matched deposit into the
            # same destination would otherwise add its seed AFTER the replay ran -
            # silently dropping that crossing's taint and leaving the second leg's
            # figures computed before its transfers were even fetched.
            ctx.taint.pop(dest_slug, None)
            ctx.seeds.setdefault(dest_slug, []).append(
                taint_engine.Seed(
                    address=hop.from_addr,
                    asset=credit.asset,
                    value=carried,
                    timestamp=credit.timestamp,
                    confidence=match.chosen.score / 100.0,
                    origin="bridge",
                    note=(
                        f"{carried:.8g} {credit.asset} attributed to the suspect "
                        f"across {spec['entity']} to {dest_slug}"
                    ),
                )
            )

        # The crossing, as its own node and its own kind of edge. It runs from the
        # bridge (last node on the source chain) to the same address on the
        # destination chain, which is where the money actually reappears.
        child_node = ctx.node(hop.from_addr, dest_slug)
        crossing_depth = hop.depth + 1
        if not ctx.store.has(child_node):
            ctx.store.add_wallet(
                child_node, depth=crossing_depth, is_start=False, chain=dest_slug
            )
        ctx.store.add_transfer(
            hop.to_addr,
            child_node,
            assets={
                credit.asset: {
                    "asset": credit.asset,
                    "value": credit.value,
                    "contract": None,
                    "tx_count": 1,
                    "timestamp": credit.timestamp,
                    "tx_hash": credit.tx_hash,
                }
            },
            value=credit.value,
            asset=credit.asset,
            tx_count=1,
            timestamp=credit.timestamp,
            tx_hash=credit.tx_hash,
            depth=crossing_depth,
            chain=dest_slug,
            edge_type="cross_chain",
            from_chain=slug,
            to_chain=dest_slug,
            # On the graph edge as well as on the Hop. The two are read by
            # different consumers - the graph view from the edge, the path view
            # from the Hop - and a figure that exists in only one of them would
            # let the graph and the report disagree about how much of the money
            # was the suspect's.
            tainted_value=carried,
            assumed_pre_existing=max(0.0, float(credit.value) - carried),
            # The evidence travels on the graph edge too. The graph view, the path
            # view and the PDF each read a different object, and a crossing that
            # shows up bare in one of them would present an inferred arrival as if
            # it were an observed transfer.
            handoff=match,
        )
        ctx.hops.append(
            Hop(
                depth=crossing_depth,
                from_addr=hop.to_addr,
                to_addr=hop.from_addr,
                value=credit.value,
                asset=credit.asset,
                tx_count=1,
                timestamp=credit.timestamp,
                tx_hash=credit.tx_hash,
                chain=dest_slug,
                edge_type="cross_chain",
                handoff=match,
                # Set here, from the handoff, rather than left for the per-hop taint
                # pass: there is no transfer on this edge for a FIFO replay to find,
                # because the value crossed a chain boundary rather than moving
                # between two wallets. The figure is the tainted share that
                # actually arrived.
                tainted_value=carried,
                assumed_pre_existing=max(0.0, float(credit.value) - carried),
            )
        )
        ctx.cross_chain_hops += 1

        # Keep going on the other side, from the matched withdrawal, with whatever
        # depth the crossing has left.
        await _walk_leg(
            ctx,
            dest_chain,
            hop.from_addr,
            start_depth=crossing_depth,
            depth_budget=depth_budget,
        )

        # Now replay THIS chain's own taint, seeded with what crossed. It has to
        # happen after the walk, because the walk is what supplies the transfers -
        # and before recursing, because the next handoff needs the tainted share of
        # any deposit made from this chain.
        ctx.taint_for(dest_slug)

        # And from there, look for further crossings, up to the cap.
        await _follow_bridges(ctx, dest_chain, suspect, depth_budget)


def _carried_taint(ctx: _WalkContext, deposit, credit) -> float:
    """
    How much of the suspect's money to credit on the other side of this bridge.

    The tainted share of the deposit, scaled by how much of the deposit actually
    arrived. Two reasons it cannot simply be the deposit's tainted value:

      a bridge takes a fee, so the credit is smaller than the deposit, and
        crediting the full amount would let taint grow across a crossing;
      the credit is itself an INFERENCE. Scaling it keeps the destination chain's
        figures no stronger than the evidence that produced them.

    Returns 0.0 when the source chain's taint has not been computed, which is the
    honest answer: we cannot say how much of that deposit was the suspect's money,
    so we credit none of it and say so rather than assuming all of it.
    """
    leg = ctx.taint_for(deposit.chain)
    if leg is None or deposit.value <= 0:
        return 0.0
    # THIS deposit's tainted share, from the replay's per-transfer ledger - not the
    # edge total, which sums every deposit the wallet ever made to the bridge.
    deposit_tainted = leg.transfer(
        deposit.tx_hash, deposit.wallet, deposit.bridge, deposit.asset
    )
    if deposit_tainted is None:
        return 0.0
    deposit_tainted = min(deposit_tainted, deposit.value)
    carried = deposit_tainted * (float(credit.value) / float(deposit.value))
    # Never credit more taint than value actually landed.
    return max(0.0, min(carried, float(credit.value)))


async def trace(
    start_address: str,
    max_depth: int = 4,
    dust_threshold: float = 0.001,
    client: EtherscanClient | None = None,
    chain_id: int | None = None,
) -> TraceResult:
    """
    Walk the money forward from `start_address` until it reaches a known entity.

    Breadth-first, not depth-first, and that choice is deliberate: BFS visits
    wallets in order of hop distance, so the first time we reach any wallet we
    have reached it by the SHORTEST path. When the result says "the funds
    reached Binance 3 hops away", BFS is what makes that number true rather than
    an artefact of traversal order.

    Identification runs at two moments, for a reason. A label lookup happens the
    instant a wallet is discovered, since it depends only on the address. The
    consolidation heuristic is re-checked when a wallet is about to be expanded,
    and once more after the walk finishes, because fan-in is a property of the
    graph and the graph is still growing - a wallet that looks ordinary when
    first seen may turn out to be where six separate branches converge.

    Args:
        start_address: the suspect wallet the investigator was given.
        max_depth: how many hops forward to follow. See the fan-out note above.
        dust_threshold: ignore transfers below this many ETH.
        client: injectable Etherscan client, for tests and replay mode.

    Returns:
        TraceResult - `.graph`, `.hops`, and `.attributions` (recognised
        endpoints, nearest first). Confidence is never 1.0.

    Raises:
        ValueError: the start address is not a well-formed Ethereum address.
        EtherscanError: the very first fetch failed, so there is no trace at all.
    """
    started_at = time.monotonic()
    client = client or get_client()
    client.reset_stats()

    # Resolved here so an unsupported chain raises before we spend an API call,
    # and so every downstream fetch and label lookup uses the same chain.
    chain = config.chain(chain_id)

    start = normalize_address(start_address)
    if len(start) != 42 or not start.startswith("0x"):
        raise ValueError(f"Not a valid Ethereum address: {start_address!r}")

    ctx = _WalkContext(
        store=graph_store.get_store(),
        client=client,
        max_depth=max_depth,
        dust_threshold=dust_threshold,
        primary_slug=chain["slug"],
    )
    # Local aliases so the post-processing below reads as it always has. The
    # context exists to carry state across a second chain leg, not to re-indent
    # the code that does the reporting.
    store = ctx.store
    hops = ctx.hops
    notes = ctx.notes
    attributions = ctx.attributions

    ctx.suspect = start
    # The suspect wallet itself is depth 0. If the start address is ITSELF a known
    # entity that is still worth reporting - and we still expand it, because
    # stopping at depth 0 would return an empty graph and say nothing about where
    # the money went.
    await _walk_leg(ctx, chain, start, start_depth=0, depth_budget=max_depth, is_start=True)

    # --- CROSS-CHAIN HANDOFF -----------------------------------------------
    # Runs after this chain's walk, because a handoff needs two things the walk
    # produces: a deposit observed on this chain, and that deposit's taint share,
    # which is only known once the FIFO replay for this chain has run.
    #
    # Taint for the primary chain is therefore computed HERE, before the
    # destination leg, rather than once at the end. Each chain gets its own
    # replay and they are never summed: an Ethereum figure and an Arbitrum figure
    # are measurements of different ledgers, and adding them would invent a
    # number that corresponds to nothing.
    taint = ctx.taint_for(chain["slug"])
    await _follow_bridges(ctx, chain, start, depth_budget=max_depth)

    # FINALISE every chain's replay now that all crossings are known. A seed that
    # arrived late (a second deposit into a chain already replayed, or a round
    # trip back onto the starting chain) dropped that chain's cached replay, and
    # the figures below must come from a replay that saw every seed and every
    # transfer - not from whichever one happened to run first.
    for traced_slug in list(ctx.chains_traced):
        ctx.taint_for(traced_slug)
    taint = ctx.taint.get(chain["slug"])

    # The destination legs may have run out of depth or hit a cap of their own,
    # and the termination explanation below has to account for that too.
    truncated = ctx.truncated
    depth_capped = ctx.depth_capped
    stopped_at = ctx.stopped_at
    start_had_no_transfers = ctx.start_had_no_transfers
    start_had_only_dust = ctx.start_had_only_dust
    fetched = ctx.chain_fetched(chain["slug"])

    # VALUE-LEVEL TAINT for every chain this trace touched. `taint` stays the
    # primary chain's replay, because every existing consumer - and every existing
    # payload field - means "the chain the investigation started on".
    for attribution in attributions.values():
        leg_taint = ctx.taint.get(attribution.chain)
        node = attribution.node_id or attribution.address

        # Gross: what reached this wallet along traced edges.
        totals = _value_received(store, node)
        attribution.value_received = totals
        attribution.value_received_eth = _native_total(totals, chain)
        if leg_taint is not None:
            attribution.tainted_value_received = leg_taint.tainted_into(attribution.address)
            attribution.tainted_inflow_fraction = leg_taint.inflow_fractions(
                attribution.address
            )
            attribution.inflow_fully_observed = leg_taint.fully_observed(
                attribution.address
            )

    # Per-hop taint, so an investigator can see which leg of the route carried the
    # suspect's money and which merely existed. A bridge crossing gets its figure
    # from the chain it arrived on, since that is the ledger that holds the value.
    for hop in hops:
        if hop.edge_type == "cross_chain":
            # Already filled from the handoff when the crossing was made: there is
            # no transfer on this edge to replay, so recomputing here would erase
            # the only tainted figure the crossing has.
            continue
        leg_taint = ctx.taint.get(hop.chain)
        if leg_taint is None:
            continue
        flow = leg_taint.edge(hop.from_addr, hop.to_addr, hop.asset)
        if flow is None:
            continue
        # The hop's value is the dust-filtered, aggregated total for this
        # edge; the taint pass replays every transfer including dust. Cap so a
        # hop can never claim more tainted value than it moved.
        hop.tainted_value = min(flow.tainted, hop.value)
        hop.assumed_pre_existing = min(flow.assumed_pre_existing, hop.value)

    # Reconstruct each attribution's route and score it. This has to happen
    # after the walk: a path is only knowable once the graph is complete, and
    # the score depends on what that path crossed.
    for attribution in attributions.values():
        attribution.path = store.shortest_path(start, attribution.node_id or attribution.address)
        attribution.path_risk_types = _risk_types_on_path(store, attribution.path)

        scored = scoring.compute_confidence(attribution)
        attribution.confidence_score = scored.score
        attribution.confidence_breakdown = scored.breakdown
        attribution.confidence_components = [c.to_dict() for c in scored.components]
        # Keep the 0-1 field in step so every existing consumer stays correct.
        attribution.confidence = scored.score / 100.0

    # Nearest first, then most confident: the closest exit point is the one an
    # investigator should act on.
    ordered = sorted(
        attributions.values(), key=lambda a: (a.hop_distance, -a.confidence)
    )

    risk_flags = _collect_risk_flags(store, start, ordered)

    # Entity resolution. Runs on finished attributions so it only aggregates -
    # each wallet keeps the hop distance and confidence it was given.
    clusters = clustering.build_clusters(store, ordered, chain=chain.get("slug"))
    index = clustering.cluster_index(clusters)
    for attribution in ordered:
        attribution.cluster_id = index.get(attribution.node_id or attribution.address)

    primary = _primary_attribution(ordered)
    termination = _classify_termination(
        found_exchange=any(a.entity_type == "exchange" for a in ordered),
        stopped_at=stopped_at,
        depth_capped=depth_capped,
        truncated=truncated,
        max_depth=max_depth,
        dust_threshold=dust_threshold,
        start_had_no_transfers=start_had_no_transfers,
        start_had_only_dust=start_had_only_dust,
        handoffs=ctx.handoffs,
        chain=chain,
    )

    # What we deliberately did not follow, reported so the gap is visible.
    # No extra API calls: the walk already fetched every wallet's token rows, so
    # what we declined to follow is known from data in hand.
    token_warnings = _unfollowed_token_note(client, chain["chain_id"])

    # LAUNDERING TYPOLOGIES. Pattern rules over the transfers already fetched -
    # no new API calls. Runs before the store closes because the detectors need
    # each wallet's entity type to exempt labelled businesses, without which an
    # exchange hot wallet would be reported as a structuring suspect.
    #
    # Deliberately the PRIMARY chain only. The detectors walk one ledger and read
    # taint keyed by bare address; running them over a merged multi-chain history
    # would silently conflate the same address on two chains. Rather than ship
    # that, the destination chain is reported as not analysed - which is the
    # honest statement, and the one the payload has to make anyway.
    matched_typologies, typologies_suppressed = typologies.detect(
        fetched, store, taint=taint, start=start
    )
    untraced_chains = [s for s in ctx.chains_traced if s != chain["slug"]]
    if untraced_chains:
        notes.append(
            "Laundering typologies were detected on "
            f"{chain['name']} only; {', '.join(untraced_chains)} was traced for "
            "money flow but its patterns were not analysed. No typology claim is "
            "made about those chains."
        )

    # Materialise a NetworkX view for serialisation and for everything that
    # already speaks DiGraph. With Neo4j this is one query at the end of the
    # walk, not a second traversal engine running alongside the first.
    graph = store.to_networkx()
    backend = store.backend
    store.close()

    return TraceResult(
        graph=graph,
        hops=hops,
        start_address=start,
        max_depth=max_depth,
        dust_threshold=dust_threshold,
        attributions=ordered,
        risk_flags=risk_flags,
        truncated=truncated,
        notes=notes,
        api_calls=client.api_calls,
        cache_hits=client.cache_hits,
        elapsed_sec=round(time.monotonic() - started_at, 2),
        backend=backend,
        termination=termination,
        token_warnings=token_warnings,
        chain=chain,
        clusters=clusters,
        taint=taint,
        typologies=matched_typologies,
        typologies_suppressed=typologies_suppressed,
        cross_chain_handoffs=ctx.handoffs,
        taint_chains=ctx.taint,
        chains_traced=list(ctx.chains_traced),
        label_coverage=ctx.label_coverage(),
    )


def _classify_termination(
    *,
    found_exchange: bool,
    stopped_at: dict[str, int],
    depth_capped: int,
    truncated: bool,
    max_depth: int,
    dust_threshold: float,
    start_had_no_transfers: bool,
    start_had_only_dust: bool,
    handoffs: list | None = None,
    chain: dict | None = None,
) -> dict:
    """
    Say WHY the walk stopped, in terms an investigator can act on.

    A trace that finds nothing used to return an empty graph and no explanation,
    which is indistinguishable from a broken tool. Each reason below implies a
    different next step - lower the threshold, raise the depth, accept that the
    trail is cut, or expand the label set - so the reason is the useful part.

    Ordered by what actually ended the search, most decisive first: a start
    wallet that never sent anything outranks a depth cap that was never reached.

    BRIDGES. A bridge used to end the trail with "outside what this tool covers".
    Since Phase 9 the tool tries to follow it, so the reason has to say what that
    attempt found: a crossing that was followed did not end the trail at all, and
    one that was ambiguous, unmatched or unsupported ended it for a specific,
    different reason. `handoffs` carries those outcomes; `chain` names the chain
    the trail left, which is not always Ethereum.
    """
    chain_name = (chain or {}).get("name") or "this chain"
    native = (chain or {}).get("native") or "ETH"
    handoffs = handoffs or []
    # Crossings that did NOT carry the trail onward. Only these can end it.
    stopped = [h for h in handoffs if getattr(h, "status", "") != "matched"]
    if start_had_no_transfers:
        return {
            "reason": "no_outgoing_transfers",
            "label": "The suspect wallet has no outgoing transfers",
            "detail": (
                "Nothing has left this wallet in the transactions we can see, so "
                "there is no trail to follow yet. The funds may still be sitting "
                "here."
            ),
        }
    if start_had_only_dust:
        return {
            "reason": "dust_only",
            "label": f"All outgoing transfers are below {dust_threshold} {native}",
            "detail": (
                "Everything leaving this wallet is smaller than the dust "
                f"threshold of {dust_threshold} {native}, so nothing was followed. "
                "Lower the threshold and re-run to include them."
            ),
        }
    if found_exchange:
        return {
            "reason": "exchange_reached",
            "label": "The trace stopped because it reached an exchange",
            "detail": "This is the intended endpoint: a regulated business that holds KYC records.",
        }
    if stopped_at.get("mixer"):
        n = stopped_at["mixer"]
        return {
            "reason": "terminated_at_mixer",
            "label": f"The trail ends at a mixer ({n} branch{'es' if n > 1 else ''})",
            "detail": (
                "A mixer deliberately breaks the link between the funds going in "
                "and coming out, so nothing beyond it can be followed on-chain. "
                "This is a hard stop, not a gap in our data."
            ),
        }
    # A bridge ends the trail only where its crossing was NOT followed. If every
    # bridge reached was crossed, the trail continued on the other side and the
    # reason it finally stopped is whatever stopped that leg (below).
    followed_all = bool(handoffs) and not stopped
    if stopped_at.get("bridge") and not followed_all:
        n = max(len(stopped), 1) if stopped else stopped_at["bridge"]
        phrases = {
            "ambiguous": "several withdrawals on the destination chain matched equally, so none was followed",
            "no_match": "no matching withdrawal was found on the destination chain within the bridge's time window",
            "unsupported": "it is a recognised bridge this tool deliberately does not follow",
            "not_registered": "we hold no verified route for this bridge",
            "hop_cap_reached": "the trace had already used its cross-chain crossings",
            "destination_unavailable": "the destination chain cannot be read with the configured API key",
        }
        counts: dict[str, int] = {}
        for h in stopped:
            counts[h.status] = counts.get(h.status, 0) + 1
        parts = [
            f"{count} because {phrases.get(status, status)}"
            if count > 1 or len(counts) > 1
            else phrases.get(status, status)
            for status, count in counts.items()
        ]
        detail = (
            "The funds were sent to a bridge, and the crossing was not followed: "
            + "; ".join(parts)
            + ". The money may continue on another chain; this trace makes no claim "
            "about where. See the cross-chain section for each attempt and its evidence."
            if parts
            else "The funds were sent to a bridge, and no crossing was attempted. The money "
            "may continue on another chain; this trace makes no claim about where."
        )
        return {
            "reason": "terminated_at_bridge",
            "label": (
                f"The trail leaves {chain_name} via a bridge and was not followed past it "
                f"({n} branch{'es' if n > 1 else ''})"
            ),
            "detail": detail,
        }
    if truncated:
        return {
            "reason": "graph_cap_reached",
            "label": "The trace hit its size limit before finding an exchange",
            "detail": (
                "The wallet fans out too widely to follow completely, so only "
                "the largest branches were expanded. The exchange may lie down "
                "a branch that was not taken."
            ),
        }
    if depth_capped:
        return {
            "reason": "depth_cap_reached",
            "label": f"The trace stopped at the {max_depth}-hop limit",
            "detail": (
                f"{depth_capped} wallet{'s' if depth_capped > 1 else ''} were "
                f"reached at {max_depth} hops and not expanded further. Raise the "
                "hop limit and re-run to follow them."
            ),
        }
    return {
        "reason": "no_labelled_entity",
        "label": "The money stopped moving before reaching anything we recognise",
        "detail": (
            "Every branch was followed to its end and none arrived at a known "
            "exchange, mixer or bridge. The funds may still be sitting in "
            "unhosted wallets, or the exchange may be missing from our label set."
        ),
    }


def _unfollowed_token_note(client, chain_id: int) -> dict:
    """
    What token movement we chose NOT to follow, and why.

    Phase 2 warned "this wallet has token transfers we do not follow" because the
    tracer followed native transfers only. That warning is now WRONG for
    allowlisted assets - USDT, USDC, DAI, WETH and WBTC are followed end to end.

    What remains true is narrower: transfers of tokens OUTSIDE the allowlist are
    still skipped, deliberately, to keep airdrop spam out of the graph. This
    reports exactly that, counted during the walk from data we already fetched -
    so it costs no extra API calls, where the old probe cost one per wallet.

    One entry needs reading carefully. Because the allowlist matches on contract
    address, a skipped token may claim the symbol of an asset we DO follow - a
    fake "USDT". That is not coverage we lack; it is an impostor the contract
    check caught, so it is flagged rather than left to look like a missed trail.
    """
    tally = dict(getattr(client, "skipped_tokens", {}) or {})
    # Only this chain's skips belong in this trace's note.
    skipped: dict[str, int] = {}
    for key, count in tally.items():
        row_chain, symbol = key if isinstance(key, tuple) else (chain_id, key)
        if row_chain == chain_id:
            skipped[symbol] = skipped.get(symbol, 0) + count
    total = sum(skipped.values())
    if not total:
        return {}

    top = sorted(skipped.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    impersonated = sorted(
        symbol
        for symbol in skipped
        if config.impersonates_followed_asset(chain_id, symbol)
    )
    native = config.chain(chain_id).get("native", "")
    followed = config.followed_assets(chain_id)

    def _skip_reason(symbol: str) -> str:
        """
        Why THIS symbol was not traced, in words a reader can act on.

        WHY THIS IS PER-ENTRY. The list is read as "assets the tool chose not
        to follow", so a bare "ETH (5)" implies the tool skipped Ethereum
        itself - which is never true; the native asset is always traced. The
        entry is a token CONTRACT calling itself ETH that is not the native
        asset, and a reader has no way to tell that from the row alone.
        Spelled out here, because a correct refusal that reads as a gap is
        worse than an incorrect one that announces itself.

        Three distinct reasons, kept apart because they warrant different
        amounts of trust:
          impersonator - claims a followed asset's ticker, is not its contract.
                         Caught by the allowlist; the trail here is a fake.
          native_name  - claims the chain's own gas-asset ticker, same idea.
          spam         - an ordinary non-allowlisted token, almost always airdrop
                         spam. Coverage limit, not a detection.
        """
        if config.impersonates_followed_asset(chain_id, symbol):
            return f"impersonates a followed asset, not the real contract"
        if native and symbol.upper() == native.upper():
            return f"not the {native} gas asset; a token calling itself {symbol}"
        if symbol.upper() in {a.upper() for a in followed}:
            return "uses a followed asset's ticker but is a different contract"
        return "not on the followed-asset allowlist (usually airdrop spam)"

    note = {
        "skipped_transfers": total,
        "distinct_tokens": len(skipped),
        "followed_assets": followed,
        "top_skipped": [
            {
                "asset": asset,
                "transfers": count,
                "impersonating": config.impersonates_followed_asset(chain_id, asset),
                # Paired with the reason so a consumer never has to infer why.
                "reason": _skip_reason(asset),
            }
            for asset, count in top
        ],
        "reason": (
            "Transfers of tokens outside the followed list were not traced. Most "
            "are airdrop spam, which would add wallets and edges without adding "
            "signal - but a genuine trail in one of these assets would not be "
            "followed either."
        ),
    }
    if impersonated:
        note["impersonated_symbols"] = impersonated
        note["impersonation_note"] = (
            "Some skipped tokens call themselves "
            + ", ".join(impersonated)
            + " but are not the real contract for that asset on this chain. They "
            "were refused for that reason, not overlooked."
        )
    return note


def _risk_types_on_path(store, path: list[str]) -> set[str]:
    """
    Which risky label types the money crossed on the way to the endpoint.

    The endpoint itself is excluded: we are scoring how trustworthy the route TO
    it is, and a mixer should not be penalised for being a mixer. Its own
    intermediate hops still count.
    """
    crossed: set[str] = set()
    for address in path[:-1]:
        entity_type = store.wallet(address).get("entity_type")
        if scoring.risk_severity(entity_type or "") is not None:
            crossed.add(entity_type)
    return crossed


def _primary_attribution(attributions: list[Attribution]) -> Attribution | None:
    """
    The one finding the report is actually about - the headline.

    NOT simply the first attribution. Attributions are ordered by hop distance,
    so a mixer one hop out sorts ahead of the exchange three hops out, but the
    exchange is the finding; the mixer is something the money passed on the way.
    Picking the wrong one here would make "on this path" contradict the path the
    panel draws, so this deliberately mirrors what summarize() reports: a named
    exchange first, an unconfirmed collection point only if there is no named
    one, and nothing at all if neither exists.
    """
    for wanted in ("exchange", "suspected_exchange"):
        for attribution in attributions:
            if attribution.entity_type == wanted:
                return attribution

    # No exchange anywhere: the trail ended at a mixer or a bridge. That IS the
    # story of this trace, so the nearest such endpoint becomes the primary
    # path - otherwise a mixer sitting directly on the money's route would be
    # reported as though it were off to one side.
    return attributions[0] if attributions else None


def _collect_risk_flags(store, start: str, attributions: list[Attribution]) -> list[RiskFlag]:
    """
    Every labelled wallet in the trace that is a risk in its own right.

    Covers mixers, bridges and - when such entries exist in labels.json - scam
    and sanctioned addresses. Each flag records whether it sits on the primary
    path (the route to the headline finding) or elsewhere in the graph, because
    a mixer on the actual trail means something quite different from one on a
    side branch the money never took.
    """
    primary = _primary_attribution(attributions)
    primary_path = set(primary.path) if primary is not None else set()

    flags: list[RiskFlag] = []
    for node, data in store.wallets():
        entity_type = data.get("entity_type")
        severity = scoring.risk_severity(entity_type or "")
        if severity is None:
            continue

        entity = data.get("label") or "Unknown entity"
        # Reported as the bare address even for a chain-qualified node: an
        # investigator looks this up on an explorer, and "arbitrum:0xabc" is not
        # something they can paste anywhere.
        address = _bare_address(node)
        totals = _value_received(store, node)
        flags.append(
            RiskFlag(
                address=address,
                entity=entity,
                risk_type=entity_type,
                severity=severity,
                hop_distance=data.get("depth", 0),
                on_primary_path=node in primary_path,
                value_received=totals,
                value_received_eth=_native_total(totals, None),
                note=scoring.risk_note(entity_type, entity),
            )
        )

    # Worst first, and within a severity the ones actually on the trail lead.
    order = {"critical": 0, "high": 1, "medium": 2}
    flags.sort(
        key=lambda f: (
            order.get(f.severity, 9),
            not f.on_primary_path,
            f.hop_distance,
        )
    )
    return flags


def _aggregate_by_recipient(
    transfers: list[Transfer], dust_threshold: float
) -> dict[str, dict]:
    """
    Collapse transactions into one flow per RECIPIENT AND ASSET.

    Per asset, not just per recipient: 5 ETH and 5,000 USDT are not 5,005 of
    anything. Summing across assets produces a number with no unit, which would
    then be used to rank branches and to report "value received" - both wrong.
    Each recipient therefore holds an `assets` map, and the totals stay separate
    all the way to the report.

    Dust is filtered per TRANSACTION and PER ASSET, before summing: a thousand
    0.0001 ETH spam sends are still spam even though they total 0.1 ETH, and a
    threshold meant for ETH says nothing about what counts as dust in USDT.
    """
    flows: dict[str, dict] = {}

    for t in transfers:
        if t.value < config.dust_threshold_for(t.asset, dust_threshold):
            continue

        flow = flows.setdefault(
            t.to_addr,
            {"to": t.to_addr, "assets": {}, "tx_count": 0, "timestamp": 0},
        )
        entry = flow["assets"].get(t.asset)
        if entry is None:
            flow["assets"][t.asset] = {
                "asset": t.asset,
                "contract": t.contract,
                "decimals": t.decimals,
                "value": t.value,
                "tx_count": 1,
                "timestamp": t.timestamp,
                "tx_hash": t.hash,
                "_max_value": t.value,
            }
        else:
            entry["value"] += t.value
            entry["tx_count"] += 1
            entry["timestamp"] = max(entry["timestamp"], t.timestamp)
            # Keep the largest single transaction of THAT asset as the citable
            # example - the one an investigator would look up first.
            if t.value > entry["_max_value"]:
                entry["_max_value"] = t.value
                entry["tx_hash"] = t.hash

        flow["tx_count"] += 1
        flow["timestamp"] = max(flow["timestamp"], t.timestamp)

    return flows


def _flow_rank(flow: dict) -> tuple:
    """
    How to order branches when we can only expand the biggest ones.

    Assets cannot be summed, and this build has no price feed, so there is no
    honest "total value". Ranking is therefore: native first (it is the asset the
    trace is denominated in), then the largest single-asset amount. Stated here
    because it decides which branches get followed at all.
    """
    native = max(
        (a["value"] for a in flow["assets"].values() if a["contract"] is None),
        default=0.0,
    )
    largest = max((a["value"] for a in flow["assets"].values()), default=0.0)
    return (native, largest)


def _primary_asset(assets: dict) -> dict | None:
    """The asset an edge is best described by: native if present, else largest."""
    if not assets:
        return None
    native = [a for a in assets.values() if a["contract"] is None]
    if native:
        return max(native, key=lambda a: a["value"])
    return max(assets.values(), key=lambda a: a["value"])


def format_assets(totals: dict[str, float], limit: int = 3) -> str:
    """
    Render per-asset totals as one readable string, e.g. "12.5 ETH + 40,000 USDT".

    Used wherever a single line has to stand in for several assets; the full
    breakdown always travels alongside it in the payload.
    """
    if not totals:
        return "0"
    ordered = sorted(totals.items(), key=lambda kv: -kv[1])
    parts = []
    for asset, amount in ordered[:limit]:
        if amount >= 1000:
            parts.append(f"{amount:,.0f} {asset}")
        elif amount >= 1:
            parts.append(f"{amount:,.2f} {asset}")
        else:
            parts.append(f"{amount:.4f} {asset}")
    if len(ordered) > limit:
        parts.append(f"+{len(ordered) - limit} more")
    return " + ".join(parts)


# The one-line caveat that travels with every positive finding. Short on purpose:
# a claim this load-bearing has to be qualified where it is made, not buried in a
# disclaimer nobody reads. We follow transaction paths, not individual coins - the
# tracer expands every large outgoing transfer of a wallet regardless of where
# that value came from, so a connected path is NOT proof the suspect's funds
# arrived. In the recorded demo 198 ETH enter a wallet that forwards 17,969 ETH.
# Three different things can be true of a finding, and they must not share one
# sentence. Which caveat a result carries is chosen per finding, in _caveat_for().
CONNECTIVITY_CAVEAT = (
    "Path connectivity, not value-level taint tracking: transfers link these "
    "wallets, which does not prove these specific funds arrived."
)

FIFO_CAVEAT = (
    "Amounts attributed to the suspect are computed by FIFO accounting: funds "
    "leave a wallet in the order they arrived. A different rule - last-in-"
    "first-out, or pro-rata pooling - would give different figures from the same "
    "transactions."
)

NO_TAINT_CAVEAT = (
    "Transfers link these wallets, but under FIFO accounting none of the value "
    "arriving here traces back to the suspect's funds - the wallets on the route "
    "moved other money in between, and on this accounting those are the coins "
    "that went on. The connection may still be worth pursuing; a different "
    "accounting rule would give a different answer."
)


def _caveat_for(result: TraceResult, attribution: Attribution | None) -> str:
    """
    The honest caveat for THIS finding.

    Phase 2 attached one connectivity caveat to everything, which was right when
    no taint was computed and is wrong now that it usually is. The three cases:

      * taint computed, value attributed  -> name the accounting rule (FIFO_CAVEAT)
      * taint computed, nothing attributed -> say so plainly (NO_TAINT_CAVEAT),
        because "a path connects" would otherwise imply money arrived
      * taint not computed at all          -> the original wording still applies
    """
    if result.taint is None or attribution is None:
        return CONNECTIVITY_CAVEAT
    if attribution.tainted_value_received:
        return FIFO_CAVEAT
    return NO_TAINT_CAVEAT


def _path_assumption(result: TraceResult, attribution: Attribution) -> dict[str, float]:
    """
    How much of THIS finding's route rested on the pre-existing-balance assumption.

    WHY THIS IS NOT THE GRAPH-WIDE FIGURE. `accounting.assumed_pre_existing` sums
    that assumption across every wallet the trace touched, which on a busy graph
    runs to six figures - printing it beside a 1,220 ETH finding implies the
    finding is swamped by uncertainty even when the route to it was fully
    accounted for. What an investigator needs is the uncertainty on the legs of
    the route they are about to act on, which is what this returns.
    """
    legs = set(zip(attribution.path, attribution.path[1:]))
    totals: dict[str, float] = {}
    for hop in result.hops:
        if (hop.from_addr, hop.to_addr) in legs and hop.assumed_pre_existing > 0:
            totals[hop.asset] = totals.get(hop.asset, 0.0) + hop.assumed_pre_existing
    return {asset: round(value, 8) for asset, value in totals.items()}


def _taint_fields(attribution: Attribution, result: TraceResult) -> dict:
    """The per-finding taint block, shared by every branch of summarize()."""
    if result.taint is None:
        return {"taint_computed": False}
    tainted = attribution.tainted_value_received
    on_path = _path_assumption(result, attribution)
    return {
        "taint_computed": True,
        "tainted_value_received": {k: round(v, 8) for k, v in tainted.items()},
        "tainted_value_display": format_assets(tainted) if tainted else None,
        "tainted_inflow_fraction": attribution.tainted_inflow_fraction,
        "inflow_fully_observed": attribution.inflow_fully_observed,
        # The uncertainty that applies to THIS route, not to the whole graph.
        "path_assumed_pre_existing": on_path,
        "path_assumed_pre_existing_display": (
            format_assets(on_path) if on_path else None
        ),
        "path_fully_accounted": not on_path,
        "inflow_note": (
            None
            if attribution.inflow_fully_observed
            else (
                "This wallet's own transaction history was not fetched - the trace "
                "stops at it - so the share-of-inflow figure is measured only "
                "against the transfers the trace itself observed, not against "
                "everything the wallet received."
            )
        ),
    }


def summarize(result: TraceResult) -> dict:
    """
    The headline finding, ready for the investigator-facing panel.

    Reports the NEAREST exchange, because hop distance is the strongest
    available proxy for how directly the suspect controlled the deposit. A
    result is always honest about failure: if nothing was recognised, that is
    stated plainly rather than dressed up as a weak hit.
    """
    # A NAMED exchange and a mere consolidation pattern are not interchangeable,
    # and the headline must never blur them. Criminals consolidate too - they
    # re-pool funds from their own split wallets, which produces exactly the
    # fan-in signature an exchange deposit sweep produces. Method (b) cannot
    # tell those apart, so a suspected hit is only ever reported as a lead.
    confirmed = [a for a in result.exchanges if a.entity_type == "exchange"]
    suspected = [a for a in result.exchanges if a.entity_type == "suspected_exchange"]
    exchanges = confirmed
    flags = result.flags

    if not confirmed and suspected:
        lead = suspected[0]
        return {
            "found": False,
            "lead": True,
            "headline": (
                f"No named exchange within {result.max_depth} hops. A transaction "
                f"path connects to one collection point {lead.hop_distance} hops "
                f"away ({lead.confidence_score}% confidence) - UNCONFIRMED."
            ),
            "caveat": _caveat_for(result, lead),
            **_taint_fields(lead, result),
            "termination": result.termination,
            "address": lead.address,
            # The graph node id, which carries the chain once a trace crosses one.
            # Matching on ddress alone finds no route across a crossing.
            "node_id": lead.node_id,
            "hop_distance": lead.hop_distance,
            "confidence": round(lead.confidence, 2),
            "confidence_score": lead.confidence_score,
            "confidence_breakdown": lead.confidence_breakdown,
            "confidence_components": lead.confidence_components,
            "method": lead.method,
            "value_received": {k: round(v, 8) for k, v in lead.value_received.items()},
            "value_received_display": format_assets(lead.value_received),
            "value_received_eth": round(lead.value_received_eth, 6),
            "recommended_action": (
                f"Do NOT treat {lead.address} as an exchange yet. Many wallets "
                f"funnel into it, but a criminal re-pooling their own split "
                f"funds produces the same pattern. Verify it independently "
                f"(Etherscan labels, outgoing transaction count) before any "
                f"lawful request is raised."
            ),
            "mixers_or_bridges_crossed": [f.entity for f in flags],
        }

    if not exchanges:
        return {
            "found": False,
            "lead": False,
            "headline": (
                "No transaction path to a known exchange within "
                f"{result.max_depth} hops of {result.start_address[:10]}..."
            ),
            "termination": result.termination,
            # Stated even with no endpoint, so a consumer can tell "the FIFO pass
            # ran but there was no endpoint to attribute value to" from "the FIFO
            # pass never ran". Without it the panel read a missing field as a
            # computed zero and printed "0.00 stolen" over a trace with no finding.
            "taint_computed": result.taint is not None,
            "recommended_action": (
                "Widen the trace depth, or expand labels.json. Funds may still "
                "be sitting in unhosted wallets or have moved via ERC-20 "
                "tokens, which this build does not yet follow."
            ),
            "mixers_or_bridges_crossed": [f.entity for f in flags],
        }

    nearest = exchanges[0]
    return {
        "found": True,
        "lead": False,
        "exchange": nearest.entity,
        "address": nearest.address,
        # The graph node id, which carries the chain once a trace crosses one.
        # Matching on ddress alone finds no route across a crossing.
        "node_id": nearest.node_id,
        "hop_distance": nearest.hop_distance,
        "confidence": round(nearest.confidence, 2),
        "confidence_score": nearest.confidence_score,
        "confidence_breakdown": nearest.confidence_breakdown,
        "confidence_components": nearest.confidence_components,
        "method": nearest.method,
        "value_received": {k: round(v, 8) for k, v in nearest.value_received.items()},
        "value_received_display": format_assets(nearest.value_received),
        "value_received_eth": round(nearest.value_received_eth, 6),
        "value_received_note": (
            "Per-asset totals this wallet received along traced edges - the gross "
            "amount that landed here, NOT the amount attributable to the suspect. "
            "See tainted_value_received for that. Assets are never summed "
            "together; there is no price feed in this build."
        ),
        **_taint_fields(nearest, result),
        "headline": _headline(result, nearest),
        "caveat": _caveat_for(result, nearest),
        "recommended_action": (
            f"Serve a lawful data request to {nearest.entity} via SAHYOG for "
            f"KYC records on deposits to {nearest.address}, covering the "
            f"transactions listed in the traced path."
        ),
        "termination": result.termination,
        "cluster_id": nearest.cluster_id,
        "cluster_members": next(
            (c.member_count for c in result.clusters if c.cluster_id == nearest.cluster_id),
            1,
        ),
        "mixers_or_bridges_crossed": [f.entity for f in flags],
        "other_exchanges_reached": [a.entity for a in exchanges[1:]],
        "unconfirmed_collection_points": [a.address for a in suspected],
    }


def _headline(result: TraceResult, nearest: Attribution) -> str:
    """
    The one sentence an investigator reads first.

    Where taint was computed it leads with VALUE ARRIVAL - "12.4 ETH of the
    suspect's funds reached Binance, 2 hops" - because that is the finding, and
    the hop count alone was always the weaker half of it. Where taint was
    computed and came out empty, it says so rather than falling back to wording
    that implies money arrived. Where taint could not be computed, the original
    connectivity wording stands.
    """
    hops = f"{nearest.hop_distance} hop{'s' if nearest.hop_distance != 1 else ''}"
    confidence = f"{nearest.confidence_score}% confidence"

    if result.taint is None:
        return f"Transaction path connects to {nearest.entity}, {hops}, {confidence}"

    tainted = nearest.tainted_value_received
    if not tainted:
        return (
            f"Transaction path connects to {nearest.entity}, {hops} - but no value "
            f"attributable to the suspect arrived under FIFO accounting"
        )
    return (
        f"{format_assets(tainted)} of the suspect's funds reached "
        f"{nearest.entity}, {hops}, {confidence}"
    )


def _node_taint(result: TraceResult, node: str):
    """
    The taint replay that holds the value for one graph node.

    Node ids carry their chain for everything off the starting chain, so the right
    replay is not always the primary one. Reading a cross-chain node out of the
    primary replay would silently report it as receiving nothing, which is the
    kind of quiet wrong answer this project treats as worse than an error.
    """
    slug = None
    if ":" in node:
        slug = node.split(":", 1)[0]
    if slug is None:
        return result.taint
    return result.taint_chains.get(slug)


def _crossing_handoff(result: TraceResult, src: str, dst: str) -> dict | None:
    """The BridgeMatch behind one crossing edge, or None if we cannot find it."""
    # Compared on the bare address, because the Hop records wallets as plain
    # addresses while the graph edge qualifies them with a chain
    # ("arbitrum:0x..."). Matching the qualified id against the bare one never
    # succeeds, which silently left every crossing edge without its evidence.
    src_bare = _bare_address(src)
    dst_bare = _bare_address(dst)
    for hop in result.hops:
        if (
            hop.edge_type == "cross_chain"
            and hop.from_addr.lower() == src_bare
            and hop.to_addr.lower() == dst_bare
        ):
            return hop.handoff.to_payload() if hop.handoff is not None else None
    return None


def to_json(result: TraceResult) -> dict:
    """
    Flatten a TraceResult into the frontend's JSON shape.

    Deliberately a flat nodes + edges pair using `id` / `source` / `target`,
    which is what Cytoscape.js consumes directly - no reshaping in the browser.
    """
    nodes = [
        {
            "id": address,
            "depth": data.get("depth", 0),
            "is_start": data.get("is_start", False),
            "label": data.get("label"),
            "entity_type": data.get("entity_type"),
            "is_vasp": data.get("is_vasp", False),
            "is_mixer": data.get("is_mixer", False),
            "is_bridge": data.get("is_bridge", False),
            "confidence": data.get("confidence"),
            "method": data.get("method"),
            # Which chain this wallet is on. Once a trace crosses a chain, the same
            # address appears twice as two different wallets, and a graph node with
            # no chain attached cannot be explained to a reader.
            "chain": data.get("chain", result.chain.get("slug")),
            # The bare address, so a consumer can paste it into an explorer without
            # having to strip the chain prefix from the node id itself.
            "address": _bare_address(address),
            # Per-asset value attributable to the suspect that reached this
            # wallet. Lets the graph show WHERE the money went, not just what
            # is connected to what. Read from THIS node's chain replay - the
            # figure for a wallet reached over a bridge exists only on the chain
            # the money arrived on.
            "tainted_in": (
                _node_taint(result, address).tainted_into(_bare_address(address))
                if _node_taint(result, address)
                else {}
            ),
        }
        for address, data in result.graph.nodes(data=True)
    ]
    nodes.sort(key=lambda n: (n["depth"], n["id"]))

    def _asset_entry(src: str, dst: str, entry: dict, edge: dict | None = None) -> dict:
        """One asset on one edge, with its tainted share attached."""
        out = {
            k: (round(v, 8) if isinstance(v, float) else v) for k, v in entry.items()
        }
        if edge is not None and edge.get("edge_type") == "cross_chain":
            # A chain crossing has no transfer for a FIFO replay to find, so its
            # tainted share cannot be recomputed here - it comes from the handoff
            # and is already on the hop. Taking it from the hop keeps the figure
            # identical in the graph, the path and the PDF instead of the payload
            # quietly showing zero.
            out["tainted_value"] = round(edge.get("tainted_value", 0.0), 8)
            out["tainted_fraction"] = (
                round(out["tainted_value"] / entry["value"], 6) if entry.get("value") else 0.0
            )
            out["assumed_pre_existing"] = round(
                min(edge.get("assumed_pre_existing", 0.0), entry.get("value", 0.0)), 8
            )
            return out
        leg = _node_taint(result, src)
        flow = (
            leg.edge(_bare_address(src), _bare_address(dst), entry.get("asset", ""))
            if leg
            else None
        )
        if flow is not None:
            # Capped at the edge's own value: the taint pass replays every
            # transfer, including the dust this aggregated edge filtered out.
            out["tainted_value"] = round(min(flow.tainted, entry.get("value", 0.0)), 8)
            out["tainted_fraction"] = (
                round(out["tainted_value"] / entry["value"], 6)
                if entry.get("value") else 0.0
            )
            out["assumed_pre_existing"] = round(
                min(flow.assumed_pre_existing, entry.get("value", 0.0)), 8
            )
        return out

    edges = [
        {
            "source": src,
            "target": dst,
            "assets": [
                _asset_entry(src, dst, entry, data)
                for entry in (data.get("assets") or {}).values()
            ],
            "asset": data.get("asset", ""),
            "value": round(data.get("value", 0.0), 8),
            # Legacy scalar: the primary asset's amount, and 0 when that asset is
            # a token. Read `assets` for the truth.
            "value_eth": round(data.get("value", 0.0), 6)
            if not data.get("asset") or data.get("asset") in ("ETH", "POL", "BNB")
            else 0.0,
            "tx_count": data.get("tx_count", 1),
            "timestamp": data.get("timestamp", 0),
            "tx_hash": data.get("tx_hash", ""),
            "depth": data.get("depth", 0),
            # "transfer" or "cross_chain". A chain crossing is not just another
            # transfer and must not be drawn as one: it is an inference, it costs a
            # hop, and it is the step where a reader most needs to be told that
            # something was assumed.
            "edge_type": data.get("edge_type", "transfer"),
            "from_chain": data.get("from_chain"),
            "to_chain": data.get("to_chain"),
            # Only on a crossing edge: the full match behind it, so a consumer -
            # the path view, the PDF - can show WHY the trace believes the value
            # reappeared rather than restating the conclusion.
            "handoff": (
                _crossing_handoff(result, src, dst)
                if data.get("edge_type") == "cross_chain"
                else None
            ),
        }
        for src, dst, data in result.graph.edges(data=True)
    ]
    # (source, target) is the final tie-break, not decoration: without it equal
    # depth and value fall back to insertion order, which differs between the
    # graph backends and made the serialised edge list backend-dependent.
    # Sort by the primary asset's amount, with (source, target) as the final
    # deterministic tie-break. Amounts of different assets are not comparable, so
    # this is an ordering convention, not a value judgement.
    edges.sort(key=lambda e: (e["depth"], -e["value"], e["source"], e["target"]))

    return {
        "start_address": result.start_address,
        "params": {
            "max_depth": result.max_depth,
            "dust_threshold_eth": result.dust_threshold,
            "chain_id": result.chain.get("chain_id"),
            "chain": result.chain.get("slug"),
            "chain_name": result.chain.get("name"),
            "native_symbol": result.chain.get("native"),
            "explorer": result.chain.get("explorer"),
        },
        "summary": summarize(result),
        "attributions": [a.to_dict() for a in result.attributions],
        "clusters": [c.to_dict() for c in result.clusters],
        "exchanges": [a.to_dict() for a in result.exchanges],
        "flags": [a.to_dict() for a in result.flags],
        "risk_flags": [f.to_dict() for f in result.risk_flags],
        "stats": {
            "nodes": result.graph.number_of_nodes(),
            "edges": result.graph.number_of_edges(),
            "hops": len(result.hops),
            "max_depth_reached": max((n["depth"] for n in nodes), default=0),
            "identified": len(result.attributions),
            "clusters": len(result.clusters),
            "labels_loaded": identify.label_count(),
            "api_calls": result.api_calls,
            "cache_hits": result.cache_hits,
            "elapsed_sec": result.elapsed_sec,
            "truncated": result.truncated,
            "graph_backend": result.backend,
        },
        "termination": result.termination,
        "token_warnings": result.token_warnings,
        # Every bridge deposit we tried to carry across, including the ones we
        # declined. A consumer must be able to tell "we followed this" from "we
        # looked and stopped", and both from "we never met a bridge" - three very
        # different states that would otherwise render the same.
        "cross_chain": {
            "chains_traced": result.chains_traced,
            "label_coverage": result.label_coverage,
            "hops_used": sum(
                1 for h in result.hops if h.edge_type == "cross_chain"
            ),
            "max_hops": config.MAX_CROSS_CHAIN_HOPS,
            "matched": sum(
                1 for h in result.cross_chain_handoffs if h.matched
            ),
            # A handoff list with no matched entry is the important case: it is
            # where the trail goes cold, and it says so with a reason.
            "handoffs": [h.to_payload() for h in result.cross_chain_handoffs],
            "fee_tolerance": config.BRIDGE_FEE_TOLERANCE,
            "match_min_score": config.BRIDGE_MATCH_MIN_SCORE,
            "note": (
                "A cross-chain handoff is an inference, not an observation. The "
                "deposit is on record on its own chain; the arrival of the same "
                "value on the destination chain is matched by amount, timing, "
                "recipient address and payout contract. It carries its own score, "
                "which is never merged into the on-chain confidence figure."
            ),
        },
        # Matched laundering typologies, strongest first, each with the
        # measurements and thresholds that produced it. Deliberately NOT merged
        # into risk_flags - see the note on TraceResult.typologies.
        "typologies": [d.to_dict() for d in result.typologies],
        "typology_summary": typologies.summarise(
            result.typologies, result.typologies_suppressed
        ),
        # How the tainted figures above were produced, and their uncertainties.
        # Present even when taint could not run, so a consumer can tell the
        # difference between "nothing was attributable" and "not computed".
        "accounting": (
            taint_engine.summarise(result.taint, result.start_address)
            if result.taint is not None
            else {"rule": None, "rule_label": CONNECTIVITY_CAVEAT}
        ),
        "notes": result.notes,
        "nodes": nodes,
        "edges": edges,
        "hops": [hop.to_dict() for hop in result.hops],
    }
