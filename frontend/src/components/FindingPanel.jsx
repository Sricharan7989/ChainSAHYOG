// The Finding panel - the investigator-facing answer to "where did the money go".
//
// Everything here is written for a police investigator, not a developer. No
// method names, no field names, no confidence floats. The panel has one job:
// state what was found, show the trail that proves it, be honest about how
// certain it is, and offer the next lawful step.

import { useState } from 'react'
import { reportUrl } from '../api.js'
import {
  ETHERSCAN,
  describeMethod,
  describeRole,
  findingPath,
  formatEth,
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

function AddressLink({ address, children }) {
  return (
    <a
      className="addr"
      href={`${ETHERSCAN}${address}`}
      target="_blank"
      rel="noreferrer"
      title={address}
    >
      {children ?? shortAddress(address)}
    </a>
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
              <AddressLink address={address} />
              {incoming && (
                <div className="path-value">
                  received {formatEth(incoming.value_eth)}
                  {incoming.tx_count > 1 && ` across ${incoming.tx_count} transactions`}
                </div>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

// Risk flags come from the backend already sorted worst-first, with the ones
// sitting on the actual money trail ahead of those on side branches - a mixer
// the funds went through means something quite different from one they didn't.
function RiskFlags({ flags }) {
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
          {formatEth(flag.value_received_eth)} · hop {flag.hop_distance} ·{' '}
          <AddressLink address={flag.address} />
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
function TokenWarning({ warnings }) {
  if (!warnings || warnings.length === 0) return null
  return (
    <section className="block">
      <h3>Untraced token activity</h3>
      <div className="token-warning">
        <p>
          {warnings.length} wallet{warnings.length === 1 ? '' : 's'} on this path also
          move ERC-20 tokens, which this version does not follow. The trail may
          continue in USDT or USDC beyond what is shown.
        </p>
        <ul>
          {warnings.map((w) => (
            <li key={w.address}>
              hop {w.hop_distance} · <AddressLink address={w.address} />
            </li>
          ))}
        </ul>
      </div>
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
          <div className="eyebrow">Finding</div>
          <h2 className="finding-none">No path to a known exchange</h2>
          <p className="finding-sub">
            No transaction path reached an exchange we recognise within{' '}
            {data.params.max_depth} hops.
          </p>
        </header>
        <div className="panel-body">
          <Termination termination={summary.termination ?? data.termination} />
          <TokenWarning warnings={data.token_warnings} />
          <RiskFlags flags={data.risk_flags} />
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
          <div className="eyebrow">Finding · unconfirmed</div>
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
          <Termination termination={summary.termination ?? data.termination} />
          <TokenWarning warnings={data.token_warnings} />
          <RiskFlags flags={data.risk_flags} />

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
        <div className="eyebrow">Finding</div>
        <h2 className="finding-title">
          Transaction path connects to <strong>{summary.exchange}</strong>
          <span className="finding-hops">
            {summary.hop_distance} hop{summary.hop_distance === 1 ? '' : 's'}
          </span>
        </h2>
        <Caveat text={summary.caveat} />
        <ConfidenceBar summary={summary} />
        <div className="finding-amount">
          {formatEth(summary.value_received_eth)} received by this wallet on traced
          transfers — not an amount attributable to the suspect
        </div>
      </header>

      <div className="panel-body">
        <section className="block">
          <h3>Traced path</h3>
          <TracedPath data={data} />
        </section>

        <MethodNote method={summary.method} />
        <Termination termination={summary.termination ?? data.termination} />
        <TokenWarning warnings={data.token_warnings} />
        <RiskFlags flags={data.risk_flags} />

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
              <AddressLink address={summary.address} />.
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
