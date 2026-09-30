# ChainSAHYOG — Backend Engine

> Crypto Wallet → VASP Attribution Engine for India's SAHYOG / I4C Cybercrime Workflow (SIH26182).

The backend traces stolen cryptocurrency forward from a suspect address through unhosted intermediate wallets, cross-chain bridges, and mixers until it reaches a centralized Virtual Asset Service Provider (VASP), providing the actionable chokepoint for lawful data requests.

---

## Quick Start

```bash
# 1. Setup environment configuration
cp .env.example .env
# Edit .env and supply your ETHERSCAN_API_KEY

# 2. Install dependencies via uv
uv sync

# 3. Start development server
uv run uvicorn main:app --reload --port 8000
```

- **Interactive API Documentation (Swagger)**: `http://localhost:8000/docs`
- **Alternative Documentation (ReDoc)**: `http://localhost:8000/redoc`

---

## Package Structure

```
backend/
├── main.py                    # Entry point: uvicorn main:app
├── app/                       # FastAPI application & configuration
│   ├── __init__.py            #   App factory, CORS, and lifecycle management
│   ├── config.py              #   Central configuration, secrets, token allowlists
│   └── routes.py              #   API routes (/trace, /report, /health, /demos, /)
├── core/                      # Analytical & forensic modules
│   ├── __init__.py
│   ├── tracer.py              #   Forward BFS multi-asset tracing engine
│   ├── identify.py            #   Exchange identification (known labels & consolidation)
│   ├── clustering.py          #   Entity resolution & hub grouping
│   ├── taint.py               #   FIFO value taint tracking & chronological replay
│   ├── typologies.py          #   Laundering pattern recognition (peel chains, layering, structuring)
│   └── scoring.py             #   Explainable, additive confidence scoring
├── services/                  # Data layer & external integrations
│   ├── __init__.py
│   ├── etherscan.py           #   Etherscan API V2 multichain client & cache
│   ├── graph_store.py         #   Dual-engine graph storage (Neo4j + NetworkX)
│   ├── replay.py              #   Recorded demo replay & cache management
│   └── report.py              #   Forensic PDF report generation (ReportLab)
├── scripts/                   # Operational CLI utilities
│   ├── __init__.py
│   ├── import_ofac.py         #   Ingest OFAC SDN cryptocurrency sanctions list
│   ├── import_tagpacks.py     #   Ingest GraphSense TagPacks entity labels
│   └── record_demo.py         #   Record a trace snapshot for instant demo replay
└── tests/                     # Comprehensive test suites
    ├── test_tracer.py         #   BFS traversal & guard rails
    ├── test_tokens.py         #   Contract-pinned token allowlists & decimals
    ├── test_taint.py          #   FIFO taint accounting & tie breaking
    ├── test_typologies.py     #   Laundering pattern rules
    ├── test_clustering.py     #   Entity clustering & hop distance rules
    ├── test_identify.py       #   Label matching & consolidation heuristics
    ├── test_scoring.py        #   Explainable confidence scoring
    └── test_backends_agree.py #   Dual backend agreement (Neo4j vs NetworkX)
```

---

## Comprehensive Documentation

For complete technical specifications, mathematical definitions, and API schemas, refer to the **[`docs/`](../docs/)** directory in the repository root:

- **[Master Documentation Index](../docs/README.md)**
- **[System Architecture & Dual Graph Engine](../docs/ARCHITECTURE.md)**
- **[API Routes Catalog](../docs/ROUTES.md)**
- **[Exhaustive API Specification & JSON Schemas](../docs/API.md)**
- **[Tracing Engine & Multi-Asset Flow Analysis](../docs/TRACING_ENGINE.md)**
- **[Entity Resolution & Clustering](../docs/ENTITY_RESOLUTION.md)**
- **[FIFO Taint Tracking & Chronological Replay](../docs/TAINT_TRACKING.md)**
- **[Laundering Typology Detection](../docs/TYPOLOGIES.md)**
- **[Explainable Confidence Scoring](../docs/CONFIDENCE_SCORING.md)**
- **[Data Sources, Labels, & OFAC Sanctions](../docs/DATA_SOURCES.md)**
- **[Deployment & Configuration Guide](../docs/DEPLOYMENT_AND_CONFIG.md)**

---

## Running Verification Tests

```bash
uv run python -m tests.test_tracer
uv run python -m tests.test_tokens
uv run python -m tests.test_taint
uv run python -m tests.test_typologies
uv run python -m tests.test_clustering
uv run python -m tests.test_identify
uv run python -m tests.test_scoring
uv run python -m tests.test_backends_agree
```
