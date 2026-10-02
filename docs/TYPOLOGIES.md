# Laundering Typology Detection

This document details the laundering typology recognition engine implemented in `backend/core/typologies.py`.

---

## 1. Investigative Purpose & Philosophy

While the tracing engine answers *"Where did the money go?"*, the typologies module answers:

> **"What does the structural behavior of this money movement look like?"**

Even when every intermediary wallet in a trail is anonymous, criminal laundering exhibits distinct geometric and temporal signatures: peeling chains, structuring into uniform slices, or routing through rapid pass-through conduits.

### The Rule Against Bare Booleans
In a law enforcement setting, reporting a bare boolean (such as `peel_chain: true`) is legally useless. An investigator cannot submit an unverified claim to a magistrate, defense counsel will challenge it, and an appellate court will reject it as unsubstantiated.

Every detection in ChainSAHYOG is emitted as a structured **`Detection`** object containing:
1. **The exact wallets and transfers involved**, in chronological order.
2. **The empirical measurements** observed on-chain.
3. **The strict threshold benchmarks** it was tested against.
4. **An auditable, plain-English explanation** ready to paste into an affidavit or SAHYOG request.

```json
{
  "typology": "peel_chain",
  "name": "Peel chain",
  "strength": 85,
  "wallets": ["0x6242...dc9f", "0x3a1b...7c2e", "0x98f1...12ab"],
  "explanation": "Funds moved down a 3-link chain, forwarding 88.5% of value to fresh wallets while peeling small amounts off.",
  "measurements": { "dominant_share": 0.885, "links": 3 },
  "thresholds": { "dominant_share": 0.80, "min_links": 3 },
  "asset": "ETH",
  "corroborating_only": false
}
```

---

## 2. Implemented Laundering Typologies

### A. Peel Chain (`peel_chain`)
- **Criminal Behavior**: A suspect wallet transfers the vast majority of its balance to a newly created address while "peeling" off a small slice towards an OTC broker, ATM, or cash-out point. The recipient wallet immediately repeats this pattern down a multi-link chain.
- **Detection Criteria**:
  - **Dominant Forward Share**: The main outgoing branch must carry at least **80%** (`PEEL_DOMINANT_SHARE = 0.80`) of total outgoing value.
  - **Peel Slice**: Secondary "peel" branches must carry no more than **20%** (`PEEL_MAX_SIDE_SHARE = 0.20`).
  - **Minimum Chain Length**: Pattern must persist across at least **3 consecutive hops** (`PEEL_MIN_LINKS = 3`).

---

### B. Layering (`layering`)
- **Criminal Behavior**: Value is moved rapidly through a succession of disposable intermediary wallets with no apparent commercial or investment purpose, solely to accumulate hop distance and obscure origin.
- **Detection Criteria**:
  - **Minimal Dwell Time**: Funds must reside in each intermediary wallet for less than **1 hour** (`LAYERING_MAX_DWELL_SEC = 3600`).
  - **Near-Total Forwarding**: Each wallet forwards between **95% and 125%** (`LAYERING_MIN_FORWARD_RATIO = 0.95`, `LAYERING_MAX_FORWARD_RATIO = 1.25`) of its incoming value.
  - **Hop Span**: Pattern must span at least **3 consecutive hops** (`LAYERING_MIN_LINKS = 3`).

---

### C. Structuring / Smurfing (`structuring`)
- **Criminal Behavior**: Evading automated anti-money laundering (AML) detection thresholds by breaking large funds into multiple smaller, near-equal payments (fan-out) or gathering multiple small payments into a single wallet (fan-in).
- **Detection Criteria**:
  - **Output/Input Count**: At least **6 distinct outputs or inputs** (`STRUCTURING_MIN_OUTPUTS = 6`, `STRUCTURING_MIN_INPUTS = 6`).
  - **Uniform Amount Distribution**: The **Coefficient of Variation (CV)** ($\frac{\sigma}{\mu}$) of the transfer amounts must be $\le \mathbf{0.10}$ (`STRUCTURING_MAX_CV = 0.10`). A tiny CV indicates deliberate, artificial slicing rather than organic payments.

---

### D. Rapid Pass-Through Conduit (`rapid_pass_through`)
- **Criminal Behavior**: A single disposable wallet functions purely as a conduit: funds arrive and are immediately swept onward in a single block or within a few minutes.
- **Detection Criteria**:
  - **Time Window**: Time between inbound and outbound transfers is $\le \mathbf{3600\text{ seconds}}$ (`PASS_THROUGH_MAX_WINDOW_SEC = 3600`).
  - **Forward Ratio**: Ratio of outbound to inbound value is between **90% and 125%** (`PASS_THROUGH_MIN_FORWARD = 0.90`, `PASS_THROUGH_MAX_FORWARD = 1.25`).
  - Operates on a single wallet, even if the next hop was not expanded.

---

### E. Round Amounts Corroboration (`round_amounts`)
- **Criminal Behavior**: High-volume transfers in clean round increments (e.g. exactly 50,000 USDT or 100 ETH).
- **CRITICAL RULE**: Round amounts **CANNOT FIRE ALONE**. Sending 1 ETH or 1,000 USDT is common in normal commerce. This detector only fires as **corroboration** when another typology has already matched the same wallets.
- **Criteria**: Transfers with $\le 2$ significant figures, representing $\ge 60\%$ of total value across at least 3 transactions.

---

## 3. False-Positive Suppression & Guards

Pattern rules applied naively to public ledgers trigger overwhelming false positives. ChainSAHYOG enforces five structural guards:

1. **Exempted Entities (`TYPOLOGY_EXEMPT_ENTITY_TYPES`)**:
   - `exchange`, `suspected_exchange`, `mixer`, and `bridge` nodes are completely **exempt** from wallet-level rules.
   - *Rationale*: An exchange hot wallet dispersing thousands of equal customer withdrawals matches the mathematical definition of "structuring", but it is simply a legitimate business operating normally. Failing to exempt it would create massive false accusations.
2. **Tainted-Only Filtering (`TYPOLOGY_TAINTED_ONLY = 1`)**:
   - Only wallets that received tainted funds from the suspect under FIFO accounting are evaluated. Unrelated background traffic on busy wallets is ignored.
3. **Materiality Floor (`TYPOLOGY_MIN_VALUE_MULTIPLE = 100`)**:
   - Patterns are only analyzed if transfer amounts exceed $100\times$ the asset dust floor (e.g. $\ge 0.1$ ETH, $\ge 100$ USDT). This prevents airdrop spam and fractional dust from triggering laundering alerts.
4. **Strength Ceiling (`TYPOLOGY_STRENGTH_CAP = 90%`)**:
   - Detections are capped at 90% strength. Pattern rules prove structure, never subjective intent.
5. **Output Cap (`TYPOLOGY_MAX_REPORTED = 15`)**:
   - Payloads report at most 15 strongest detections, with any suppressed excess counted explicitly in `typology_summary.suppressed_count`.
