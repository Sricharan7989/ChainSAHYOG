# FIFO Taint Tracking & Chronological Event Replay

This document details the value-level taint tracking and chronological event replay engine implemented in `backend/core/taint.py`.

---

## 1. The Attribution Problem: Connectivity vs Value Flow

A naive blockchain trace proves only **connectivity**: a chain of transfers connects Address A to Address B. However, connectivity alone is insufficient for legal evidence.

### The Dilution Fallacy
Consider the following real-world scenario:
1. Suspect wallet sends **10 ETH** to an intermediate wallet at 10:00 AM.
2. The intermediate wallet is an active OTC desk or high-volume trading bot that already holds **500 ETH** from unrelated third parties.
3. At 11:00 AM, the intermediate wallet sends **200 ETH** onward to Binance.

A naive graph trace reports that Binance received "200 ETH" from the trail. A defense lawyer will immediately challenge this in court: *Those 200 ETH were not the suspect's coins; they were clean funds belonging to third-party clients.*

**Taint tracking answers the precise legal question:**  
*Of the funds that arrived at the exchange, exactly how much value is mathematically attributable to the suspect?*

---

## 2. The Accounting Rule: First-In, First-Out (FIFO)

Cryptocurrency tokens on an account-based ledger (like Ethereum) are fungible: a wallet does not maintain discrete coin serial numbers. To trace funds through an account that mixes deposits, an accounting rule must be chosen and applied consistently.

ChainSAHYOG implements **First-In, First-Out (FIFO)**: funds leave a wallet in the strict order they arrived.

```
Wallet receives 10 tainted ETH at t1  (Queue: [10 tainted])
Wallet receives 90 clean   ETH at t2  (Queue: [10 tainted, 90 clean])
Wallet sends    50 ETH         at t3  --> The first 10 ETH out are TAINTED;
                                          the next 40 ETH out are CLEAN.
```

### Why FIFO Over LIFO or Pro-Rata Pooling?
1. **Established Legal Precedent**: In common law jurisdictions (including India, the UK, and the Commonwealth), the rule in *Clayton's Case* and subsequent asset-recovery case law establishes FIFO as the primary standard for following misappropriated funds through mixed bank accounts.
2. **Defensibility**: FIFO is clear, intuitive, and readily explained to judges and magistrates without complex probabilistic modeling.
3. **Transparent Reporting**: Because alternative rules (e.g., pro-rata pooling where 50 ETH out would carry 10% = 5 ETH taint) yield different numbers from the identical transactions, every figure emitted by ChainSAHYOG is explicitly accompanied by the rule name:
   > `"accounting_rule": "FIFO (first in, first out): funds leave a wallet in the order they arrived."`

---

## 3. Chronological Event Replay

### Why Traversal Order Fails for Accounting
The discovery walk is a Breadth-First Search (BFS). It visits wallets by hop distance: Hop 1, then Hop 2, then Hop 3.

However, real-world blockchain transactions do not occur in hop order. A wallet at Hop 2 may have received funds from Hop 3 earlier in historical time. Propagating taint in BFS order would attempt to draw from a queue that had not yet received its historical deposits.

### The Chronological Replay Pipeline
To ensure mathematical integrity:
1. The BFS discovery walk completes its collection of transfers.
2. `taint.build_events()` extracts every individual transaction into a single master event list.
3. The event list is sorted into a **strict chronological total order**.
4. The FIFO replay loop processes events forward in time, maintaining internal balance queues for every observed wallet.

---

## 4. Deterministic Total Ordering & Tie-Breaking

Multiple transfers frequently occur within the same Ethereum block, sharing the exact same block timestamp. Non-deterministic sorting would cause the same trace to output conflicting taint numbers on subsequent runs.

To ensure 100% deterministic reproducibility, transfers are ordered using a 5-step lexicographic hierarchy:

$$\text{Sort Key} = (\text{timestamp}, \text{block\_number}, \text{tx\_index}, \text{tx\_hash}, \text{asset}, \text{from}, \text{to}, \text{value})$$

1. **Block Timestamp**: Unix seconds recorded on the block header.
2. **Block Number**: Chain height (a higher block is strictly later in time).
3. **Transaction Index (`tx_index`)**: The transaction's execution order within the block (determined by EVM consensus).
4. **Transaction Hash (`tx_hash`)**: Lexicographic hash comparison. This provides a stable, deterministic tie-break for transactions sharing an index.
5. **Asset, Sender, Recipient, Value**: Resolves multiple internal token transfers contained within a single smart contract transaction.

Where step 4 decides the FIFO queue position, the value affected is recorded in `accounting.tie_broken_value` so investigators can verify if tie-breaking introduced any material artifact.

---

## 5. The Pre-Existing Balance Problem

Due to API pagination limits (`MAX_TXNS_PER_ADDRESS = 1000`) or funds deposited prior to the investigation window, a wallet may disburse more funds than our observed incoming transfers account for.

When an outgoing payment exceeds the observed inflow queue:
- **The Conservative Standard**: ChainSAHYOG assumes the unobserved shortfall was **UNTAINTED (Clean)**.
- **Why**: This conservative assumption guarantees that the engine **never invents a link to the suspect**. It prevents overstating criminal liability.
- **Explicit Uncertainty Reporting**: Any value disbursed from an unobserved balance is tracked in `assumed_pre_existing`. If an attribution relies on unobserved funds, it is clearly flagged:
  > `"assumed_pre_existing": { "ETH": 5.0 }`

---

## 6. Output Metrics

The FIFO engine attaches detailed attribution fields to the final trace payload:

- **`tainted_value_received`**: Exact amount of suspect money that landed at the exchange (e.g. `{"USDT": 45000.0, "ETH": 148.23}`).
- **`inflow_fraction`**: Proportion of the recipient's total observed incoming volume that originated from the suspect (e.g., `0.985` = 98.5%).
- **`tainted_in` (Nodes)**: Visual node property allowing the frontend graph to display where the suspect's money flowed.
- **`tainted_value` & `tainted_fraction` (Edges)**: Edge properties showing the exact tainted value and tainted percentage crossing each transfer hop.
