# ChainSAHYOG — project handoff and execution plan

**Read this entire file before touching any code.**

This is the complete context for a blockchain-forensics project built for
Smart India Hackathon 2026, problem statement **SIH26182**, sponsored by the
Ministry of Home Affairs. It is written to be handed to an AI coding assistant
with no prior knowledge of the project. It covers what the tool does, what is
already built, what is broken right now, and the three remaining phases to
execute.

Repository: `https://github.com/Sricharan7989/CryptoCypher.git`
Team: Cassiopeia, IIIT Sri City
Owner: Kancharla Sricharan

---

# PART 1 — WHAT THIS PROJECT IS

## The problem statement

> Automated Attribution of Unknown Cryptocurrency Wallets to Nearest Virtual
> Asset Service Providers (VASPs) through Blockchain Intelligence APIs

An investigator has a suspect wallet address from a cybercrime complaint. That
wallet is anonymous, freshly created, and tells them nothing. The tool traces
the money forward through the public blockchain, hop by hop, until it reaches a
wallet controlled by a centralized exchange (a VASP such as Binance, WazirX,
OKX). It reports which exchange the funds reached, how many hops away, how much
value arrived, a confidence score, and any mixers or bridges crossed.

That exchange is the actionable endpoint. Police serve it a lawful request
through India's SAHYOG portal, and the exchange's KYC records identify the human
behind the wallet.

## The core insight — state this in comments where relevant

Criminals move stolen crypto through many fresh, anonymous, self-controlled
"unhosted" wallets to break the trail. But to turn crypto into spendable cash
they must eventually deposit into a centralized exchange, which performed KYC
and can freeze funds.

**We do not try to recognize the criminal's wallets.** They are new and
anonymous, and a criminal never reuses one. We follow the money *through* them
until we recognize the **exchange** at the end, which cannot hide because it is
a large regulated business with a stable, recognizable on-chain fingerprint.

This distinction matters and has been misunderstood before. A database of known
criminal wallets is **not** how attribution works here. It is only used for
demo input selection and for risk flagging. If attribution depended on
recognizing the criminal, the tool would be useless against any new offender.

The tool never breaks cryptography, never decrypts anything, and never unmasks
anyone itself. It follows public transaction data to a recognizable regulated
chokepoint.

## Non-negotiable honesty discipline

This runs through the entire codebase and is the project's main credibility
asset. Judges trust a tool that knows its own boundaries more than one that
claims everything.

1. **Never claim 100% certainty.** Every attribution carries a confidence score
   capped below certainty. Unnamed/suspected exchange clusters cap at 67% and
   must never print a company name.
2. **"We detected nothing" and "we did not look" are different statements.**
   Any card or field that can receive a payload lacking its data must say the
   analysis was not performed, not that nothing was found. A false negative
   presented as a finding is worse than showing nothing.
3. **Path connectivity is not value arrival.** Where FIFO taint was computed,
   state value arrival. Where it could not be computed, fall back to
   path-connectivity wording.
4. **Inference must be scored separately from observation.** A cross-chain
   bridge match is inference. It gets its own visibly lower score.
5. **Ambiguity is reported, never resolved silently.** If several bridge
   withdrawals match, report all of them and lower confidence.
6. **An honest stop beats a wrong guess.** A trace that terminates with a
   specific reason is a usable result. A trace that guesses the wrong
   destination chain corrupts a police report.

---

# PART 2 — ARCHITECTURE AND REPO LAYOUT

```
Frontend (React + Vite, JavaScript)
  - address input, chain selector, Trace button
  - money-flow graph (Cytoscape.js)
  - finding panel: exchange, hops, taint, confidence, flags, typologies
        |
        v  HTTP / JSON
Backend (Python 3.11+, FastAPI, uvicorn, httpx)
  - /trace, /report, /health endpoints
  - forward BFS tracing engine with depth cap and dust thresholds
  - exchange identification (four methods, see below)
  - FIFO value-level taint tracking
  - laundering typology detectors
  - entity clustering
  - weighted explainable confidence scoring
  - PDF report generation (ReportLab)
        |
        v
Graph store: NetworkX in-memory, or Neo4j (Cypher) when configured
Data sources:
  - Etherscan V2 API — multichain, one key, chainid parameter
  - GraphSense TagPacks — exchange address labels
  - OFAC SDN list via ultrasoundmoney/ofac-ethereum-addresses — sanctioned
```

## Backend files

| Path | Role |
|---|---|
| `backend/app/config.py` | Chain ids, `TOKEN_CONTRACTS` per chain, `DUST_THRESHOLDS`, typology thresholds including `PEEL_MAX_GROWTH` |
| `backend/core/tracer.py` | Forward BFS engine, largest file, `_aggregate_by_recipient` |
| `backend/core/identify.py` | Four identification methods; `is_terminal()` around :471 |
| `backend/core/scoring.py` | Weighted explainable confidence |
| `backend/core/taint.py` | FIFO chronological replay, per-wallet per-asset lot ledger |
| `backend/core/typologies.py` | Five detectors; `_walk_peel_chain` around :383 |
| `backend/core/clustering.py` | Entity resolution |
| `backend/services/graph_store.py` | MemoryStore and Neo4jStore behind one interface |
| `backend/services/etherscan.py` | `txlist` and `tokentx` fetch, cache, throttle |
| `backend/services/report.py` | PDF generation |
| `backend/scripts/import_ofac.py` | Pulls OFAC sanctioned addresses into labels |
| `backend/scripts/import_tagpacks.py` | Pulls GraphSense exchange labels |
| `backend/scripts/record_demo.py` | Records a trace for instant replay |
| `data/labels.json` | 525 labels, 123 sanctioned, shape `{address: {entity, type, source, chain}}` |

## Frontend files

| Path | Role |
|---|---|
| `frontend/src/components/TraceGraph.jsx` | Cytoscape graph, node styling, legend |
| `frontend/src/components/FindingPanel.jsx` | Headline result, traced path, tabs |
| `frontend/src/components/findings/TaintCard.jsx` | FIFO taint display |
| `frontend/src/lib/trace-path.js` | Explorer URL construction |

## The four identification methods

| Method | Status | How it works |
|---|---|---|
| (a) Known-label lookup | Works | Match address against `labels.json` |
| (b) Deposit-consolidation fingerprint | Works | High distinct-sender fan-in implies an exchange deposit hub. Identifies *unlabelled* exchanges. Caps at 67% and never names a company. |
| (c) Behavioral classifier | Stub | Future scope |
| (d) Co-spend clustering | Built in Phase 10 | Bitcoin only. Shared transaction inputs imply shared ownership. This is the entire reason the UTXO pipeline exists; it is impossible on Ethereum's account model. |

## Hard rules

- API keys live only in `backend/.env`, which is gitignored. Never in frontend
  code.
- Cap trace depth (default 4) and skip dust transfers, or the graph explodes.
- Cache fetched wallets in memory during a trace; never refetch.
- Respect Etherscan free-tier rate limits with small async delays.
- Token matching is by **contract address per chain**, never by symbol. Symbols
  are trivially spoofable and the codebase already detects impersonation.
- Token decimals are per-contract, never assumed. USDT and USDC are 6 decimals
  on Ethereum but **18 on BNB Chain**. A flat allowlist would misstate every
  amount by 10^12.
- Docstrings explain the *why*, because they double as presentation material.

---

# PART 3 — WHAT IS ALREADY BUILT

Phases 0 through 8 are complete and committed. Summary of each:

| Phase | Delivered |
|---|---|
| 0 | OFAC sanctioned labels imported; scoring bug fixed; sanctioned support in frontend and PDF; confirmed sanctioned wallets do **not** terminate a trace (they are not cash-out points) |
| 1 | Neo4j `in_degrees` per-wallet grouping fix; `status()` honesty fix; silent-fallback logging raised to warning; backend made the single source of truth for the traced path; committed test suite |
| 2 | Honest output: path-connectivity wording, specific termination reasons, unfollowed-token warnings |
| 3 | Multi-chain via Etherscan V2 `chainid` parameter: Ethereum (1), Polygon (137), BNB Chain (56), Arbitrum (42161); chain-aware labels; chain-aware explorer links |
| 4 | Demo re-recording and rehearsal |
| 5 | Exchange clustering: entity resolution plus suspected-cluster grouping of unlabelled consolidation groups; hop distance reported to the first cluster member reached |
| 6 | ERC-20 token tracing: `tokentx` merged with `txlist`, per-asset decimals and dust thresholds, per-asset aggregation, contract-pinned allowlist, fake-token impersonation detection |
| 7 | FIFO taint tracking: chronological replay, per-wallet per-asset lot ledgers, pre-existing balance treated as untainted and surfaced as uncertainty, deterministic same-timestamp tie-breaking |
| 8 | Five laundering typology detectors: peel chain, layering, structuring/smurfing, rapid pass-through, round amounts (never fires alone) |

## Phase 8 verified result, for regression comparison

On the Ronin/Lazarus demo address
`0x098b716b8aaf21512996dc57eb0615e2383e2f96`, the typology detectors reported
**15 detections with 39 suppressed**, ratios 0.986 to 1.00, amounts 600 to
3,276 ETH. These were real pass-through conduits on the Lazarus route.

**If a trace of that address now reports zero typologies, something is broken.**
See Part 4.

---

# PART 4 — OPEN DEFECTS, FIX THESE FIRST

Do not start Phase 9 until these are closed. Work through them in order.

## 4.1 — BLOCKER: commit `c38d0f9` is missing from the frontend branch

Commit `c38d0f9` "Fix peel-chain growth bug, prioritise rare typologies in
reporting cap" exists on `main` but is **absent from `feature/frontend-revamp`**.
It carries two real fixes plus 56 lines of tests:

- **Peel-chain growth bug.** `_walk_peel_chain` followed the largest recipient
  without requiring the principal to shrink, producing nonsense "chains" like
  3.4 → 517 → 5,894 ETH. A peel chain by definition *peels*: value must
  decrease. Fixed with `PEEL_MAX_GROWTH = 1.05`.
- **Reporting cap crowding out rare findings.** Fifteen pass-throughs scoring
  82 to 90 filled the reporting budget and suppressed a peel chain scoring 75.
  Fixed to admit the strongest of each typology first, then fill remaining
  budget by score.

Check whether the fix is present:

```powershell
Select-String -Path backend\core\typologies.py,backend\app\config.py -Pattern "PEEL_MAX_GROWTH"
```

If that returns nothing, recover it:

```bash
git merge main
```

Then re-run a trace of the Ronin address and confirm typologies reappear.

## 4.2 — Field-name mismatches rendering silently blank

`frontend/src/components/findings/TaintCard.jsx` reads field names the backend
does not emit, so those values render blank with no error:

| Line | Frontend reads | Backend emits |
|---|---|---|
| ~26 | `summary.inflow_fraction` | `tainted_inflow_fraction` |
| ~98 | `accounting.observed_wallets` | `wallets_observed` |

Audit the whole component for further mismatches rather than fixing only these
two. A build step cannot catch this class of bug; only mounting the component
exposes it.

## 4.3 — Typologies card makes a false claim on payloads without typologies

The Laundering Typologies card prints:

> "No distinct structural laundering patterns (peel chains, rapid layering, or
> smurfing structuring) were detected along this money trail."

Cached demo payloads recorded before Phase 8 have **no `typologies` key at
all**. The guard that prevents a crash falls through to this sentence, which
asserts a clean trail where no analysis ran.

Fix it the way the taint card already handles this: distinguish "detectors ran
and found nothing" from "this recording predates the detector, no analysis was
performed". Apply the same audit to every card that can receive a payload
missing its field.

## 4.4 — No live-versus-replay indicator in the current frontend

The new frontend shows no sign of whether a result is a live trace or a cached
replay. The old panel had a "replayed from a recorded trace" badge with the
capture timestamp. Its absence has repeatedly caused confusion about whether new
features were working. Restore it, prominently.

## 4.5 — Verify the two headline value figures read different fields

`SUSPECT-ATTRIBUTABLE VALUE` and `GROSS TRACED INFLOW` both displayed
1,219.9618 ETH. They are conceptually different numbers (taint-attributed value
versus total observed inflow) and should rarely match exactly. Confirm they read
different backend fields rather than the same one twice.

## 4.6 — All 525 labels are Ethereum-only

Every entry in `data/labels.json` carries `chain: ethereum`. Multi-chain
ingestion works, but identification cannot fire on Polygon, BNB Chain, or
Arbitrum because there are no labels for those chains. Either seed exchange
labels for those chains or present multi-chain ingestion as architecture with
labels as a known gap. Do not let the UI imply identification works on a chain
where it cannot.

## 4.7 — Entity types conflated in cluster display

"Resolved Entity Clusters" lists Tornado Cash Router (a mixer) and Optimism
Gateway (a bridge) alongside exchanges such as Huobi and FTX. These are
operationally very different: an exchange is a subpoena target, a mixer is
usually not, a bridge is a handoff point. Separate them visually or label the
type on each row.

## 4.8 — Presentation issue in the skipped-assets list

The skipped non-allowlisted assets list includes `ETH (5)`, which reads as if
the tool is skipping Ethereum itself. It is presumably a scam token using the
symbol ETH, correctly refused. Label such entries with the reason the way
`DAI (39) ⚠ Fake` already is.

## 4.9 — Demo recordings go stale after every phase

Attributed figures have drifted across recordings (379.70 ETH, 100.96 ETH,
1,219.9618 ETH observed at different times). Every phase changes trace output,
so recordings must be regenerated at the end of each phase. Recording is an
HTTP call:

```bash
curl -m 1800 "http://127.0.0.1:8000/trace?address=<ADDR>&mode=live&max_depth=3&save=true"
```

`record_demo.py` lives at `backend/scripts/` and needs module invocation, not a
bare `python record_demo.py` from the project root.

---

# PART 5 — PHASE 9: CROSS-CHAIN HANDOFF

Makes the cross-chain claim real. Genuinely error-prone, so the honesty
requirements here matter more than the feature itself. Depends on multi-chain
ingestion (Phase 3) and bridge tags.

## Prompt

```
Follow value across bridges. Today bridges are tagged and flagged, and the
trace stops there. Multi-chain ingestion exists, so a handoff is now possible.

1. Build a bridge registry: bridge address, the chains it connects, and how its
   deposits and withdrawals appear on each side. Start with three or four major
   EVM bridges you can verify by hand on both block explorers. Quality matters
   far more than coverage.

2. On reaching a tagged bridge, attempt a handoff: search the destination chain
   for a matching withdrawal, matched on value (allowing for bridge fees) and a
   time window. Make both the fee tolerance and the window configurable.

3. Score the match explicitly and separately from on-chain confidence. A
   cross-chain match is inference, not observation. If several candidates match
   within the window, report all of them rather than silently picking one, and
   lower the confidence accordingly.

4. Continue the trace on the destination chain from the matched withdrawal,
   carrying the taint fraction across the bridge. Cap total cross-chain hops so
   a trace cannot wander indefinitely.

5. Make the bridge crossing visible everywhere: in the graph as a distinct edge
   type, in the traced path as an explicit "crossed to Polygon via X, matched
   on value and time" step, and in the PDF with the match evidence shown.

6. When no confident match is found, keep the current honest termination rather
   than guessing. A wrong chain handoff is worse than a stopped trace.

Note: data/labels.json is currently Ethereum-only. If the destination chain has
no labels, identification cannot fire there. Say so in the payload rather than
reporting a dead end that looks like an absence of activity.

Add tests: a clean single-candidate match, an ambiguous multi-candidate case
that must report all candidates, and a no-match case that must terminate.
```

## Verify before moving on

- Find a real bridge transaction, trace it, and verify by hand on **both** block
  explorers that the matched withdrawal is the right one
- An ambiguous case reports multiple candidates instead of picking one
- Cross-chain confidence is visibly lower than same-chain confidence
- The traced path shows the crossing as its own labelled step
- Taint carries across the bridge
- A no-match case terminates honestly with a specific reason

---

# PART 6 — PHASE 10: BITCOIN / UTXO PIPELINE

The largest phase, and the one that makes the dual data model claim true rather
than aspirational. It is also where co-spend clustering finally works, which is
the real reason the second pipeline exists.

## Essential background

Bitcoin's UTXO model is structurally different from Ethereum's account model,
and two consequences drive this phase:

- **Co-spend clustering is possible on Bitcoin and impossible on Ethereum.**
  Addresses that appear together as inputs to one transaction were almost
  certainly signed by one owner.
- **Peel chains are a UTXO artefact.** Bitcoin's forced change output creates
  them naturally. Ethereum's account model does not. Empirically: across 725
  Ethereum wallets searched, zero three-link peel chains were found, and only 4
  of 123 sanctioned addresses had even 2 links. Do not treat weak peel-chain
  results on Ethereum as a bug.

## Prompt

```
Add the Bitcoin UTXO pipeline. This is a second data model, not another chain
id. Bitcoin transactions have inputs and outputs rather than a single from and
to, so ingestion and graph construction both differ.

1. Add a Bitcoin client behind the same interface the EVM client satisfies, so
   core/tracer.py does not care which chain it is walking. Use a public API you
   can verify by hand; pick one and tell me why.

2. Decide how a UTXO transaction maps into the existing graph schema. A
   many-inputs to many-outputs transaction is not a single edge. Choose between
   a transaction-as-node bipartite representation and proportional
   input-to-output edges, implement it, and explain the trade-off you accepted.
   Whatever you choose must preserve value conservation.

3. Implement co-spend clustering, which is the reason this pipeline exists.
   Addresses appearing together as inputs to the same transaction are almost
   certainly controlled by one owner. Use union-find over input sets to collapse
   addresses into entities, and feed those entities into the existing entity
   clustering so Bitcoin exchange clusters work the same way as EVM ones.

4. Do NOT implement change-address heuristics. They are materially less
   reliable, and a wrong change-address guess corrupts the whole downstream
   trace. Note it as future work.

5. Make FIFO taint work on the UTXO model. UTXOs are naturally ordered, so this
   should be cleaner than the account model, but verify it rather than assuming.

6. Add Bitcoin labels to data/labels.json with the chain field, and confirm no
   address is ever matched against the wrong chain.

7. Update the frontend chain selector, the explorer links, and the PDF header
   for Bitcoin.

Add tests: a multi-input transaction clusters its input addresses, value is
conserved through the graph mapping, and a Bitcoin trace reaches a labelled
exchange.
```

## Verify before moving on

- Trace a known Bitcoin address and verify the first two hops by hand on a block
  explorer
- Co-spend clustering groups addresses that share transaction inputs
- Total value in equals total value out across the graph mapping
- An Ethereum label never matches a Bitcoin address
- Taint works on a Bitcoin trace
- Peel-chain detection now produces meaningful results, since Bitcoin is where
  this typology actually occurs

---

# PART 7 — PHASE 11: RE-RECORD, RECONCILE, REHEARSE

Everything above changes trace output, so demos need recording again regardless
of when they were last done. This phase is also where the presentation catches
up with reality.

## Prompt

```
Final consistency pass.

1. Re-record every demo trace. Compare each recording against a live trace of
   the same address: same attribution, same hop count, same taint figure, same
   typologies, same risk flags. Report any difference.

2. Run the full test suite and report coverage by module. Flag anything with no
   tests at all.

3. Audit the codebase for claims that are now stale in either direction: code
   comments, docstrings, README, CLAUDE.md, the /health and / endpoint
   responses, and every user-facing string describing what the tool can do.
   Several were written when the tool was Ethereum-only and
   path-connectivity-only, and now understate it.

4. Audit every frontend card for the "we did not look" failure mode: any card
   that can receive a payload missing its field must say no analysis was
   performed, never that nothing was found.

5. Produce a capability summary: for each problem-statement requirement,
   DONE / PARTIAL / NOT DONE with the file that implements it.

6. List everything still genuinely not implemented, so it can be stated plainly
   rather than discovered by a judge.
```

## Verify before moving on

- Every demo replays instantly and matches a live trace
- Test suite passes
- The capability summary is honest, including what is missing

## Then update the presentation

These claims become true and the deck currently understates them:

- Multi-chain support, including both data models (Phases 3 and 10)
- Exchange clusters (Phase 5)
- Value-level attribution with FIFO named as the accounting rule (Phase 7)
- Laundering typologies (Phase 8)
- Cross-chain mapping (Phase 9)
- Co-spend clustering (Phase 10)

These remain untrue and are worth stating plainly:

- SAHYOG API integration is simulated; no portal access exists
- Mixer and bridge detection is tag-based, not behavioural
- Change-address heuristics are deliberately not implemented
- Behavioral classifier (identification method c) remains a stub

---

# PART 8 — RUNNING THE PROJECT

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env         # then add ETHERSCAN_API_KEY
uvicorn app.main:app --reload --port 8080

# Frontend
cd frontend
npm install
npm run dev
```

Port 8000 may be blocked on Windows with `[WinError 10013]`. Use `--port 8080`.

Confirm the backend is alive at `/health`. It reports the active graph store
backend, supported chains, and loaded label count.

---

# PART 9 — RECURRING MISTAKES TO AVOID

Collected from the build so far. Each of these cost real time.

1. **Clicking a recorded demo button and expecting new features.** Cached
   payloads predate whatever was just built. Tick "Force live" or re-record.
   This caused confusion three separate times.
2. **Assuming token decimals.** Per-contract, per-chain, always. BNB Chain
   USDT/USDC are 18 decimals, not 6.
3. **Matching tokens by symbol.** Symbols are spoofable. Pin to contract
   addresses.
4. **Relying on `vite build` to catch frontend breakage.** A reference to an
   undefined component inside a never-mounted branch builds cleanly and throws
   at runtime. One such bug produced a blank white page. Mount the component.
5. **Script-based bulk rewrites of JSX.** A rewrite replacing everything between
   two function names silently deleted a component that sat inside that span.
6. **Test fixtures with identical timestamps.** FIFO taint came out zero and the
   test compared zeros, passing while proving nothing. Fixtures need causal
   ordering.
7. **Not committing.** Phase work was repeatedly left uncommitted, and one
   branch is still missing a commit because of it. Commit once per phase.
8. **Treating a detector's silence as a clean result.** See defect 4.3.
