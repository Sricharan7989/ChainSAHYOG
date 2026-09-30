# API Routes Catalog

This document details all HTTP endpoints exposed by the ChainSAHYOG FastAPI backend (`backend/app/routes.py`).

---

## Route Overview

| Endpoint | HTTP Method | Function | Primary Purpose |
| :--- | :---: | :--- | :--- |
| **[`/`](#1-get-)** | `GET` | `root()` | Service metadata, liveness check, and API discovery. |
| **[`/health`](#2-get-health)** | `GET` | `health()` | System liveness probe; reports active graph backend and supported chains. |
| **[`/trace`](#3-get-trace)** | `GET` | `trace_address()` | Execute or replay a forward blockchain money-flow trace. |
| **[`/report`](#4-get-report)** | `GET` | `trace_report()` | Generate and download an investigation-ready forensic PDF report. |
| **[`/demos`](#5-get-demos)** | `GET` | `list_demos()` | List pre-recorded demonstration traces available for instant playback. |

---

## Route Specifications

### 1. `GET /`

Returns human- and machine-readable service metadata. Useful for verifying that the API is up without triggering external requests.

- **Authentication**: None
- **Request Headers**: None
- **Query Parameters**: None

#### Responses
- **`200 OK`**:
```json
{
  "service": "vasp-attribution-engine",
  "version": "0.1.0",
  "live_trace_available": true,
  "graph": "memory",
  "chains": {
    "default": 1,
    "supported": [
      {
        "chain_id": 1,
        "slug": "ethereum",
        "name": "Ethereum",
        "native": "ETH",
        "explorer": "https://etherscan.io"
      },
      {
        "chain_id": 137,
        "slug": "polygon",
        "name": "Polygon",
        "native": "POL",
        "explorer": "https://polygonscan.com"
      },
      {
        "chain_id": 56,
        "slug": "bnb",
        "name": "BNB Chain",
        "native": "BNB",
        "explorer": "https://bscscan.com",
        "requires_paid_plan": true
      },
      {
        "chain_id": 42161,
        "slug": "arbitrum",
        "name": "Arbitrum One",
        "native": "ETH",
        "explorer": "https://arbiscan.io"
      }
    ]
  },
  "docs": "/docs"
}
```

---

### 2. `GET /health`

Liveness and dependency health probe. Used by frontend health checks and container orchestrators.

- **Authentication**: None
- **Query Parameters**: None

#### Health Semantics
- `graph`: Reports either `"neo4j"` (connected to Neo4j container) or `"memory"` (using in-process NetworkX). `"memory"` is considered a completely **healthy state**, as traces return identical results on both engines.

#### Responses
- **`200 OK`**:
```json
{
  "status": "ok",
  "graph": "memory",
  "chains": {
    "default": 1,
    "supported": [...]
  }
}
```

---

### 3. `GET /trace`

The primary forensic investigative endpoint. Traces money forward from a suspect EVM address across intermediary hops until an exchange is reached or trace boundaries are met.

- **Authentication**: None
- **Query Parameters**:

| Parameter | Type | Required | Default | Validation / Constraints | Description |
| :--- | :---: | :---: | :---: | :--- | :--- |
| `address` | `string` | **Yes** | — | Valid EVM address (`^0x[a-fA-F0-9]{40}$`) | Suspect wallet address to begin forward trace from. |
| `max_depth` | `integer` | No | `4` | `1 <= max_depth <= 6` | Maximum number of forward hops to traverse. |
| `dust_threshold` | `float` | No | `0.001` | `>= 0.0` | Minimum native transfer amount (ETH/POL/BNB) to follow. |
| `mode` | `string` | No | `"auto"` | `auto`, `live`, `cache` | Execution mode (see table below). |
| `chain_id` | `integer` | No | `1` | Supported: `1`, `137`, `56`, `42161` | EVM network identifier to execute trace upon. |
| `save` | `boolean` | No | `false` | `true`, `false` | When `true`, saves live trace to on-disk replay cache. |

#### Execution Modes (`mode`)
- **`auto` (Default)**: If a pre-recorded trace exists in `data/cache/` for this address and chain, return it immediately (0ms latency). Otherwise, execute a live trace via Etherscan.
- **`live`**: Bypass all caches and force a live multi-hop query against the public blockchain.
- **`cache`**: Only return pre-recorded traces. Returns `404 Not Found` if no recording exists.

#### Responses
- **`200 OK`**: Returns full trace payload containing Cytoscape graph nodes/edges, attribution summary, clusters, typologies, and taint accounting. *(See [API.md](./API.md) for full JSON schema).*
- **`400 Bad Request`**: Malformed EVM address (not 40 hex chars after 0x) or invalid parameter value.
- **`404 Not Found`**: `mode=cache` specified but no recording exists on disk for that address/chain.
- **`422 Unprocessable Entity`**: Unsupported `chain_id` (e.g. `chain_id=999`).
- **`502 Bad Gateway`**: Upstream Etherscan API failure, network timeout, or rate-limit exhaustion.
- **`503 Service Unavailable`**: `ETHERSCAN_API_KEY` is not configured in `backend/.env` and a live trace was attempted.

---

### 4. `GET /report`

Generates an official, court-ready forensic PDF report summarizing the findings of `/trace`.

- **Authentication**: None
- **Query Parameters**: Identical to `GET /trace` (`address`, `max_depth`, `dust_threshold`, `mode`, `chain_id`).

#### Behavior & Caching
- Operates through the shared `_run_or_replay()` helper.
- **In-Memory Cache**: If the investigator just viewed the trace in the UI, `/report` reuses the in-memory payload from that trace. It generates the PDF in under 100ms without touching the blockchain or external APIs.
- The document content is guaranteed to never contradict what appeared on the investigator's screen.

#### Responses
- **`200 OK`**:
  - `Content-Type`: `application/pdf`
  - `Content-Disposition`: `attachment; filename="ChainSAHYOG-Report-0x62425cd6.pdf"`
- **`400`, `404`, `422`, `502`, `503`**: Identical error conditions to `GET /trace`.

---

### 5. `GET /demos`

Lists all pre-recorded demonstration traces available for zero-latency, fail-safe pitch demonstrations.

- **Authentication**: None
- **Query Parameters**: None

#### Responses
- **`200 OK`**:
```json
{
  "demos": [
    {
      "address": "0x62425cd6bdcb6bfe51558ea465b063486b70dc9f",
      "chain": "ethereum",
      "chain_id": 1,
      "recorded_at": "2026-09-30T19:42:10Z",
      "summary": {
        "found": true,
        "exchange": "Binance",
        "hop_distance": 2,
        "confidence_score": 95
      }
    }
  ]
}
```
