# Entity Resolution & Clustering

This document explains how ChainSAHYOG identifies whether a wallet belongs to a regulated Virtual Asset Service Provider (VASP) and resolves disparate on-chain wallets into unified legal entities (`backend/core/identify.py` and `backend/core/clustering.py`).

---

## 1. The Identification Problem

A criminal operates disposable, anonymous unhosted wallets. Centralized exchanges, by contrast, are large businesses with hundreds of hot wallets, cold reserves, and millions of customer deposit addresses.

ChainSAHYOG evaluates every wallet encountered during a trace using four distinct identification methodologies:

| Method Code | Identification Method | Operational Status | Description & Confidence Range |
| :---: | :--- | :---: | :--- |
| **(a)** | **Known-Label Lookup** | ✅ **Active** | Exact match against curated public registries and sanctions lists. Confidence: **95%**. |
| **(b)** | **Deposit-Consolidation** | ✅ **Active** | Algorithmic detection of deposit-sweeping fan-in behavior. Confidence: **35% – 67%**. |
| **(c)** | Behavioral Classifier | 🔲 *Future Scope* | Statistical classification of transaction frequencies, timings, and gas fees. |
| **(d)** | Co-Spend Clustering | 🔲 *N/A (Ethereum)* | Multi-input UTXO heuristic; inapplicable to EVM account-based models. |

---

## 2. Method (a): Known-Label Registry

Method (a) performs instantaneous exact-match lookups against `data/labels.json`.

- **Registry Sources**: Curated from public Etherscan labels, GraphSense TagPacks, and official U.S. Treasury OFAC SDN sanctions designations.
- **Hot-Reloading**: The file watcher tracks `labels.json` on disk and reloads modifications at runtime without restarting the FastAPI server.
- **Classification Categories**:
  - `exchange`: Centralized VASPs (Binance, Kraken, Coinbase, WazirX).
  - `mixer`: Obfuscation protocols (Tornado.Cash, Blender.io).
  - `bridge`: Cross-chain interoperability protocols (Across, Stargate, Arbitrum Bridge).
  - `sanctioned`: Explicitly sanctioned illicit addresses (e.g. Lazarus Group).
- **Confidence**: Set to **95%** (never 100%, acknowledging label churn and institutional wallet migrations).

---

## 3. Method (b): Deposit-Consolidation Pattern

When a criminal deposits stolen cryptocurrency into an exchange, they send funds to a **unique, one-time deposit address** generated specifically for their account. 

Shortly thereafter, the exchange's automated treasury scripts sweep funds from thousands of these customer deposit addresses into a few consolidated **hot wallets**. This creates a distinct, recognizable on-chain fan-in topology ($N \to 1$).

```
[Customer Deposit Wallet A] ──┐
[Customer Deposit Wallet B] ──┼──> [Exchange Hot Wallet] (Hub)
[Customer Deposit Wallet C] ──┘
```

### The Dual-Gate Heuristic
To prevent misclassifying ordinary active personal wallets, a wallet must pass two independent gates to qualify:
1. **Absolute Floor**: It must have at least **6 distinct senders** within the observed graph.
2. **Adaptive Graph Percentile**: Its in-degree (fan-in) must exceed the **95th percentile** of in-degrees across all wallets in the current trace.

### Legal Caution & `suspected_exchange`
A criminal re-pooling their own split funds across multiple unhosted wallets produces a fan-in pattern geometrically identical to an exchange sweep. 

For this reason:
- Method (b) emits the entity type **`suspected_exchange`**, never a named entity.
- Confidence is strictly capped at **67%**.
- The API summary and PDF report display an explicit warning: *"Do NOT treat this wallet as an exchange yet. Verify independently before serving legal notices."*

---

## 4. Entity Resolution (`Cluster`)

An investigator does not serve a court order or SAHYOG notice to "wallet 0x28c6...". They serve a single legal request to **Binance**, citing all relevant deposit and hot wallet addresses.

`core/clustering.py` collapses all related wallets discovered during a trace into unified **`Cluster`** objects:

```json
{
  "cluster_id": "label:binance",
  "entity": "Binance",
  "entity_type": "exchange",
  "method": "known_label",
  "named": true,
  "members": [
    "0x28c6c06298d514db089934071355e5743bf21d60",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549"
  ],
  "member_count": 2,
  "member_hops": {
    "0x28c6c06298d514db089934071355e5743bf21d60": 2,
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": 3
  },
  "hop_distance": 2,
  "hop_distance_rule": "hop_distance is the distance to the first cluster member reached in this trace (minimum member depth).",
  "value_received": { "ETH": 198.45, "USDT": 75000.0 },
  "confidence_score": 95,
  "hub": null
}
```

### Cluster Types
1. **Named Clusters (`label:<entity-slug>`)**:
   - Groups all wallets resolving to the same confirmed entity label on this chain.
   - Inherits the entity name, `known_label` method, and 95% confidence score.
2. **Suspected Clusters (`hub:<hub-address>`)**:
   - Formed around a deposit-consolidation hub wallet, grouping the hub with every tributary address that swept into it during the trace.
   - Retains `suspected_exchange` classification and keeps confidence at or below 67%.

---

## 5. The Minimum Hop-Distance Rule

How is hop distance determined when a cluster contains wallets at varying network depths?

$$\text{cluster.hop\_distance} = \min_{w \in \text{members}} (\text{depth}(w))$$

### Core Guarantees of this Rule
1. **Never Shortens Reported Distance**: The cluster reports the depth of the *first* wallet reached. It never invents proximity that does not exist.
2. **Never Lengthens Reported Distance**: It does not average depths or use the internal sweep hub's depth.
3. **Only Reached Wallets Count**: Wallets belonging to Binance that were not touched during this trace are completely ignored.
4. **Auditability**: Every cluster object carries `member_hops` detailing the exact depth of every constituent address so magistrates and defense counsel can verify the measurement.

---

## 6. Terminal Entity Logic

When the forward BFS walk encounters an address identified as an **`exchange`**, **`suspected_exchange`**, **`mixer`**, or **`bridge`**, it classifies the node as **terminal** and halts expansion along that branch:
- **Exchanges**: The investigative goal is achieved (the regulated exit chokepoint is reached). Expanding customer withdrawals from an exchange would trace innocent third-party users.
- **Mixers**: Mixers pool and randomize deposits. Continuing forward on-chain produces meaningless false linkages.
- **Bridges**: Funds have exited the EVM network.
