"""
Exchange identification — deciding whether a wallet in the trace is a VASP.

WHY THIS MODULE IS THE PAYOFF
-----------------------------
The tracer maps where money went. This module answers the question that makes
the trace actionable: is this wallet the property of a regulated business that
holds KYC records? A path through twelve anonymous wallets is useless on its
own. The same path ending at a wallet we can name as Binance is a lawful
request away from a human identity.

WHY IDENTIFICATION IS POSSIBLE AT ALL
-------------------------------------
A criminal's wallets are fresh and anonymous, so there is nothing to recognise.
An exchange is the opposite: it serves millions of users, must publish deposit
addresses, and settles enormous volume through a small set of wallets. It
cannot hide, and it cannot cheaply rotate. That asymmetry is the entire basis
of this tool - we never identify the criminal, we identify the exit.

THE FOUR METHODS
----------------
  (a) known_label_lookup   - WORKS. Direct match against data/labels.json.
  (b) consolidation_score  - WORKS. Deposit-consolidation fan-in fingerprint.
  (c) behavioral_classifier - STUB, future scope.
  (d) cospend_cluster      - STUB, not applicable to Ethereum's account model.

Every result carries a confidence below 1.0. This tool informs a lawful
request; it never asserts certainty, and an investigator must be able to see
WHICH method produced a claim in order to weigh it. That is why `method` and
`evidence` travel with every Identification.
"""

import json
from dataclasses import dataclass, replace

import networkx as nx

from app import config
from core import addresses
from services import graph_store

# --- Tunables -----------------------------------------------------------------

# The chain a label belongs to when the file does not say. Every entry predates
# multi-chain support and describes Ethereum, so this keeps them all valid.
DEFAULT_CHAIN = "ethereum"

# Distinct in-graph senders before fan-in is considered meaningful at all.
# Below this, a shared recipient is just as likely to be a merchant, a contract
# or coincidence, so claiming "exchange" would be irresponsible.
CONSOLIDATION_MIN_SENDERS = 4

# Distinct senders at or above which we actually flag the address. Expressed as
# a COUNT rather than as a score cutoff, because the count is the thing with a
# real-world meaning and a reviewer can argue with it: six separate wallets from
# one suspect's flow converging on a single address is a genuine anomaly, since
# a trace only walks a few hundred wallets of one money flow in the first place.
CONSOLIDATION_FLAG_SENDERS = 6

# Fan-in at or above which we treat the consolidation pattern as saturated and
# award the method's maximum confidence.
CONSOLIDATION_STRONG_SENDERS = 12

# Confidence for an exact labels.json hit. Deliberately not 1.0: labels can go
# stale, exchanges rotate wallets, and a published list can simply be wrong.
LABEL_CONFIDENCE = 0.95

# Ceiling for a pure fan-in inference. Far lower than a label match, because
# the pattern is suggestive, not identifying - it says "this behaves like a
# collection point", never "this is Binance".
CONSOLIDATION_MAX_CONFIDENCE = 0.70

# CHAIN-WIDE FAN-IN. The subgraph count above only sees senders this trace
# walked, so "several of the suspect's own paths reconverge" and "an exchange
# collects deposits from hundreds of unrelated customers" look identical to it.
# A candidate that passes the subgraph gates is therefore checked against how
# many distinct addresses have sent to it chain-wide. Below the minimum it is
# not a collection point, whatever the subgraph shows.
#
# CALIBRATED, not chosen: see docs/fan-in-calibration.md and
# data/calibration/fanin_sample.json (70 labelled exchange wallets, 9 known
# attacker re-pooling wallets, measured at one pinned block). Senders are
# counted only over NON-DUST transfers of FOLLOWED assets, because zero-value
# "address poisoning" spam gave an OFAC-listed Lazarus wallet 204 raw senders.
# On that measure the attacker wallets reach at most 9; a floor of 20 sits above
# all of them with a 2x margin and keeps 44 of the 50 genuine deposit-collecting
# exchange wallets in the sample.
CONSOLIDATION_GLOBAL_MIN_SENDERS = 20
CONSOLIDATION_GLOBAL_STRONG_SENDERS = 200
# SECOND CONDITION: a collection point receives from many and pays out in
# sweeps; an attacker's pool receives from a few and fans out. Distinct value
# senders per outgoing transaction below this is the attacker shape (Ronin's
# 0xee009faf: 9 senders over ~1,300 outgoing rows = 0.007). Calibrated on the
# same sample: costs 3 of 50 genuine collecting wallets.
CONSOLIDATION_MIN_SENDERS_PER_OUT_TX = 0.01

# What every fan-in finding must say about itself (surfaced on the lead and in
# the PDF). The calibration is the reason, so the tool states it.
FAN_IN_WEAK_SIGNAL = (
    "Fan-in is a weak signal, not a reliable detector: calibrated against verified exchange "
    "wallets, attacker pools reached 9 senders and the smallest genuine collecting exchange 10. "
    "That near-overlap is why a fan-in-only identification is capped at 67% and never names a company."
)
FAN_IN_ETHEREUM_ONLY = (
    "The fan-in thresholds were calibrated on Ethereum only; applying them on {chain} is an "
    "assumption, not a measurement, until {chain} has enough labelled exchange wallets to re-calibrate."
)
# Where the label coverage note lives: what no structural method can find.
STRUCTURAL_LIMIT = (
    "Fan-in can only find wallets that are currently collecting deposits. In calibration, 20 of 70 "
    "labelled exchange wallets were dormant or withdrawal-only, so no structural method would find "
    "them; only a label names such a wallet."
)
# Where the chain-wide count cannot be obtained, the finding rests on subgraph
# structure alone and its confidence is scaled by this factor.
CONSOLIDATION_SUBGRAPH_ONLY_FACTOR = 0.5


@dataclass(frozen=True)
class Identification:
    """
    One attribution claim about one address.

    `method` and `evidence` are not decoration. An investigator acting on this
    has to know whether the name came from a published label or from a
    statistical hunch, because those justify very different actions.
    """

    address: str
    entity: str
    entity_type: str  # exchange | mixer | bridge | suspected_exchange
    method: str  # known_label | consolidation
    confidence: float
    evidence: str
    # For a consolidation finding: senders observed in this trace and senders
    # chain-wide (see apply_global_fan_in). None for a label match.
    fan_in: dict | None = None

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "entity": self.entity,
            "entity_type": self.entity_type,
            "method": self.method,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
        }


# --- Label store --------------------------------------------------------------

_labels: dict[str, dict] | None = None
_labels_mtime: float | None = None


def load_labels(force_reload: bool = False) -> dict[str, dict]:
    """
    Read data/labels.json into memory, re-reading it whenever the file changes.

    Keys are lowercased on load so a checksummed address from any source still
    matches. Underscore-prefixed keys are documentation, not data, and JSON has
    no comment syntax - hence the convention.

    CHAIN AWARENESS: the in-memory index is keyed by (chain, address), not by
    address alone. The same address can be a completely different entity on
    another network - a deployer controls the address on every EVM chain, and
    contract addresses collide by construction - so a label that is true on
    Ethereum must not be asserted on Polygon. Two spellings are accepted in the
    file: a bare address (which means Ethereum, keeping every existing entry
    valid) and "<chain>:<address>" for anything chain-specific. An explicit
    "chain" field on the entry wins over both.

    WHY it watches the file's timestamp: labels are DATA, and uvicorn --reload
    only watches code. Without this, importing new labels appears to do nothing
    until someone thinks to restart the server - a trap that would be found
    mid-demo rather than now. Caching on mtime keeps lookups free while making
    an edit to labels.json take effect on the next request.
    """
    global _labels, _labels_mtime, label_origin_counts

    def _mtime(path):
        try:
            return path.stat().st_mtime
        except OSError:
            return None

    # Both files are watched: the committed labels.json and the gitignored
    # labels.local.json (rows we may use but not redistribute).
    local_path = getattr(config, "LABELS_LOCAL_PATH", None)
    mtime = (_mtime(config.LABELS_PATH), _mtime(local_path) if local_path else None)

    if _labels is not None and not force_reload and mtime == _labels_mtime:
        return _labels
    _labels_mtime = mtime

    try:
        raw = json.loads(config.LABELS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        # A missing labels file disables method (a) but must not break a trace;
        # the consolidation heuristic still works.
        raw = {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"data/labels.json is not valid JSON: {exc}") from exc

    # The local file only ADDS rows. On a clash the committed row wins, so a
    # local copy can never silently override a published, cited label.
    local_raw = {}
    if local_path is not None and local_path.exists():
        try:
            local_raw = json.loads(local_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"data/labels.local.json is not valid JSON: {exc}") from exc
    label_origin_counts = {"committed": 0, "local": 0, "local_file_present": bool(local_raw)}
    merged = dict(raw)
    for key, meta in local_raw.items():
        if not str(key).startswith("_") and key not in raw:
            merged[key] = meta

    index: dict[tuple[str, str], dict] = {}
    rejected: list[str] = []
    for key, meta in merged.items():
        key = str(key).strip()
        if key.startswith("_") or not isinstance(meta, dict):
            continue

        # "<chain>:<address>" in the key, an explicit "chain" field, or neither
        # (Ethereum). The field wins so a file can be reorganised without
        # rewriting every key.
        chain_from_key, _, address = key.rpartition(":")
        chain_name = str(meta.get("chain") or chain_from_key or DEFAULT_CHAIN).strip().lower()
        # FORMAT GUARD. Keyed by the chain's own rule (core/addresses.py): never
        # lowercased where case carries meaning, and a row whose address does not
        # parse for its chain is refused here rather than indexed - so an
        # Ethereum-shaped address filed under Tron, or the reverse, can never
        # match anything.
        canonical = addresses.try_normalize(address, chain_name)
        if canonical is None:
            rejected.append(key)
            continue
        index[(chain_name, canonical)] = meta
        label_origin_counts["local" if key in local_raw and key not in raw else "committed"] += 1

    global rejected_label_keys
    rejected_label_keys = rejected
    _labels = index
    return _labels


# Label rows refused by the format guard on the last load, for diagnostics.
rejected_label_keys: list[str] = []
# How many indexed rows came from the committed file and from the local one.
label_origin_counts: dict = {"committed": 0, "local": 0, "local_file_present": False}


def label_stats() -> dict:
    """Label counts for /health: committed vs local, and per chain, type and evidence tier."""
    labels = load_labels()
    by_chain, by_type, by_tier = {}, {}, {}
    for (chain_name, _), meta in labels.items():
        by_chain[chain_name] = by_chain.get(chain_name, 0) + 1
        t = str(meta.get("type", "unknown"))
        by_type[t] = by_type.get(t, 0) + 1
        tier = str(meta.get("evidence_tier") or "unrecorded")
        by_tier[tier] = by_tier.get(tier, 0) + 1
    return {
        "total": len(labels),
        **label_origin_counts,
        "refused_by_format_guard": len(rejected_label_keys),
        "by_chain": by_chain,
        "by_type": by_type,
        "by_evidence_tier": by_tier,
    }


def label_count(chain: str | None = None) -> int:
    """
    How many addresses we can recognise, optionally for one chain only.

    The per-chain number is the honest one to show next to a trace: a Polygon
    trace is not helped by 525 Ethereum labels.
    """
    labels = load_labels()
    if chain is None:
        return len(labels)
    return sum(1 for (chain_name, _) in labels if chain_name == chain)


def inferred_label_count(chain: str) -> int:
    """How many of a chain's labels are same-address inferences, not direct labels."""
    return sum(
        1
        for (chain_name, _), meta in load_labels().items()
        if chain_name == chain and meta.get("source") == INFERRED_LABEL_SOURCE
    )


# Labels carried over from the same address on Ethereum by
# scripts/infer_cross_chain_labels.py. They name a company on the strength of an
# inference (same key, active EOA on this chain), so they are identified under
# their own method and scored below a direct label match.
INFERRED_LABEL_SOURCE = "inferred_cross_chain_same_address"
INFERRED_LABEL_CONFIDENCE = 0.6


# --- (a) Known-label lookup — WORKS -------------------------------------------


def known_label_lookup(address: str, chain: str | None = None) -> Identification | None:
    """
    Method (a): is this address a known entity ON THIS CHAIN?

    The highest-quality signal available. An exchange's hot wallets are public
    knowledge precisely because the exchange cannot operate secretly, so a
    direct hit names the entity outright rather than inferring it.

    The chain is part of the question, not a detail: matching an Ethereum label
    against a Polygon address would invent a finding, and inventing findings is
    the single worst failure this tool has.

    Returns None when the address is unknown on that chain - the normal case,
    since most wallets in a trace are the criminal's own anonymous ones.
    """
    chain_name = (chain or DEFAULT_CHAIN).strip().lower()
    # An address that does not parse for this chain cannot match a label on it -
    # the format guard on the lookup side.
    key = addresses.try_normalize(address, chain_name)
    if key is None:
        return None
    meta = load_labels().get((chain_name, key))
    if meta is None:
        return None

    entity = str(meta.get("entity", "Unknown entity"))
    entity_type = str(meta.get("type", "unknown"))

    if meta.get("source") == INFERRED_LABEL_SOURCE:
        origin = meta.get("inferred_from") or {}
        evidence = meta.get("evidence") or {}
        return Identification(
            address=key,
            entity=entity,
            entity_type=entity_type,
            method="inferred_label",
            confidence=INFERRED_LABEL_CONFIDENCE,
            evidence=(
                f"INFERRED, not a direct label: this address is labelled {entity} on "
                f"{origin.get('chain', 'ethereum')}, and on {chain_name} it is an ordinary "
                f"account (not a contract) with {evidence.get('nonce', '?')} outgoing "
                "transactions. The same key controls the same address on every EVM chain, "
                f"so it is probably {entity} here too - but no label for {chain_name} "
                "says so."
            ),
        )

    role = meta.get("role")
    return Identification(
        address=key,
        entity=entity,
        entity_type=entity_type,
        method="known_label",
        confidence=LABEL_CONFIDENCE,
        evidence=(
            f"Label: {entity} ({entity_type}"
            + (f", {role}" if role else "")
            + f") on {chain_name}. Source: "
            + (meta.get("citation") or "not recorded")
            + "."
        ),
    )


def _as_store(graph):
    """
    Accept either a graph store or a bare NetworkX graph.

    The tracer passes a store (Neo4j or in-memory); tests and any ad-hoc
    analysis pass a DiGraph directly. Wrapping here means the identification
    logic below is written once and does not care which backend produced the
    graph - which is also what lets us prove the two backends agree.
    """
    if hasattr(graph, "wallet_count"):
        return graph
    store = graph_store.MemoryStore()
    store._g = graph  # noqa: SLF001 - deliberate adoption of the caller's graph
    return store


# --- (b) Deposit-consolidation clustering — WORKS -----------------------------


def consolidation_score(
    address: str, graph: nx.DiGraph, node: str | None = None
) -> float:
    """
    Method (b): score how much this address looks like a collection point.

    THE FINGERPRINT: an exchange gives every customer their own deposit
    address, then sweeps them all into a small number of hot wallets. The
    result is a wallet with very high fan-in - many distinct senders paying one
    recipient - which is the inverse of an ordinary personal wallet, and it is
    structural. An exchange cannot avoid it without abandoning the deposit model
    its business runs on. That is what makes the pattern worth trusting even
    when the address is not on any label list.

    Returns 0.0 to 1.0, scaled between CONSOLIDATION_MIN_SENDERS and
    CONSOLIDATION_STRONG_SENDERS. Below the minimum the score is 0.0, because a
    handful of shared senders is ordinary and flagging it would produce false
    accusations.

    LIMITATION 1 - CRIMINALS CONSOLIDATE TOO. This is the serious one, and it
    is confirmed on real data: tracing the Ronin Bridge hacker flags an address
    that 6+ traced wallets funnel 84,963 ETH into, but its outgoing transaction
    count is ~1,600 against a real Binance hot wallet's ~18,000,000. It is the
    attacker re-pooling their own split funds, not an exchange sweeping customer
    deposits - and the two produce an identical fan-in signature. So a hit from
    this method is a LEAD, never an identification, and it must never be
    reported as a named exchange. The cheap discriminator, if this needs to get
    stronger later, is outgoing transaction count: exchange hot wallets exceed
    criminal wallets by three to four orders of magnitude, at a cost of one
    extra API call per candidate.

    LIMITATION 2: the fan-in counted here is IN-GRAPH only - distinct
    senders that this particular trace happened to walk. A forward BFS is close
    to a tree, so in-degree is usually 1 and only rises where laundering paths
    re-converge. That makes a positive result meaningful but a negative one
    weak: this measures convergence within the trace, not the address's true
    global fan-in. Reading real deposit consolidation requires fetching each
    candidate's INCOMING transactions from Etherscan and counting distinct
    senders chain-wide. That is the intended upgrade, and it costs one extra
    API call per candidate.
    """
    store = _as_store(graph)
    node = node or address
    if not store.has(node):
        return 0.0

    # Distinct senders. The store collapses repeat payments between the same
    # pair into one edge, so this is a distinct-counterparty count by
    # construction. Self-loops do not count - a wallet paying itself is not a
    # third party, and both backends exclude them.
    fan_in = len(store.predecessors(node))

    if fan_in < CONSOLIDATION_MIN_SENDERS:
        return 0.0
    if fan_in >= CONSOLIDATION_STRONG_SENDERS:
        return 1.0

    span = CONSOLIDATION_STRONG_SENDERS - CONSOLIDATION_MIN_SENDERS
    return (fan_in - CONSOLIDATION_MIN_SENDERS) / span


def consolidation_fan_in(
    address: str, graph: nx.DiGraph, node: str | None = None
) -> int:
    """Distinct third-party senders into this address, within the traced graph."""
    store = _as_store(graph)
    node = node or address
    if not store.has(node):
        return 0
    return len(store.predecessors(node))


def adaptive_fan_in_floor(graph: nx.DiGraph, percentile: float = 0.95, chain: str | None = None) -> int:
    """
    The fan-in a node must beat to count as UNUSUAL *for this particular graph*.

    WHY a fixed count is not enough: in a sparse trace (a thin laundering chain)
    six converging senders is remarkable. In a dense trace through high-volume
    infrastructure it is completely ordinary - measured on a real 402-node,
    1060-edge trace, a flat threshold of six flagged 34 separate addresses,
    which is not a finding, it is noise. Consolidation is a claim that an
    address is an OUTLIER, so the bar has to be read off the graph it sits in.
    """
    store = _as_store(graph)
    if store.wallet_count() == 0:
        return CONSOLIDATION_FLAG_SENDERS
    # PER CHAIN. Measured over the whole multi-chain graph, a large Ethereum leg
    # set the bar for a small Polygon leg. With `chain`, only that chain's
    # wallets define what is unusual on it.
    try:
        degrees = sorted(store.in_degrees(chain=chain)) if chain else sorted(store.in_degrees())
    except TypeError:  # a store without per-chain support
        degrees = sorted(store.in_degrees())
    if not degrees:
        return CONSOLIDATION_FLAG_SENDERS
    index = int(percentile * (len(degrees) - 1))
    return degrees[index]


def consolidation_identify(
    address: str, graph: nx.DiGraph, node: str | None = None, chain: str | None = None
) -> Identification | None:
    """
    Wrap the consolidation pattern into an Identification, or None if too weak.

    Two gates, both of which must pass. The absolute floor
    (CONSOLIDATION_FLAG_SENDERS) stops us calling three senders a pattern. The
    adaptive floor stops us calling an ordinary node in a dense graph an
    outlier. The gates are sender COUNTS, not the normalised score: scoring is
    for expressing confidence, but the decision to make an accusation at all
    should rest on a number an investigator can check by eye.

    `node` is the graph key for this wallet, which differs from `address` once a
    trace crosses a chain: the same address on two chains is two different
    wallets and gets two different nodes. It defaults to `address`, so a
    single-chain caller is unaffected.
    """
    fan_in = consolidation_fan_in(address, graph, node=node)
    if fan_in < CONSOLIDATION_FLAG_SENDERS:
        return None
    floor = adaptive_fan_in_floor(graph, chain=chain)
    if fan_in < floor:
        return None

    score = consolidation_score(address, graph, node=node)
    confidence = CONSOLIDATION_MAX_CONFIDENCE * max(score, 0.5)

    return Identification(
        # Already the canonical graph key; lowercasing it would corrupt a Tron
        # or legacy Bitcoin address.
        address=address.strip(),
        entity="Unknown exchange (consolidation pattern)",
        # NOT "exchange" - we have not named anyone. This is a behavioural
        # suspicion, and the label keeps that distinction visible downstream.
        entity_type="suspected_exchange",
        method="consolidation",
        confidence=confidence,
        evidence=(
            f"{fan_in} distinct traced wallets funnel into this address "
            f"(fan-in score {score:.2f}; unusual for this chain's part of the graph, "
            f"where the 95th percentile is {floor}), matching the "
            f"deposit-consolidation pattern exchanges produce when sweeping "
            f"customer deposits. UNCONFIRMED - a criminal re-pooling their own "
            f"split funds produces the same shape."
        ),
        fan_in={"subgraph_senders": fan_in, "subgraph_floor": floor},
    )


def apply_global_fan_in(ident: Identification, chain_wide: dict | None) -> Identification | None:
    """
    Decide a subgraph consolidation candidate on its CHAIN-WIDE sender count.

    `chain_wide` is {"senders": n, "complete": bool, ...} from the tracer, or
    None when the count could not be obtained. Returns:
      * None - fewer than CONSOLIDATION_GLOBAL_MIN_SENDERS distinct senders ever
        paid this address: it is a reconvergence point, not a collection point;
      * the identification, scored on the chain-wide number, with both figures;
      * where the count could not be obtained, the identification at reduced
        confidence, saying it rests on subgraph structure only. Never the old
        behaviour silently.
    """
    sub = (ident.fan_in or {}).get("subgraph_senders", 0)
    if chain_wide is None or chain_wide.get("senders") is None:
        reason = (chain_wide or {}).get("error") or "the client cannot count senders chain-wide"
        return replace(
            ident,
            confidence=round(ident.confidence * CONSOLIDATION_SUBGRAPH_ONLY_FACTOR, 4),
            fan_in={**(ident.fan_in or {}), "global_checked": False, "chain_senders": None,
                    "global_note": reason},
            evidence=ident.evidence + (
                f" The chain-wide sender count could not be obtained ({reason}), so this rests on "
                "subgraph structure only and its confidence is halved."
            ),
        )

    # The calibrated measure: distinct senders of non-dust value in followed
    # assets. Older callers that only supply raw senders fall back to those.
    n = int(chain_wide.get("value_senders", chain_wide["senders"]))
    complete = bool(chain_wide.get("complete"))
    if n < CONSOLIDATION_GLOBAL_MIN_SENDERS:
        return None
    out_rows = chain_wide.get("out_rows")
    per_out = (n / out_rows) if out_rows else None
    if per_out is not None and per_out < CONSOLIDATION_MIN_SENDERS_PER_OUT_TX:
        return None
    span = CONSOLIDATION_GLOBAL_STRONG_SENDERS - CONSOLIDATION_GLOBAL_MIN_SENDERS
    strength = min(1.0, max(0.0, (n - CONSOLIDATION_GLOBAL_MIN_SENDERS) / span))
    bound = "exactly" if complete else "at least"
    return replace(
        ident,
        confidence=round(CONSOLIDATION_MAX_CONFIDENCE * max(strength, 0.5), 4),
        fan_in={**(ident.fan_in or {}), "global_checked": True, "chain_senders": n,
                "chain_senders_raw": chain_wide.get("senders"),
                "chain_out_rows": out_rows, "senders_per_out_tx": None if per_out is None else round(per_out, 4),
                "chain_senders_complete": complete, "rows_read": chain_wide.get("rows")},
        evidence=(
        f"{sub} distinct wallets in this trace and {bound} {n} distinct addresses chain-wide have "
        f"sent non-dust value to this address" + ("" if complete else
                                   " (counted from its most recent transactions before the as-of height)")
        + ", matching the deposit-consolidation pattern exchanges produce when sweeping customer "
        "deposits. UNCONFIRMED - no label names it."
        ),
    )


# --- (c) Behavioral classifier — STUB, future scope ---------------------------


def behavioral_classifier(address: str, graph: nx.DiGraph) -> None:
    """
    Method (c): classify a wallet from its transaction behaviour. NOT IMPLEMENTED.

    TODO (future scope). The intended approach: extract per-wallet features
    that separate institutional wallets from personal ones - transaction
    frequency, balance stability, round-number amounts, gas-price strategy,
    hour-of-day activity spread, in/out ratio, lifetime - and train a small
    supervised classifier on the labelled addresses in labels.json as ground
    truth.

    WHY IT WOULD HELP: it is the only method that can flag an exchange wallet
    that appears on no label list, which is exactly the gap for regional VASPs
    and freshly rotated hot wallets.

    WHY IT IS DEFERRED: it needs a labelled training set far larger than our
    starter file, and a weak classifier here produces confident false
    attributions - the most damaging error this tool can make in a law
    enforcement context. Methods (a) and (b) are deliberately prioritised.

    Always returns None, so callers can wire it in now and it stays inert.
    """
    return None


# --- (d) Co-spend clustering — STUB, not applicable to Ethereum ---------------


def cospend_cluster(address: str, graph: nx.DiGraph) -> None:
    """
    Method (d): cluster addresses by common spending. NOT IMPLEMENTED.

    TODO (future scope), and a note on why it is listed at all: co-spend (or
    "common input ownership") clustering is the workhorse of BITCOIN forensics.
    When one Bitcoin transaction spends several UTXOs as inputs, one private
    key signed for all of them, so they almost certainly share an owner.

    It does NOT transfer to Ethereum. Ethereum uses an account model, not
    UTXOs: a transaction has exactly one sender, so there is no multi-input
    event to infer shared ownership from. The Ethereum-appropriate substitutes
    are gas-funding analysis (one wallet seeding many with initial gas) and
    deposit-address reuse - both closer to method (b).

    Since this project is Ethereum-only, this method is N/A by design rather
    than merely unfinished. Always returns None.
    """
    return None


# --- Combined entry point -----------------------------------------------------


def identify(
    address: str, graph: nx.DiGraph, chain: str | None = None, node: str | None = None
) -> Identification | None:
    """
    Run the available methods against one address, best evidence first.

    Order matters: a label match names an actual company and outranks any
    statistical pattern, so it is checked first and returned immediately. The
    consolidation heuristic only speaks when the label list is silent.

    `address` is the bare wallet address, which is what labels are keyed by. `node`
    is the graph key for it, supplied separately because a trace that crosses a
    chain stores the same address on two chains as two distinct nodes. Defaults to
    `address`, so single-chain callers are unaffected.

    Returns None when nothing recognises the address - the expected outcome for
    the criminal's own wallets, and the reason the trace keeps walking.
    """
    hit = known_label_lookup(address, chain=chain)
    if hit is not None:
        return hit

    # Deliberately chain-agnostic: fan-in is a shape in the traced graph, and
    # that graph is already confined to one chain by the tracer.
    hit = consolidation_identify(address, graph, node=node, chain=chain)
    if hit is not None:
        return hit

    # Stubs, wired in so the pipeline is complete. Both return None today.
    if behavioral_classifier(address, graph) is not None:  # pragma: no cover
        pass
    if cospend_cluster(address, graph) is not None:  # pragma: no cover
        pass

    return None


def is_terminal(ident: Identification | None) -> bool:
    """
    Should the trace STOP expanding a wallet with this identification?

    Yes in three cases, each for its own reason:

      * exchange / suspected_exchange - we have arrived. This is the answer the
        investigation wanted, and walking past it would just enumerate the
        exchange's own internal shuffling.

      * mixer - the trail is broken by design. A mixer pool's outputs are
        deliberately unlinkable from its inputs, so following its outgoing
        transfers produces paths that look like evidence but are not. Stopping
        is the honest choice, and it also avoids expanding a wallet with tens of
        thousands of counterparties.

      * bridge - the funds have left Ethereum for another chain. We are
        Ethereum-only by scope, so there is nothing further to follow here.

    In all three cases the node is still recorded and flagged; only expansion
    stops.
    """
    if ident is None:
        return False
    return ident.entity_type in {"exchange", "suspected_exchange", "mixer", "bridge"}
