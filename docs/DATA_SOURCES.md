# Data Sources & Ingestion Pipelines

This document details external data integrations, entity registries, and automated ingestion scripts used by ChainSAHYOG.

---

## 1. Etherscan API V2 Multichain Client

Primary blockchain transaction history is retrieved via Etherscan API V2 (`backend/services/etherscan.py`).

### Key Design Principles

1. **Unified Multichain Endpoint**:
   - ChainSAHYOG utilizes Etherscan V2 (`https://api.etherscan.io/v2/api`).
   - A single API key serves Ethereum, Polygon, BNB Chain, and Arbitrum One by passing the `chainid` parameter on every request.
2. **Process-Lifetime Memory Cache**:
   - In money laundering trails, funds frequently loop, cycle, and re-converge on common intermediary addresses.
   - Without caching, a wallet touched by 5 different paths would trigger 5 redundant Etherscan requests.
   - `services/etherscan.py` maintains an in-memory dictionary keyed by `(chain_id, address)`. Wallets are fetched at most once per server lifetime.
3. **Serial Throttling (250ms Delay)**:
   - The Etherscan free tier allows a maximum of 5 requests per second.
   - The client enforces a 250ms delay between consecutive requests, guaranteeing an effective rate of ~4 calls/sec. This ensures the engine never triggers HTTP 429 rate-limit bans mid-trace.
4. **Etherscan Error Model Handling**:
   - Etherscan returns HTTP 200 status codes even on failures (e.g. rate limit trips or query errors), reporting errors inside the JSON body via `"status": "0"` and `"message": "NOTOK"`.
   - The client inspects the JSON payload structure rather than relying on HTTP response status codes, raising `EtherscanError` when upstream issues occur.
5. **Data Filtering**:
   - Automatically discards failed transactions, contract deployments, self-sends, and non-allowlisted zero-value calls.

---

## 2. Entity Labels Registry (`data/labels.json`)

The known-labels database maps EVM addresses to verified institutions and legal classifications.

### Label Schema
```json
{
  "0x28c6c06298d514db089934071355e5743bf21d60": {
    "name": "Binance",
    "type": "exchange",
    "chain": "ethereum",
    "source": "etherscan_public"
  },
  "0x1da5821544e25c636c1417ba96ade4cf6d2f9b5a": {
    "name": "Tornado.Cash: Router",
    "type": "mixer",
    "chain": "ethereum",
    "source": "graphsense_tagpacks"
  },
  "0x098b716b8aaf21512996dc57eb0615e2383e2f96": {
    "name": "Lazarus Group",
    "type": "sanctioned",
    "chain": "ethereum",
    "source": "ofac_sdn"
  }
}
```

### Entity Classifications
- `exchange`: Centralized exchanges holding KYC records (e.g. Binance, Coinbase, WazirX, OKX).
- `mixer`: Obfuscation protocols designed to break chain-of-custody (e.g. Tornado Cash).
- `bridge`: Cross-chain bridge contracts (e.g. Across, Stargate, Arbitrum Bridge).
- `sanctioned`: State-sponsored or illicit addresses designated on international sanctions lists.

---

## 3. Automated Ingestion Scripts (`backend/scripts/`)

### A. OFAC Sanctions Ingestion (`scripts/import_ofac.py`)
- **Source**: U.S. Department of the Treasury Office of Foreign Assets Control (OFAC) Specially Designated Nationals (SDN) XML feed.
- **Functionality**:
  1. Downloads the latest official SDN list from the U.S. Treasury portal.
  2. Parses `<digitalCurrencyAddressRecord>` nodes across Bitcoin, Ethereum, and EVM assets.
  3. Formats entries and merges them into `data/labels.json` under `type: "sanctioned"`.
- **Usage**:
  ```bash
  uv run python -m scripts.import_ofac
  ```

---

### B. GraphSense TagPacks Importer (`scripts/import_tagpacks.py`)
- **Source**: GraphSense public TagPacks repository (academic and open-source blockchain intelligence tags).
- **Functionality**:
  1. Parses TagPack YAML schema definitions.
  2. Resolves entity identities, actor categories, and confidence levels.
  3. Merges verified exchange, mixer, and bridge tags into `data/labels.json`.
- **Usage**:
  ```bash
  uv run python -m scripts.import_tagpacks --dry-run
  ```

---

### C. Demo Trace Recording (`scripts/record_demo.py`)
- **Purpose**: Live demonstrations before magistrates, evaluators, or police supervisors must never fail due to intermittent Wi-Fi or API outages.
- **Functionality**:
  1. Executes a real live trace against a known suspect address.
  2. Captures the complete output (nodes, edges, typologies, taint calculations).
  3. Serializes the result to `data/cache/<chain>/<address>.json`.
  4. The frontend demo picker reads these snapshots via `GET /demos` to provide instant, fail-safe playback.
- **Usage**:
  ```bash
  # Record a 3-hop demo trace
  uv run python -m scripts.record_demo 0x62425cd6bdcb6bfe51558ea465b063486b70dc9f --depth 3

  # List existing cached demo records
  uv run python -m scripts.record_demo --list
  ```
