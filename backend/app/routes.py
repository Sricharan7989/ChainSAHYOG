"""
API routes for the VASP Attribution Engine.

Endpoints:
  /         - friendly landing page
  /health   - liveness probe
  /trace    - run (or replay) a forward trace and return the finding
  /report   - the same finding as an investigation-ready PDF
  /demos    - recorded traces available for instant replay
"""

from fastapi import APIRouter, HTTPException, Query, Request, Response

from app import config
from core import tracer
from services import graph_store, replay, report
from core import addresses, identify
from services.etherscan import EtherscanError

router = APIRouter()

# Most recent live payload per address, for this process only. Makes
# "trace, then download the PDF" instant instead of re-walking the chain.
_RECENT: dict[tuple[str, str], dict] = {}


@router.get("/health")
def health() -> dict:
    """
    Liveness probe — also what the frontend pings to confirm the backend is up.

    Reports which graph backend is live. Neo4j is optional: "memory" here is a
    healthy state, not a failure, and traces return identical results either way.

    `chains.readable` is reported per chain for the same reason. A chain whose
    explorer API the configured key does not cover cannot be traced, and the
    UI has to be able to say "we cannot read BNB Chain with this key" rather
    than discover it as a 502 after an investigator has started work.
    """
    return {
        "status": "ok",
        "graph": graph_store.status(),
        "chains": {
            "default": config.DEFAULT_CHAIN_ID,
            "supported": config.supported_chains(),
            "readable": {
                chain["slug"]: config.chain_readable(chain["chain_id"])
                for chain in config.supported_chains()
            },
        },
        # Committed (redistributable) and local (not redistributable) label
        # counts, reported separately, with the evidence-tier mix.
        "labels": identify.label_stats(),
    }


@router.get("/trace")
async def trace_address(
    address: str = Query(..., description="Suspect Ethereum address (0x...)"),
    max_depth: int = Query(
        config.MAX_TRACE_DEPTH, ge=1, le=6, description="How many hops to follow forward"
    ),
    dust_threshold: float = Query(
        config.DUST_THRESHOLD_ETH, ge=0.0, description="Ignore transfers below this many ETH"
    ),
    mode: str = Query(
        "auto",
        pattern="^(auto|live|cache)$",
        description="auto = replay if recorded else live; live = always fresh; cache = recorded only",
    ),
    chain_id: int = Query(
        config.DEFAULT_CHAIN_ID,
        description="EVM chain to trace: 1 Ethereum, 137 Polygon, 56 BNB Chain, 42161 Arbitrum",
    ),
    save: bool = Query(False, description="Record this result for instant replay later"),
    as_of_block: int | None = Query(
        None, ge=0,
        description="Pin the trace to this block height on the starting chain. Omitted: the "
        "chain head when the trace starts. Re-running at the same height reproduces the result.",
    ),
) -> dict:
    """
    Follow the money forward from a suspect wallet and return the flow graph.

    Returns a flat `nodes` + `edges` pair (Cytoscape-ready), `hops` in the order
    the walk made them, and the attribution results:

      summary       - the headline finding for the investigator panel.
      attributions  - every recognised address, nearest hop first.
      exchanges     - the actionable subset: VASPs that can be served a request.
      flags         - mixers and bridges crossed on the way.

    Confidence is never 1.0. `method` on every attribution says whether the name
    came from a published label or from a behavioural pattern, because those
    justify very different actions.

    max_depth is capped at 6 by the route, not by taste: out-degree compounds,
    so each extra hop multiplies both the graph size and the API calls.
    """
    payload = await _run_or_replay(
        address,
        max_depth=max_depth,
        dust_threshold=dust_threshold,
        mode=mode,
        chain_id=chain_id,
        as_of_block=as_of_block,
    )

    if save and payload.get("source") != "cache":
        replay.save_trace(payload)
        payload["recorded"] = True

    return payload


async def _run_or_replay(
    address: str,
    *,
    max_depth: int,
    dust_threshold: float,
    mode: str,
    chain_id: int = config.DEFAULT_CHAIN_ID,
    prefer_recent: bool = False,
    as_of_block: int | None = None,
) -> dict:
    """
    Produce a trace payload, from the recording if there is one, else live.

    `prefer_recent` is for /report. The PDF must describe the trace the
    investigator was looking at, so the in-memory result of that exact trace
    (same address, chain, depth and dust threshold) wins in EVERY mode. It used
    to be consulted only in auto mode, so a report requested after a live trace
    re-walked the chain - taking minutes, and able to print figures that differ
    from the screen.

    Shared by /trace and /report so a report can never disagree with the trace
    the investigator was looking at when they asked for it. Also keeps the most
    recent result of each address in memory, so generating the PDF straight
    after a trace costs nothing rather than re-walking the chain.
    """
    # 422 for an unsupported chain: it is an unprocessable parameter value, the
    # same class of error FastAPI raises for a bad max_depth. Resolved FIRST,
    # because what counts as a valid address depends on the chain.
    try:
        chain = config.chain(chain_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    key = addresses.try_normalize(address, chain["slug"])
    if key is None:
        other = addresses.families_for(address)
        hint = f" It parses as a {', '.join(sorted(other))} address." if other else ""
        raise HTTPException(
            status_code=400,
            detail=f"'{address}' is not a valid {addresses.describe(chain['slug'])} address "
            f"for {chain['name']}.{hint}",
        )
    # The in-process map is keyed by chain too: the same address on another
    # network is a different trace and must not be served from the wrong one.
    # (The on-disk cache does the same, inside replay._path_for.)
    recent_key = (chain["slug"], key, as_of_block)

    # The exact trace that was on screen, if this process produced it. Matched on
    # depth AND dust threshold, since either changes the result.
    recent = _RECENT.get(recent_key)
    same_params = (
        recent is not None
        and recent["params"]["max_depth"] == max_depth
        and recent["params"].get("dust_threshold_eth") == dust_threshold
    )
    if prefer_recent and same_params:
        return recent

    if mode in ("auto", "cache"):
        cached = replay.load_trace(key, chain=chain["slug"], as_of_block=as_of_block)
        if cached is not None:
            return cached
        if mode == "cache":
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No recorded trace for {key} on {chain['name']}"
                    + (f" at block {as_of_block}" if as_of_block is not None else "") + ". "
                    f"Run it live first, or use mode=auto."
                ),
            )

    # In-memory result from earlier in this process.
    if mode == "auto" and same_params:
        return recent

    # Tron is read keyless through TronGrid; every other chain needs the
    # Etherscan key.
    if chain.get("family") != "tron" and not config.has_etherscan_key():
        raise HTTPException(
            status_code=503,
            detail="ETHERSCAN_API_KEY is not configured in backend/.env - cannot run a live trace.",
        )

    try:
        result = await tracer.trace(
            address,
            max_depth=max_depth,
            dust_threshold=dust_threshold,
            chain_id=chain["chain_id"],
            as_of_block=as_of_block,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EtherscanError as exc:
        # Upstream problem, not the investigator's. 502 keeps that distinction
        # visible in the frontend instead of looking like an empty result.
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    payload = tracer.to_json(result)
    payload["source"] = "live"
    _RECENT[recent_key] = payload
    return payload


@router.get("/report")
async def trace_report(
    address: str = Query(..., description="Suspect Ethereum address (0x...)"),
    max_depth: int = Query(config.MAX_TRACE_DEPTH, ge=1, le=6),
    dust_threshold: float = Query(config.DUST_THRESHOLD_ETH, ge=0.0),
    mode: str = Query("auto", pattern="^(auto|live|cache)$"),
    chain_id: int = Query(config.DEFAULT_CHAIN_ID),
    as_of_block: int | None = Query(None, ge=0),
):
    """
    The same finding as /trace, rendered as an investigation-ready PDF.

    Served as an attachment so the browser saves it under a filename an
    investigator can file without renaming. Uses the identical payload /trace
    returns, so the document can never contradict what was on screen.
    """
    payload = await _run_or_replay(
        address,
        max_depth=max_depth,
        dust_threshold=dust_threshold,
        mode=mode,
        chain_id=chain_id,
        prefer_recent=True,
        as_of_block=as_of_block,
    )

    pdf = report.build_report(payload)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{report.filename_for(payload["start_address"])}"'
        },
    )


@router.get("/demos")
def list_demos() -> dict:
    """
    Recorded traces available for instant replay.

    The frontend uses this to offer demo addresses that cannot fail on stage,
    while any other address still runs live.
    """
    return {"demos": replay.list_cached()}


@router.get("/")
def root(request: Request) -> dict:
    """Friendly landing response so a bare localhost:8000 visit isn't a 404."""
    return {
        "service": "vasp-attribution-engine",
        "version": request.app.version,
        # Reports only WHETHER a key is configured, never the key itself.
        "live_trace_available": config.has_etherscan_key(),
        "graph": graph_store.status(),
        "chains": {
            "default": config.DEFAULT_CHAIN_ID,
            "supported": config.supported_chains(),
        },
        "docs": "/docs",
    }
