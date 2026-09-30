# Tracing Engine & Multi-Asset Flow Analysis

The Tracing Engine (`backend/core/tracer.py`) is the core analytical component of ChainSAHYOG. It maps the movement of stolen funds forward across the blockchain from a suspect wallet to a regulated exit point.

---

## 1. Forward Traversal Mechanics

### Breadth-First Search (BFS) vs Depth-First Search (DFS)
The engine strictly executes a **Breadth-First Search (BFS)** traversal:

1. **Shortest-Path Guarantee**: In an unweighted or hop-counted graph, BFS guarantees that the first time any wallet or exchange is reached, it is discovered via the shortest possible path. When an investigator is informed that funds reached Binance "2 hops away", BFS is what ensures that number is legally accurate. DFS could report an arbitrary, longer circuitous route first.
2. **Predictable Bounding**: BFS expands uniformly by depth layer ($0 \to 1 \to 2 \dots$). This enables strict depth capping without leaving shallow, high-probability branches unexplored.

### Outgoing-Only Traversal
The engine follows **outgoing transfers only**. It never traverses incoming edges.
- **Why**: Incoming edges lead backwards to victims, legitimate buyers, or unrelated third-party funders. An investigator already knows the suspect's origin; the legal imperative is to find the *downstream exit point* where the criminal attempts to liquidate funds into fiat.

---

## 2. Multi-Asset Tracing & Contract-Pinned Allowlist

### Why Contract Addresses Are Identity (Not Symbols)
In EVM blockchains, an ERC-20 token's `symbol()` is an arbitrary string chosen by the smart contract deployer. Anyone can deploy a worthless contract named `"USDT"` or `"USDC"`.

If an attribution engine matches tokens by symbol strings:
- An attacker or spammer sending fake `"USDT"` would distort the graph.
- The engine would sum worthless tokens with real assets.
- A police report would falsely state that millions of dollars in USDT moved to an exchange.

**ChainSAHYOG pins token identities exclusively to verified smart contract addresses per chain (`app/config.py`).** The token symbol in our reports is a verified display label assigned by our engine, never a string trusted from the chain.

### Per-Chain Token Allowlist & Decimals

Token contracts and decimals differ across networks. For example, USDT uses 6 decimals on Ethereum and 18 decimals on BNB Chain. Misinterpreting decimals distorts financial amounts by 12 orders of magnitude.

| Chain ID | Asset | Contract Address | Decimals |
| :---: | :---: | :--- | :---: |
| **1 (Ethereum)** | USDT | `0xdac17f958d2ee523a2206206994597c13d831ec7` | 6 |
| | USDC | `0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48` | 6 |
| | DAI | `0x6b175474e89094c44da98b954eedeac495271d0f` | 18 |
| | WETH | `0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2` | 18 |
| | WBTC | `0x2260fac5e5542a773aa44fbcfedf7c193bc2c599` | 8 |
| **137 (Polygon)** | USDT | `0xc2132d05d31c914a87c6611c10748aeb04b58e8f` | 6 |
| | USDC | `0x3c499c542cef5e3811e1192ce70d8cc03d5c3359` | 6 |
| | USDC.e | `0x2791bca1f2de4661ed88a30c99a7a9449aa84174` | 6 |
| | DAI | `0x8f3cf7ad23cd3cadbd9735aff958023239c6a063` | 18 |
| | WETH | `0x7ceb23fd6bc0add59e62ac25578270cff1b9f619` | 18 |
| | WBTC | `0x1bfd67037b42cf73acf2047067bd4f2c47d9bfd6` | 8 |
| **56 (BNB Chain)** | USDT | `0x55d398326f99059ff775485246999027b3197955` | 18 |
| | USDC | `0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d` | 18 |
| | DAI | `0x1af3f329e8be154074d8769d1ffa4ee058b1dbc3` | 18 |
| | ETH | `0x2170ed0880ac9a755fd29b2688956bd959f933f8` | 18 |
| | BTCB | `0x7130d2a12b9bcbfae4f2634d864a1ee1ce3ead9c` | 18 |
| **42161 (Arbitrum)**| USDT | `0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9` | 6 |
| | USDC | `0xaf88d065e77c8cc2239327c5edb3a432268e5831` | 6 |
| | USDC.e | `0xff970a61a04b1ca14834a43f5de4533ebddb5cc8` | 6 |
| | DAI | `0xda10009cbd5d07dd0cecc66161fc93d7c9000da1` | 18 |
| | WETH | `0x82af49447d8a07e3bd95bd0d56f35241523fbab1` | 18 |
| | WBTC | `0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f` | 8 |

### Impersonation Detection
When a token transfer is encountered outside the verified contract allowlist, the engine inspects its claimed symbol. If a fraudulent token claims the name of an allowlisted asset (e.g., claiming `"USDT"` from an unverified contract), it is flagged in `token_warnings.impersonated_symbols`. This transparently proves to investigators that the asset was rejected as a counterfeit, not overlooked as a missing feature.

---

## 3. Flow Aggregation & Per-Asset Dust Filtering

### Separate Ledger Accounting
Transfers are collapsed into flows keyed by **recipient AND asset**:
- 5 ETH and 5,000 USDT are kept in separate ledger buckets; they are never summed together into "5,005" units.
- Each edge stores an `assets` dictionary tracking individual tokens, transaction counts, timestamps, and representative hashes.

### Per-Transaction, Per-Asset Dust Floors
Spam transactions and dust dusting attacks spray fractional pennies across thousands of addresses to pollute blockchain indexers.

1. **Filtering is Per-Transaction**: Filtering occurs before aggregation. A thousand 0.0001 ETH spam sends cannot sum past the threshold to pollute the graph.
2. **Thresholds are Asset-Denominated**:
   - `ETH` / `WETH`: 0.001 ETH (~$2–4)
   - `POL`: 1.0 POL (~$0.40)
   - `BNB`: 0.002 BNB (~$1.00)
   - `USDT` / `USDC` / `DAI`: 1.0 unit ($1.00)
   - `WBTC` / `BTCB`: 0.00002 BTC (~$1–2)

---

## 4. Combinatorial Guard-Rails

A busy exchange hot wallet can process tens of thousands of transactions per minute. Unbounded forward walks would crash server memory and exhaust API quotas.

| Guard-Rail Setting | Default | Rationale & Protection |
| :--- | :---: | :--- |
| `MAX_TRACE_DEPTH` | `4` | Deep enough to penetrate 3–4 intermediary laundering hops; prevents infinite depth search. |
| `MAX_EDGES_PER_NODE` | `25` | Expands only the 25 highest-value outgoing flows per wallet. |
| `MAX_NODES_PER_TRACE` | `400` | Hard ceiling on total wallets instantiated in a single trace. |
| `MAX_TXNS_PER_ADDRESS` | `1000` | Truncates transaction fetching to the 1,000 most recent records per wallet. |
| `ETHERSCAN_REQUEST_DELAY_SEC` | `0.25s` | Enforces 4 calls/second to comfortably operate within the Etherscan free tier (5 calls/s). |

---

## 5. Walk Termination Classification

When a forward branch ceases expansion, `_classify_termination()` assigns a decisive, plain-language reason to the result:

| Reason Key | Status Description | Meaning for the Investigator |
| :--- | :--- | :--- |
| `exchange_reached` | Regulated exchange reached | **Goal achieved**. Serve lawful request to exchange. |
| `terminated_at_mixer` | Trail terminates at mixer | **Chain of custody severed**. Funds entered Tornado Cash or similar mixer. On-chain trail cut. |
| `terminated_at_bridge` | Trail leaves chain via bridge | **Funds bridged cross-chain**. Funds moved to another network outside current trace scope. |
| `no_outgoing_transfers` | No outgoing transfers from start | **Funds dormant**. Stolen funds still sit in suspect wallet. |
| `dust_only` | All transfers below dust floor | **Transfers too small**. Lower `dust_threshold` and re-run. |
| `depth_cap_reached` | Reached max depth limit | **Trail continues deeper**. Increase `max_depth` (up to 6) and re-run. |
| `graph_cap_reached` | Graph size ceiling hit | **High-degree fan-out**. Only largest branches followed. |
| `no_labelled_entity` | Path ended at unlabelled wallet | **Funds in unhosted wallet** or exchange is unlabelled. |
