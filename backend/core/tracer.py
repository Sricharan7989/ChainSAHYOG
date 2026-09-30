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
from core import clustering, identify, scoring, taint as taint_engine
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

    def to_dict(self) -> dict:
        return {
            "address": self.address,
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

    store = graph_store.get_store()
    hops: list[Hop] = []
    notes: list[str] = []
    attributions: dict[str, Attribution] = {}  # keyed by address, first hit wins
    truncated = False

    def record(address: str, ident: identify.Identification, depth: int) -> None:
        """Mark the wallet and log the attribution, keeping the shortest hop distance."""
        _mark_node(store, address, ident)
        if address in attributions:
            return
        attributions[address] = Attribution(
            address=address,
            entity=ident.entity,
            entity_type=ident.entity_type,
            method=ident.method,
            confidence=ident.confidence,
            hop_distance=depth,
            evidence=ident.evidence,
        )

    # depth = hops from the start address. The suspect wallet itself is depth 0.
    store.add_wallet(start, depth=0, is_start=True)

    # If the suspect address is ITSELF a known entity, that is worth reporting -
    # but we still expand it. Stopping at depth 0 would return an empty graph
    # and tell the investigator nothing about where the money went.
    start_ident = identify.known_label_lookup(start, chain=chain["slug"])
    if start_ident is not None:
        record(start, start_ident, 0)
        notes.append(
            f"The start address is itself a known entity ({start_ident.entity}); "
            f"tracing onward from it anyway."
        )

    # `expanded` guards against refetching a wallet we have already walked out
    # of. Laundering paths loop and re-converge, so without this the walk can
    # revisit the same wallet along every inbound path - or spin forever on a
    # cycle. The wallet keeps its FIRST (shortest) depth, per the BFS argument.
    expanded: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(start, 0)])

    # Every wallet whose history we pulled, with BOTH directions, for the taint
    # pass. Held here rather than re-read from the client cache so the replay sees
    # exactly the data the walk saw.
    fetched: dict[str, list[Transfer]] = {}

    # Why did the walk stop? Counted as it happens, because after the fact the
    # graph cannot tell you whether a branch ended at a mixer, ran out of depth,
    # or simply had nothing above the dust threshold.
    stopped_at: dict[str, int] = {}
    depth_capped = 0
    start_had_no_transfers = False
    start_had_only_dust = False

    while queue:
        address, depth = queue.popleft()

        if address in expanded:
            continue
        # Depth cap: this wallet is recorded in the graph, we just do not ask
        # where its money went next. This is the boundary of the trace.
        if depth >= max_depth:
            depth_capped += 1
            continue
        if store.wallet_count() >= config.MAX_NODES_PER_TRACE:
            truncated = True
            notes.append(
                f"Stopped expanding at {config.MAX_NODES_PER_TRACE} wallets "
                f"(MAX_NODES_PER_TRACE). The graph is partial."
            )
            break

        # Re-check before spending an API call. Fan-in may have matured since
        # this wallet was queued, and if it is now recognisable the branch is
        # already answered - expanding an exchange hot wallet would be both
        # pointless and ruinously expensive.
        if depth > 0:
            ident = identify.identify(address, store, chain=chain["slug"])
            if ident is not None:
                record(address, ident, depth)
                if identify.is_terminal(ident):
                    stopped_at[ident.entity_type] = stopped_at.get(ident.entity_type, 0) + 1
                    continue

        expanded.add(address)

        try:
            # BOTH directions, in the same API calls the walk always made. The
            # walk itself uses only the outgoing half; the incoming half is what
            # lets the taint pass order each wallet's balance. Fetching it here
            # rather than in a second sweep is what keeps taint free.
            fetched_transfers = await client.get_wallet_transfers(
                address, chain_id=chain["chain_id"]
            )
            fetched[address] = fetched_transfers
            transfers = [t for t in fetched_transfers if t.from_addr == address]
        except Exception as exc:  # noqa: BLE001 - one bad wallet must not kill the trace
            if address == start:
                # No data for the suspect wallet means there is nothing to show.
                raise
            notes.append(f"Could not fetch {address}: {exc}")
            continue

        # Aggregate first, THEN pick the biggest branches. Ranking raw
        # transactions would let one counterparty paid in 50 small slices lose
        # to a single larger one-off, even though it received far more overall.
        flows = _aggregate_by_recipient(transfers, dust_threshold)
        ranked = sorted(flows.values(), key=_flow_rank, reverse=True)

        if address == start and not ranked:
            # Distinguishing "sent nothing" from "sent only dust" matters: the
            # first is a dead end, the second is a threshold the investigator
            # can lower and re-run.
            start_had_no_transfers = not transfers
            start_had_only_dust = bool(transfers)

        if len(ranked) > config.MAX_EDGES_PER_NODE:
            truncated = True
            notes.append(
                f"{address} sent to {len(ranked)} recipients; expanded the "
                f"{config.MAX_EDGES_PER_NODE} largest by value."
            )
            ranked = ranked[: config.MAX_EDGES_PER_NODE]

        child_depth = depth + 1
        for flow in ranked:
            to_addr = flow["to"]

            if not store.has(to_addr):
                store.add_wallet(to_addr, depth=child_depth, is_start=False)

            assets = {
                symbol: {k: v for k, v in entry.items() if not k.startswith("_")}
                for symbol, entry in flow["assets"].items()
            }
            primary = _primary_asset(flow["assets"]) or {}

            store.add_transfer(
                address,
                to_addr,
                # Per-asset detail is the truth; the scalar fields below describe
                # the edge's PRIMARY asset only, for callers that need one number.
                assets=assets,
                value=primary.get("value", 0.0),
                asset=primary.get("asset", ""),
                tx_count=flow["tx_count"],
                timestamp=flow["timestamp"],
                tx_hash=primary.get("tx_hash", ""),
                depth=child_depth,
            )

            # One hop row per asset moved: an ETH hop and a USDT hop between the
            # same pair are two different facts an investigator may cite.
            for entry in assets.values():
                hops.append(
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
                    )
                )

            # Label lookup the moment the wallet is discovered - it needs only
            # the address, so there is no reason to wait.
            child_ident = identify.known_label_lookup(to_addr, chain=chain["slug"])
            if child_ident is not None:
                record(to_addr, child_ident, child_depth)
                if identify.is_terminal(child_ident):
                    stopped_at[child_ident.entity_type] = (
                        stopped_at.get(child_ident.entity_type, 0) + 1
                    )
                    # Branch complete: we found where this money came to rest.
                    continue

            if to_addr not in expanded and child_depth < max_depth:
                queue.append((to_addr, child_depth))

    # Final consolidation sweep. Fan-in is only fully known once the walk is
    # over, so a wallet where several branches converged may become recognisable
    # here even though it looked ordinary every time we saw it mid-walk.
    for address, data in store.wallets():
        if address in attributions or address == start:
            continue
        late = identify.consolidation_identify(address, store)  # chain-agnostic
        if late is not None:
            record(address, late, data.get("depth", 0))
            notes.append(
                f"{address} was identified as a consolidation point only after "
                f"the walk completed; its onward transfers were still followed."
            )

    # VALUE-LEVEL TAINT. Runs on the transfers already fetched, in chronological
    # order, under the FIFO rule documented in core/taint.py. Separate from the
    # walk because FIFO needs time order and the walk runs in breadth-first order.
    taint = taint_engine.compute_taint(fetched, start) if fetched else None

    # Attach how much value actually reached each identified endpoint - gross, and
    # the part attributable to the suspect.
    for attribution in attributions.values():
        totals = _value_received(store, attribution.address)
        attribution.value_received = totals
        attribution.value_received_eth = _native_total(totals, chain)
        if taint is not None:
            attribution.tainted_value_received = taint.tainted_into(attribution.address)
            attribution.tainted_inflow_fraction = taint.inflow_fractions(
                attribution.address
            )
            attribution.inflow_fully_observed = taint.fully_observed(
                attribution.address
            )

    # Per-hop taint, so an investigator can see which leg of the route carried the
    # suspect's money and which merely existed.
    if taint is not None:
        for hop in hops:
            flow = taint.edge(hop.from_addr, hop.to_addr, hop.asset)
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
        attribution.path = store.shortest_path(start, attribution.address)
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
        attribution.cluster_id = index.get(attribution.address)

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
    )

    # What we deliberately did not follow, reported so the gap is visible.
    # No extra API calls: the walk already fetched every wallet's token rows, so
    # what we declined to follow is known from data in hand.
    token_warnings = _unfollowed_token_note(client, chain["chain_id"])

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
) -> dict:
    """
    Say WHY the walk stopped, in terms an investigator can act on.

    A trace that finds nothing used to return an empty graph and no explanation,
    which is indistinguishable from a broken tool. Each reason below implies a
    different next step - lower the threshold, raise the depth, accept that the
    trail is cut, or expand the label set - so the reason is the useful part.

    Ordered by what actually ended the search, most decisive first: a start
    wallet that never sent anything outranks a depth cap that was never reached.
    """
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
            "label": f"All outgoing transfers are below {dust_threshold} ETH",
            "detail": (
                "Everything leaving this wallet is smaller than the dust "
                f"threshold of {dust_threshold} ETH, so nothing was followed. "
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
    if stopped_at.get("bridge"):
        n = stopped_at["bridge"]
        return {
            "reason": "terminated_at_bridge",
            "label": f"The trail leaves Ethereum via a bridge ({n} branch{'es' if n > 1 else ''})",
            "detail": (
                "The funds moved to another blockchain. The trail continues "
                "there, outside what this tool covers."
            ),
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
    note = {
        "skipped_transfers": total,
        "distinct_tokens": len(skipped),
        "followed_assets": config.followed_assets(chain_id),
        "top_skipped": [
            {
                "asset": asset,
                "transfers": count,
                "impersonating": config.impersonates_followed_asset(chain_id, asset),
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
    for address, data in store.wallets():
        entity_type = data.get("entity_type")
        severity = scoring.risk_severity(entity_type or "")
        if severity is None:
            continue

        entity = data.get("label") or "Unknown entity"
        flags.append(
            RiskFlag(
                address=address,
                entity=entity,
                risk_type=entity_type,
                severity=severity,
                hop_distance=data.get("depth", 0),
                on_primary_path=address in primary_path,
                value_received=_value_received(store, address),
                value_received_eth=_native_total(_value_received(store, address), None),
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
            # Per-asset value attributable to the suspect that reached this
            # wallet. Lets the graph show WHERE the money went, not just what
            # is connected to what.
            "tainted_in": result.taint.tainted_into(address) if result.taint else {},
        }
        for address, data in result.graph.nodes(data=True)
    ]
    nodes.sort(key=lambda n: (n["depth"], n["id"]))

    def _asset_entry(src: str, dst: str, entry: dict) -> dict:
        """One asset on one edge, with its tainted share attached."""
        out = {
            k: (round(v, 8) if isinstance(v, float) else v) for k, v in entry.items()
        }
        flow = result.taint.edge(src, dst, entry.get("asset", "")) if result.taint else None
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
                _asset_entry(src, dst, entry)
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
