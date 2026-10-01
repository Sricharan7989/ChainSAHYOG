# Deployment & Configuration Guide

This document details how to configure, deploy, and operate the ChainSAHYOG backend.

---

## 1. Environment Variables Reference

API keys and operational toggles are defined in `backend/.env`. A template is provided at `backend/.env.example`.

### Core Secrets & API Keys
| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `ETHERSCAN_API_KEY` | **Yes** (for live) | `""` | Free tier API key from [Etherscan](https://etherscan.io/myapikey). Supports multichain via V2 endpoint. |
| `ALCHEMY_API_KEY` | No | `""` | Optional Alchemy key for enhanced token transfers. |

### Graph Database (Neo4j)
| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `NEO4J_URI` | No | `bolt://localhost:7687` | Bolt protocol connection URL to Neo4j. |
| `NEO4J_USER` | No | `neo4j` | Neo4j database username. |
| `NEO4J_PASSWORD` | No | `vasptrace2026` | Neo4j database password. |
| `NEO4J_DATABASE` | No | `neo4j` | Target Neo4j database name. |
| `NEO4J_DISABLED` | No | `0` | Set to `1` or `true` to force in-memory NetworkX engine. |

### Token & Tracing Tunables
| Variable | Default | Description |
| :--- | :---: | :--- |
| `TOKEN_ALLOWLIST` | `None` (All) | Comma-separated list of symbols to follow (e.g. `USDT,USDC`). Unset follows all verified tokens. |
| `DUST_THRESHOLD_TOKEN` | `1.0` | Default dust floor for tokens lacking explicit threshold. |
| `TYPOLOGY_TAINTED_ONLY` | `1` | Restrict typology detectors to wallets carrying suspect taint (`1` enabled, `0` disabled). |
| `PEEL_MIN_LINKS` | `3` | Minimum consecutive links to classify as a peel chain. |
| `PEEL_DOMINANT_SHARE` | `0.80` | Minimum share of value moving to next hop in a peel link (80%). |
| `LAYERING_MAX_DWELL_SEC`| `3600` | Maximum dwell time per wallet for layering classification (1 hr). |
| `STRUCTURING_MAX_CV` | `0.10` | Maximum Coefficient of Variation for structuring fan-out amounts (10%). |
| `TYPOLOGY_MAX_REPORTED` | `15` | Maximum number of typology detections to serialize in trace payload. |

---

## 2. Local Development Quickstart

ChainSAHYOG manages dependencies and virtual environments with [`uv`](https://github.com/astral-sh/uv).

### Step 1: Clone & Configure
```bash
cd backend
cp .env.example .env
# Edit .env and supply your ETHERSCAN_API_KEY
```

### Step 2: Install Dependencies
```bash
uv sync
```

### Step 3: Run the Development Server
```bash
uv run uvicorn main:app --reload --port 8000
```
- **API Base**: `http://localhost:8000`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **Alternative ReDoc**: `http://localhost:8000/redoc`

---

## 3. Docker Compose Setup (Neo4j Graph Database)

Neo4j is optional. If the container is stopped or offline, the engine seamlessly uses its in-memory NetworkX engine without crashing or altering trace results.

To run Neo4j for persistent cross-case graph storage:

```bash
# Start Neo4j in background
docker compose up -d

# View live container logs
docker compose logs -f neo4j

# Stop Neo4j
docker compose down
```

### Accessing the Neo4j Browser
- **URL**: `http://localhost:7474`
- **Username**: `neo4j`
- **Password**: `vasptrace2026` (or whatever was set in `docker-compose.yml`)

---

## 4. Running Backend Verification Tests

The backend test suite consists of 8 comprehensive verification modules validating backends, token allowlists, taint math, typologies, and tracer logic.

Execute tests using `uv run python -m`:

```bash
cd backend

# 1. Tracing engine & BFS walk
uv run python -m tests.test_tracer

# 2. Token allowlist, contract pinning, and decimals
uv run python -m tests.test_tokens

# 3. FIFO taint tracking & chronological replay
uv run python -m tests.test_taint

# 4. Laundering typology detectors
uv run python -m tests.test_typologies

# 5. Entity resolution & clustering
uv run python -m tests.test_clustering

# 6. Exchange identification (known labels & consolidation)
uv run python -m tests.test_identify

# 7. Additive confidence scoring
uv run python -m tests.test_scoring

# 8. Dual graph backend agreement (Neo4j vs NetworkX)
uv run python -m tests.test_backends_agree
```
