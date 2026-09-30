// The Finding panel - the investigator-facing answer to "where did the money go".
//
// Everything here is written for a police investigator, not a developer. No
// method names, no field names, no confidence floats. The panel has one job:
// state what was found, show the trail that proves it, be honest about how
// certain it is, and offer the next lawful step.

import { useState } from 'react'
import { reportUrl } from '../api.js'
import {
  chainName,
  describeMethod,
  describeRole,
  explorerAddressUrl,
  findingPath,
  formatAssets,
  formatEth,
  nativeSymbol,
  pathEdges,
  shortAddress,
} from '../trace-path.js'

// The score is a weighted sum the backend can account for line by line. The
// panel therefore never shows it as a bare number: the arithmetic is one click
// away, because a figure that can justify a legal request has to be
// challengeable by whoever reads it.
function ConfidenceBar({ summary }) {
  const [open, setOpen] = useState(false)
  const pct = summary.confidence_score ?? Math.round((summary.confidence ?? 0) * 100)
  const components = summary.confidence_components ?? []
  const band = pct >= 85 ? 'high' : pct >= 60 ? 'moderate' : 'low'

  return (
    <div className="confidence">
      <div className="confidence-head">
        <span className={`confidence-value conf-${band}`}>{pct}%</span>
        <span className="confidence-label">confidence · {band}</span>
        {components.length > 0 && (
          <button
            type="button"
            className="why"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            title={summary.confidence_breakdown}
          >
            {open ? 'Hide reasoning' : 'Why this score?'}
          </button>
        )}
      </div>

      <div className="confidence-track">
        <div className={`confidence-fill conf-${band}`} style={{ width: `${pct}%` }} />
      </div>

      {open && (
        <div className="score-detail">
          <table className="score-table">
            <tbody>
              {components.map((c) => (
                <tr key={c.label}>
                  <td>{c.label}</td>
                  <td className={c.points < 0 ? 'pts pts-neg' : 'pts pts-pos'}>
                    {c.points > 0 ? `+${c.points}` : c.points}
                  </td>
                </tr>
              ))}
              <tr className="score-total">
                <td>Confidence</td>
                <td className="pts">{pct}</td>
              </tr>
            </tbody>
          </table>
          <p className="score-note">
            Scores are capped at 95. Certainty is never claimed.
          </p>
        </div>
      )}
    </div>
  )
}

// Takes `data` so the link points at the right explorer for the traced chain.
function AddressLink({ address, children, data }) {
  return (
    <a
      className="addr"
      href={explorerAddressUrl(data, address)}
      target="_blank"
      rel="noreferrer"
      title={address}
    >
      {children ?? shortAddress(address)}
    </a>
  )
}

/**
 * How much of one leg was the suspect's money.
 *
 * Shown per leg because that is where a route stops being about the suspect. A
 * leg that moved 17,969 ETH of which none is attributable looks identical to the
 * real thing without this, and it is the exact misreading taint tracking exists
 * to prevent - so "none of it" is stated loudly rather than left as an absence.
 */
function LegTaint({ edge, data }) {
  const tainted = Object.fromEntries(
    (edge.assets ?? [])
      .filter((a) => (a.tainted_value ?? 0) > 0)
      .map((a) => [a.asset, a.tainted_value]),
  )
  const computed = (edge.assets ?? []).some((a) => a.tainted_value !== undefined)
  if (!computed) return null

  if (Object.keys(tainted).length === 0) {
    return (
      <span className="leg-taint leg-taint-none">
        none of it traceable to the suspect
      </span>
    )
  }
  return (
    <span className="leg-taint">
      of which {formatAssets(tainted, undefined, nativeSymbol(data))} the suspect&rsquo;s
    </span>
  )
}

function TracedPath({ data }) {
  // Straight from the payload: the same route the PDF prints.
  const addresses = findingPath(data)
  const incomingEdges = pathEdges(data, addresses)
  const nodesById = new Map(data.nodes.map((n) => [n.id, n]))

  if (addresses.length === 0) {
    return (
      <p className="muted">
        No direct route could be reconstructed to this address.
      </p>
    )
  }

  return (
    <ol className="path">
      {addresses.map((address, index) => {
        const node = nodesById.get(address) ?? {}
        const incoming = index === 0 ? null : incomingEdges[index - 1]
        const isStart = index === 0
        const isEnd = index === addresses.length - 1

        const role = describeRole(node, isStart)

        const kind = isStart
          ? 'start'
          : node.is_vasp
            ? 'vasp'
            : node.is_mixer || node.is_bridge || node.entity_type === 'sanctioned'
              ? 'flag'
              : 'plain'

        return (
          <li key={address} className={`path-step step-${kind}`}>
            <div className="path-marker">
              <span className="path-dot" />
              {!isEnd && <span className="path-line" />}
            </div>
            <div className="path-body">
              <div className="path-role">
                {role}
                {!isStart && (
                  <span className="path-hop">hop {index}</span>
                )}
              </div>
              <AddressLink address={address} data={data} />
              {incoming && (
                <div className="path-value">
                  received {formatAssets(
                    Object.fromEntries((incoming.assets ?? []).map((a) => [a.asset, a.value])),
                    incoming.value_eth,
                    nativeSymbol(data),
                  )}
                  {incoming.tx_count > 1 && ` across ${incoming.tx_count} transactions`}
                  <LegTaint edge={incoming} data={data} />
                </div>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

/**
 * Matched laundering typologies - the shape of the movement, not the identity.
 *
 * A SECTION OF ITS OWN, deliberately not folded into risk flags. A risk flag says
 * what a wallet IS and rests on a published label; a typology says what the
 * movement LOOKS LIKE and rests on our own pattern rules. Showing them together
 * would lend the inference the label's authority.
 *
 * Each entry opens to its full explanation, the measurements that triggered it
 * and the thresholds it was judged against. That is the whole point: an
 * investigator has to be able to lift the paragraph into a case file, and anyone
 * can then disagree with our numbers rather than take our word.
 */
function Typologies({ data }) {
  const found = data.typologies ?? []
  const summary = data.typology_summary ?? {}
  const [open, setOpen] = useState(() => new Set())
  if (found.length === 0) return null

  const toggle = (i) =>
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })

  return (
    <section className="block">
      <h3>Laundering typologies</h3>
      <p className="muted typology-caveat">{summary.caveat}</p>
      {summary.suppressed > 0 && (
        <p className="muted typology-caveat">
          Showing the {summary.count} strongest; {summary.suppressed} further match
          {summary.suppressed === 1 ? '' : 'es'} of the same kinds not listed.
        </p>
      )}
      <ul className="typology-list">
        {found.map((tp, i) => {
          const band = tp.strength >= 80 ? 'high' : tp.strength >= 60 ? 'mid' : 'low'
          return (
            <li key={`${tp.typology}-${i}`} className={`typology typology-${band}`}>
              <button
                type="button"
                className="typology-head"
                onClick={() => toggle(i)}
                aria-expanded={open.has(i)}
              >
                <span className="typology-name">{tp.name}</span>
                {tp.asset && <span className="typology-asset">{tp.asset}</span>}
                <span className="typology-strength">{tp.strength}/100</span>
                {tp.corroborating_only && (
                  <span className="typology-weak">corroborating only</span>
                )}
                <span className="typology-chevron">{open.has(i) ? '−' : '+'}</span>
              </button>
              {open.has(i) && (
                <div className="typology-body">
                  <p>{tp.explanation}</p>
                  <dl className="typology-numbers">
                    <dt>Measured</dt>
                    <dd>
                      {Object.entries(tp.measurements ?? {})
                        .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
                        .join(' · ')}
                    </dd>
                    <dt>Thresholds applied</dt>
                    <dd>
                      {Object.entries(tp.thresholds ?? {})
                        .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
                        .join(' · ')}
                    </dd>
                  </dl>
                  <div className="typology-wallets">
                    {(tp.wallets ?? []).slice(0, 8).map((w) => (
                      <AddressLink key={w} address={w} data={data} />
                    ))}
                    {(tp.wallets ?? []).length > 8 && (
                      <span className="muted">
                        +{tp.wallets.length - 8} more
                      </span>
                    )}
                  </div>
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

// Risk flags come from the backend already sorted worst-first, with the ones
// sitting on the actual money trail ahead of those on side branches - a mixer
// the funds went through means something quite different from one they didn't.
function RiskFlags({ flags, data }) {
  if (!flags || flags.length === 0) return null

  const onPath = flags.filter((f) => f.on_primary_path)
  const elsewhere = flags.filter((f) => !f.on_primary_path)

  const render = (flag) => (
    <li key={flag.address} className={`flag sev-${flag.severity}`}>
      <span className="flag-icon" aria-hidden="true">!</span>
      <div>
        <div className="flag-name">
          {flag.entity}
          <span className="flag-sev">{flag.severity}</span>
          {flag.on_primary_path && <span className="flag-tag">on this path</span>}
        </div>
        <div className="flag-note">{flag.note}</div>
        <div className="flag-meta">
          {formatAssets(flag.value_received, flag.value_received_eth, nativeSymbol(data))} ·
          hop {flag.hop_distance} ·{' '}
          <AddressLink address={flag.address} data={data} />
        </div>
      </div>
    </li>
  )

  return (
    <section className="block">
      <h3>Risk flags</h3>
      {onPath.length > 0 && <ul className="flags">{onPath.map(render)}</ul>}
      {elsewhere.length > 0 && (
        <>
          <p className="flags-sub">
            Elsewhere in the trace, not on the route to this finding:
          </p>
          <ul className="flags flags-muted">{elsewhere.map(render)}</ul>
        </>
      )}
    </section>
  )
}

// The PDF is offered on every outcome, including "nothing found" - a negative
// result is still a result an investigator may need to file and justify.
function ReportActions({ data }) {
  return (
    <section className="block">
      <h3>Report</h3>
      <a
        className="download"
        href={reportUrl(data.start_address, { maxDepth: data.params.max_depth })}
        target="_blank"
        rel="noreferrer"
      >
        Download PDF report
      </a>
      <p className="action-note">
        Includes the traced path with transaction hashes, the confidence
        breakdown, risk flags and the basis-and-limitations statement.
      </p>
    </section>
  )
}

/**
 * Attributed value, gross value, and the uncertainty between them.
 *
 * These are two different numbers and the panel must never let them blur. The
 * gross figure is everything that landed in the wallet along traced transfers;
 * the attributed figure is the part FIFO accounting traces to the suspect. On the
 * recorded demo those were 17,969 and 198 - showing only the first is the bug
 * this replaces, and showing only the second hides the context an investigator
 * needs to judge it.
 */
function ValueBreakdown({ summary, data }) {
  const native = nativeSymbol(data)
  const gross = formatAssets(summary.value_received, summary.value_received_eth, native)

  if (!summary.taint_computed) {
    return (
      <div className="finding-amount">
        {gross} received by this wallet on traced transfers — not an amount
        attributable to the suspect
      </div>
    )
  }

  const fractions = Object.entries(summary.tainted_inflow_fraction ?? {})

  return (
    <div className="value-breakdown">
      <div className="vb-row vb-primary">
        <span className="vb-label">Attributable to the suspect</span>
        <span className="vb-figure">
          {summary.tainted_value_display ?? 'none'}
        </span>
      </div>
      {fractions.length > 0 && (
        <p className="vb-note">
          {fractions
            .map(([asset, f]) => `${(f * 100).toFixed(2)}% of the ${asset} this wallet received`)
            .join(', ')}
          {summary.inflow_fully_observed ? '' : ' (of the transfers the trace observed)'}
        </p>
      )}
      <div className="vb-row">
        <span className="vb-label">Gross on traced transfers</span>
        <span className="vb-figure vb-muted">{gross}</span>
      </div>
      <p className="vb-rule">
        FIFO accounting · {summary.path_fully_accounted
          ? 'every transfer on this route was accounted for'
          : `${summary.path_assumed_pre_existing_display} on this route could not be
             accounted for from observed inflows and was treated as not the suspect's`}
      </p>
    </div>
  )
}

// The caveat sits directly under the headline, never in a footnote. The tool
// follows transaction paths, not individual coins: it expands every large
// outgoing transfer of a wallet regardless of where that value came from. A
// connected path therefore does not prove the suspect's funds arrived.
function Caveat({ text }) {
  if (!text) return null
  return <p className="caveat">{text}</p>
}

// Why the walk stopped. Without this, a trace that finds nothing is
// indistinguishable from a broken tool - and each reason implies a different
// next step (lower the threshold, raise the hop limit, accept a hard stop).
function Termination({ termination }) {
  if (!termination?.label) return null
  return (
    <section className="block">
      <h3>Why the trace stopped</h3>
      <div className={`termination term-${termination.reason ?? 'unknown'}`}>
        <div className="termination-label">{termination.label}</div>
        {termination.detail && <p className="termination-detail">{termination.detail}</p>}
      </div>
    </section>
  )
}

// Wallets on the traced path that move ERC-20 tokens we do not follow. Shown
// because the alternative is silence: the trail just ends and the panel implies
// the money stopped, when it may have continued in USDT or USDC.
// What we deliberately did NOT follow. Phase 2 warned that token transfers were
// unfollowed altogether; that is no longer true - USDT, USDC, DAI, WETH and WBTC
// are traced end to end. What remains is tokens outside that list, skipped to
// keep airdrop spam out of the graph, which is worth saying rather than hiding.
//
// A skipped token can claim the symbol of one we follow, because the backend
// matches the contract address and not the name. Those are marked "impostor":
// without that, a skipped "USDT" reads as the tool having missed real money,
// when in fact it refused a fake.
function TokenWarning({ warnings }) {
  const note = warnings
  if (!note || !note.skipped_transfers) return null
  return (
    <section className="block">
      <h3>Tokens not followed</h3>
      <div className="token-warning">
        <p>
          Traced: {(note.followed_assets ?? []).join(', ')}. Skipped{' '}
          {note.skipped_transfers} transfer{note.skipped_transfers === 1 ? '' : 's'} of{' '}
          {note.distinct_tokens} other token{note.distinct_tokens === 1 ? '' : 's'} —
          mostly airdrop spam, but a genuine trail in one of them would not be followed.
        </p>
        <ul>
          {(note.top_skipped ?? []).slice(0, 5).map((t) => (
            <li key={t.asset}>
              {t.asset} · {t.transfers} transfer{t.transfers === 1 ? '' : 's'}
              {t.impersonating ? (
                <span className="impostor-tag" title={note.impersonation_note ?? ''}>
                  impostor — not the real {t.asset} contract
                </span>
              ) : null}
            </li>
          ))}
        </ul>
        {note.impersonated_symbols?.length ? (
          <p className="impostor-note">{note.impersonation_note}</p>
        ) : null}
      </div>
    </section>
  )
}

// Entity clusters: the wallets of one business, as one row. A lawful request is
// served on the entity, so this - not the raw address list - is the actionable
// view. Members stay one click away because an investigator still has to verify
// each address individually.
function Clusters({ data }) {
  const [open, setOpen] = useState(() => new Set())
  const clusters = data.clusters ?? []
  if (clusters.length === 0) return null

  const toggle = (id) =>
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  return (
    <section className="block">
      <h3>Entity clusters</h3>
      <ul className="clusters">
        {clusters.map((c) => (
          <li key={c.cluster_id} className={`cluster ${c.named ? '' : 'cluster-unnamed'}`}>
            <button type="button" className="cluster-head" onClick={() => toggle(c.cluster_id)}>
              <span className="cluster-entity">
                {c.named ? c.entity : 'Unnamed collection point'}
              </span>
              <span className="cluster-count">
                {c.member_count} wallet{c.member_count === 1 ? '' : 's'}
              </span>
              <span className="cluster-meta">
                hop {c.hop_distance} ·{' '}
                {formatAssets(c.value_received, c.value_received_eth, nativeSymbol(data))}
              </span>
              <span className="cluster-toggle">{open.has(c.cluster_id) ? '−' : '+'}</span>
            </button>
            {open.has(c.cluster_id) && (
              <ul className="cluster-members">
                {c.members.map((m) => (
                  <li key={m}>
                    hop {c.member_hops?.[m] ?? '?'} · <AddressLink address={m} data={data} />
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
      <p className="score-note">
        Hop distance is to the first member reached; grouping does not change it.
      </p>
    </section>
  )
}

function SourceBadge({ data }) {
  if (data.source !== 'cache') return null
  return (
    <div className="source-badge" title={`Recorded ${data.recorded_at}`}>
      Replayed from a recorded trace
      {data.recorded_at ? ` · captured ${data.recorded_at.slice(0, 16).replace('T', ' ')} UTC` : ''}
    </div>
  )
}

function MethodNote({ method }) {
  const described = describeMethod(method)
  return (
    <section className="block">
      <h3>How this was identified</h3>
      <div className={`method ${described.strong ? 'method-strong' : 'method-weak'}`}>
        <div className="method-title">{described.title}</div>
        <p className="method-detail">{described.detail}</p>
      </div>
    </section>
  )
}

export default function FindingPanel({ data, loading, error, onToast }) {
  const [routed, setRouted] = useState(false)

  if (loading) {
    return (
      <aside className="panel">
        <div className="panel-empty">
          <div className="spinner" />
          <p>Following the money…</p>
          <p className="muted">
            Reading public transaction records hop by hop. This can take a minute
            on a busy wallet.
          </p>
        </div>
      </aside>
    )
  }

  if (error) {
    return (
      <aside className="panel">
        <div className="panel-empty">
          <h2 className="finding-none">Trace could not run</h2>
          <p className="muted">{error}</p>
        </div>
      </aside>
    )
  }

  if (!data) {
    return (
      <aside className="panel">
        <div className="panel-empty">
          <h2>No trace yet</h2>
          <p className="muted">
            Enter a suspect wallet address to follow its funds forward through
            the blockchain and find the exchange where they landed.
          </p>
        </div>
      </aside>
    )
  }

  const summary = data.summary ?? {}
  const handleRoute = () => {
    setRouted(true)
    onToast(
      `Request prepared for ${summary.exchange ?? 'the identified exchange'} — ` +
        `simulated SAHYOG routing, nothing was actually sent.`,
    )
  }

  // --- Nothing recognised -----------------------------------------------
  if (!summary.found && !summary.lead) {
    return (
      <aside className="panel">
        <header className="finding-head none">
          <SourceBadge data={data} />
          <div className="eyebrow">Finding · {chainName(data)}</div>
          <h2 className="finding-none">No path to a known exchange</h2>
          <p className="finding-sub">
            No transaction path reached an exchange we recognise within{' '}
            {data.params.max_depth} hops.
          </p>
        </header>
        <div className="panel-body">
          <Clusters data={data} />
          <Termination termination={summary.termination ?? data.termination} />
          <TokenWarning warnings={data.token_warnings} />
          <Typologies data={data} />
          <RiskFlags flags={data.risk_flags} data={data} />
          <section className="block">
            <h3>What to do next</h3>
            <p className="muted">{summary.recommended_action}</p>
          </section>
          <ReportActions data={data} />
        </div>
      </aside>
    )
  }

  // --- Unconfirmed lead --------------------------------------------------
  if (!summary.found && summary.lead) {
    return (
      <aside className="panel">
        <header className="finding-head lead">
          <SourceBadge data={data} />
          <div className="eyebrow">Finding · {chainName(data)} · unconfirmed</div>
          <h2 className="finding-title">
            A transaction path connects to a collection point {summary.hop_distance} hop
            {summary.hop_distance === 1 ? '' : 's'} away
          </h2>
          <p className="finding-sub">
            This is a lead, not an identified exchange. It has not been named and
            must be verified before any request is raised.
          </p>
          <Caveat text={summary.caveat} />
          <ConfidenceBar summary={summary} />
        </header>

        <div className="panel-body">
          <section className="block">
            <h3>Traced path</h3>
            <TracedPath data={data} />
          </section>

          <MethodNote method={summary.method} />
          <Clusters data={data} />
          <Termination termination={summary.termination ?? data.termination} />
          <TokenWarning warnings={data.token_warnings} />
          <Typologies data={data} />
          <RiskFlags flags={data.risk_flags} data={data} />

          <section className="block">
            <h3>Recommended action</h3>
            <div className="action action-caution">
              <p>{summary.recommended_action}</p>
            </div>
          </section>
          <ReportActions data={data} />
        </div>
      </aside>
    )
  }

  // --- Confirmed exchange -------------------------------------------------
  return (
    <aside className="panel">
      <header className="finding-head found">
        <SourceBadge data={data} />
        <div className="eyebrow">Finding · {chainName(data)}</div>
        <h2 className="finding-title">
          {summary.taint_computed && summary.tainted_value_display ? (
            <>
              <strong>{summary.tainted_value_display}</strong> of the suspect&rsquo;s
              funds reached <strong>{summary.exchange}</strong>
            </>
          ) : summary.taint_computed ? (
            <>
              Path connects to <strong>{summary.exchange}</strong>, but no value
              attributable to the suspect arrived
            </>
          ) : (
            <>
              Transaction path connects to <strong>{summary.exchange}</strong>
            </>
          )}
          <span className="finding-hops">
            {summary.hop_distance} hop{summary.hop_distance === 1 ? '' : 's'}
            {summary.cluster_members > 1 &&
              ` · ${summary.cluster_members} wallets of this entity`}
          </span>
        </h2>
        <Caveat text={summary.caveat} />
        <ConfidenceBar summary={summary} />
        <ValueBreakdown summary={summary} data={data} />
      </header>

      <div className="panel-body">
        <section className="block">
          <h3>Traced path</h3>
          <TracedPath data={data} />
        </section>

        <MethodNote method={summary.method} />
        <Clusters data={data} />
        <Termination termination={summary.termination ?? data.termination} />
        <TokenWarning warnings={data.token_warnings} />
        <Typologies data={data} />
        <RiskFlags flags={data.risk_flags} data={data} />

        {summary.other_exchanges_reached?.length > 0 && (
          <section className="block">
            <h3>Other exchanges reached</h3>
            <p className="muted">
              Funds also arrived at {summary.other_exchanges_reached.join(', ')}.
              Each may hold records worth requesting.
            </p>
          </section>
        )}

        <section className="block">
          <h3>Recommended action</h3>
          <div className="action">
            <p>
              Route a lawful data request to <strong>{summary.exchange}</strong>{' '}
              via SAHYOG for the KYC records behind deposits to{' '}
              <AddressLink address={summary.address} data={data} />.
            </p>
            <button
              className="sahyog"
              onClick={handleRoute}
              disabled={routed}
              type="button"
            >
              {routed ? 'Request prepared' : `Route to SAHYOG`}
            </button>
            <p className="action-note">
              Simulated for this demo — no request leaves this machine.
            </p>
          </div>
        </section>

        <ReportActions data={data} />
      </div>
    </aside>
  )
}
