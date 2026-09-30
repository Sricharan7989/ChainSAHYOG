# ChainSAHYOG Documentation

> **Crypto Wallet → VASP Attribution & Forensic Intelligence Engine**  
> Law Enforcement Blockchain Intelligence for India's SAHYOG / I4C Cybercrime Workflow (SIH26182)

---

## What We Are Building

ChainSAHYOG is a forensic blockchain intelligence tool designed specifically for law enforcement investigators. When cryptocurrency is stolen in a cyber incident, victims report a transaction hash or a suspect unhosted wallet address.

An investigator enters this suspect address into ChainSAHYOG. The engine autonomously follows the stolen funds forward across the blockchain—hop by hop, across intermediary wallets, obfuscation services, and supported EVM networks—until the trail terminates at a **Centralized Virtual Asset Service Provider (VASP)**, such as Binance, WazirX, or Kraken.

ChainSAHYOG reports:
- **Which exchange** the funds reached.
- **How many hops** separated the suspect from the exchange.
- **An explainable confidence score** quantifying the certainty of attribution.
- **FIFO-tainted asset values** calculating exactly how much of the suspect's money landed at the exchange.
- **Detected laundering typologies** (peel chains, layering, structuring, pass-throughs).
- **Critical risk flags** (OFAC sanctions, mixers, cross-chain bridges).
- **Recommended lawful actions** ready to route directly to exchange compliance teams via India's **SAHYOG / I4C** portal.

---

## The Core Insight

```
[Suspect Wallet] ──(Hop 1)──> [Unhosted Wallet] ──(Hop 2)──> [Unhosted Wallet] ──(Hop 3)──> [VASP / Exchange]
  (Fresh, Anon)                 (Fresh, Anon)                 (Fresh, Anon)           (Regulated Chokepoint)
       │                             │                             │                             │
       ▼                             ▼                             ▼                             ▼
 Cannot Unmask                 Cannot Unmask                 Cannot Unmask              ★ KYC Records Unmask
 Directly                      Directly                      Directly                     Real-World Identity
```

Criminals move illicit cryptocurrency through many fresh, disposable, self-custodied ("unhosted") wallets to sever the direct connection to the victim. 

**ChainSAHYOG does not attempt to unmask anonymous intermediate wallets.** Instead, it exploits a fundamental structural asymmetry: to convert cryptocurrency into fiat currency (real cash) or trade liquid assets at scale, criminals must eventually deposit into centralized exchanges. 

Exchanges are regulated financial institutions:
- They enforce mandatory **Know Your Customer (KYC)** identity verification.
- They possess government-issued ID, IP logs, withdrawal bank accounts, and phone numbers.
- They operate large, recognizable, stable on-chain hot and deposit wallets that cannot hide.

By tracing public transaction data forward to these regulated chokepoints, law enforcement can issue lawful data preservation and KYC disclosure notices via SAHYOG to identify the perpetrators. The tool never breaks cryptography or decrypts data—it rigorously analyzes public ledgers.

---

## Documentation Index

Explore the specialized technical documentation below:

| Document | Topic & Scope |
| :--- | :--- |
| **[ARCHITECTURE.md](./ARCHITECTURE.md)** | System design, three-tier backend architecture, dual-engine graph store (Neo4j & NetworkX), multi-chain framework, and end-to-end dataflow sequence diagrams. |
| **[ROUTES.md](./ROUTES.md)** | Complete HTTP routing directory detailing every FastAPI endpoint, parameters, validation rules, HTTP status codes, and exception semantics. |
| **[API.md](./API.md)** | Exhaustive API specification, request parameters, Cytoscape-compatible graph schemas, detailed finding schemas, and error structures. |
| **[TRACING_ENGINE.md](./TRACING_ENGINE.md)** | Forward BFS walk mechanics, contract-pinned ERC-20 allowlists, decimals handling, multi-asset aggregation, dust filtering, and walk termination classification. |
| **[ENTITY_RESOLUTION.md](./ENTITY_RESOLUTION.md)** | Exchange identification methods: known label registries, deposit-consolidation heuristics, entity clustering (`Cluster`), and the minimum hop-distance rule. |
| **[TAINT_TRACKING.md](./TAINT_TRACKING.md)** | First-In-First-Out (FIFO) value taint accounting, chronological event replay, deterministic tie-breaking, pre-existing balance handling, and uncertainty disclosures. |
| **[TYPOLOGIES.md](./TYPOLOGIES.md)** | Automated money laundering pattern detectors: Peel chains, layering, structuring/smurfing, rapid pass-through, round amount corroboration, and false-positive guards. |
| **[CONFIDENCE_SCORING.md](./CONFIDENCE_SCORING.md)** | Weighted, legally defensible confidence score arithmetic (+50 label, +22 consolidation, hop distance decay, path cleanliness, bounds). |
| **[DATA_SOURCES.md](./DATA_SOURCES.md)** | Etherscan V2 client, rate-limit throttling, memory caching, `labels.json`, OFAC sanctions ingestion script, TagPacks importer, and demo replay recordings. |
| **[DEPLOYMENT_AND_CONFIG.md](./DEPLOYMENT_AND_CONFIG.md)** | Environment variables, configuration options, Docker Compose setup for Neo4j, local `uv` development, and running test suites. |

---

## Technical Stack Summary

- **Runtime & Language**: Python 3.11+
- **API Framework**: FastAPI, Uvicorn, Pydantic, HTTPX (async client)
- **Graph Engines**: NetworkX (in-memory, deterministic) + Neo4j 5.x (Bolt protocol, batch-buffered persistence)
- **Blockchain Data**: Etherscan API V2 (multichain via single key)
- **Document Generation**: ReportLab (forensic court-ready PDF generation)
- **Package & Environment Management**: `uv`
