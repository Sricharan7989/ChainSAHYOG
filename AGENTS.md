# AGENTS.md — Crypto Wallet → VASP Attribution Engine (SIH26182)

This file is the project's north star. Read it before every task.

## What we are building

A lightweight blockchain-intelligence tool for a law-enforcement use case
(India's SAHYOG / I4C cybercrime workflow). An investigator enters a suspect
Ethereum wallet address. The tool traces the money forward, hop by hop, through
the public blockchain until it reaches a wallet controlled by a centralized
exchange (a VASP, e.g. Binance, WazirX). It then reports WHICH exchange the
funds reached, how many hops away, a confidence score, and any mixers/bridges
crossed on the way. That exchange is the actionable point: police serve it a
lawful request via SAHYOG, and the exchange's KYC records unmask the human.

The tool never breaks cryptography, never decrypts anything, never unmasks
anyone itself. It follows PUBLIC transaction data to a recognizable regulated
chokepoint. That is the whole idea.

## The core insight (state this in comments where relevant)

Criminals move stolen crypto through many fresh, anonymous, self-controlled
"unhosted" wallets to hide the trail. But to convert crypto into real cash they
must eventually deposit into a centralized exchange, which did KYC and can
freeze funds. We do NOT try to recognize the criminal's wallets (they are new
and anonymous). We follow the money THROUGH them until we recognize the
EXCHANGE at the end, which cannot hide because it is a large regulated business
with a stable, recognizable on-chain fingerprint.

## Scope & Capabilities

The engine supports forward tracing, multi-asset flow analysis, and forensic attribution across EVM networks:
1. **Multi-Chain EVM Tracing**: Ethereum (1), Polygon (137), BNB Chain (56), Arbitrum One (42161) via Etherscan V2.
2. **Contract-Pinned Token Tracing**: Follows allowlisted stablecoins and wrapped assets (USDT, USDC, DAI, WETH, WBTC, USDC.e) pinned strictly to verified contract addresses with per-chain decimals.
3. **FIFO Taint Tracking**: Mathematical First-In-First-Out accounting over chronological events to quantify suspect funds reaching an exchange.
4. **Laundering Typologies**: Algorithmic detection of peel chains, layering, structuring/smurfing, and rapid pass-throughs with challengeable parameters.
5. **Entity Resolution & Clustering**: Consolidating thousands of deposit and sweep addresses into unified business entities (e.g., Binance) using the minimum-hop-distance rule.
6. **Dual-Engine Graph Architecture**: Persistent Neo4j graph storage with transparent, automatic fallback to in-memory NetworkX.
7. **OFAC Sanctions & Risk Flagging**: Real-time cross-referencing against US Treasury SDN lists and known obfuscators (mixers, bridges).
8. **Forensic PDF Reports**: Court- and investigator-ready documentation generated via ReportLab.

Methods (c) behavioral classifier and (d) co-spend clustering remain marked as future scope.

## Architecture

```
Frontend (React + Vite)
  - address input, chain selector, "Trace" button
  - money-flow graph (Cytoscape.js) with path highlighting
  - finding panel: exchange, hops, confidence, typologies, taint tracking, flags
        |
        v  (HTTP / JSON)
Backend (Python + FastAPI)
  - /trace, /report, /health, /demos endpoints
  - Tracing engine (NetworkX / Neo4j directed graph, forward BFS with depth & dust caps)
  - Token tracking engine (Contract-pinned allowlist, decimals normalization)
  - FIFO taint engine (Chronological event replay, per-route attribution)
  - Typologies detector (Peel chains, layering, structuring, pass-through)
  - Exchange identification & clustering:
      a. known-label lookup   (WORKS — from labels.json + OFAC)
      b. consolidation cluster (WORKS — fan-in heuristic & hub models)
      c. behavioral classifier (STUB — future scope)
      d. co-spend clustering   (STUB / N/A on account model — future scope)
  - Risk + confidence scoring (weighted, explainable arithmetic)
  - Report generator (PDF via ReportLab)
        |
        v
Data sources & Storage
  - Etherscan V2 Multichain API [ETHERSCAN_API_KEY]
  - Alchemy API (optional) [ALCHEMY_API_KEY]
  - Neo4j Graph Database (optional, docker-compose) [NEO4J_URI]
  - labels.json (address -> entity: exchanges, mixers, bridges, OFAC)
  - Replay cache (data/cache/<address>.json for instant pitch playback)
```

## Tech stack

- Backend: Python 3.11+, FastAPI, uvicorn, httpx (async requests), networkx, neo4j
- Data: pydantic models, python-dotenv for keys, pyyaml
- Frontend: React + Vite (JavaScript), Cytoscape.js for graph visualization
- PDF: ReportLab (forensic multi-page reports)
- Graph Store: Neo4j (optional) with automatic NetworkX in-memory fallback

## Hard rules

- API keys live ONLY in backend `.env` (gitignored). NEVER in frontend code.
- Cap trace depth (default 4) and ignore dust transfers (< threshold) to prevent combinatorial explosion.
- Cache fetched wallets in memory during a trace so we never refetch.
- Respect Etherscan free-tier rate limit (5 calls/sec) — 250ms serial delay.
- Every attribution carries an explainable confidence score. Never claim 100% certainty.
- Write clear docstrings explaining the WHY (this doubles as court-ready documentation).

## Demo reliability

Always support cache/replay mode (`mode=auto` or `mode=cache`) so demos run instantly and never depend on live third-party network calls during a pitch, while retaining the capability to run fresh live traces.

## Definition of done

Enter a suspect EVM address -> see money-flow graph -> path lights up to a recognized exchange entity -> panel states:
"XX ETH/USDT of the suspect's funds reached <Exchange>, N hops away, YY% confidence" with typology detections and risk flags -> simulated "Route to SAHYOG" action and downloadable court-ready PDF report.
