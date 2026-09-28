// Helpers for reading a trace response.
//
// The backend returns the whole money-flow graph plus the attributions. The
// panel needs one more thing: the actual chain of wallets from the suspect to
// the exchange, hop by hop. That is derived here rather than round-tripping to
// the server, since the edge list already contains everything required.

/**
 * The traced route to the headline finding, as addresses, straight from the payload.
 *
 * The backend already computed this (tracer.trace -> store.shortest_path) and it
 * is what the PDF prints, so the frontend MUST NOT recompute it. It used to run
 * its own BFS here, which agreed only by luck: the recorded Binance demo has
 * three equally short two-hop routes, and nothing forced both sides to break the
 * tie the same way. The graph could then highlight a different route from the one
 * the report cited. One computation, one source of truth.
 *
 * Returns [] when nothing was identified, or when no route was reconstructed.
 */
export function findingPath(data) {
  const target = data?.summary?.address
  if (!target) return []
  const attribution = (data.attributions ?? []).find((a) => a.address === target)
  return attribution?.path ?? []
}

/**
 * The transfer edges between consecutive addresses of a path.
 *
 * Index i is the edge INTO addresses[i + 1], so the panel can show what each
 * wallet received. Missing edges become null rather than throwing - a payload
 * whose path and edge list disagree should degrade, not blank the panel.
 */
export function pathEdges(data, addresses) {
  const byPair = new Map(
    (data.edges ?? []).map((e) => [`${e.source}->${e.target}`, e]),
  )
  const edges = []
  for (let i = 0; i < addresses.length - 1; i += 1) {
    edges.push(byPair.get(`${addresses[i]}->${addresses[i + 1]}`) ?? null)
  }
  return edges
}

/**
 * The address the headline finding points at, whichever form the result took.
 * A confirmed exchange and an unconfirmed lead both carry `address`.
 */
export function primaryAddress(summary) {
  return summary?.address ?? null
}

/** 0x1234…cdef - short enough to scan, long enough to compare by eye. */
export function shortAddress(address) {
  if (!address || address.length < 12) return address ?? ''
  return `${address.slice(0, 8)}…${address.slice(-6)}`
}

/** Plain English for how an attribution was made. No jargon in the panel. */
export function describeMethod(method) {
  switch (method) {
    case 'known_label':
      return {
        title: 'Matched against known exchange wallets',
        detail:
          'This address appears on our register of published exchange wallets. ' +
          'Exchanges cannot hide these - they must publish deposit addresses to ' +
          'their customers.',
        strong: true,
      }
    case 'consolidation':
      return {
        title: 'Deposit-consolidation pattern',
        detail:
          'Many separate wallets funnel into this one address, which is how an ' +
          'exchange sweeps customer deposits. The exchange has not been named, ' +
          'and a criminal re-pooling their own funds looks the same.',
        strong: false,
      }
    default:
      return {
        title: 'Not identified',
        detail: 'No identification method recognised this address.',
        strong: false,
      }
  }
}

/**
 * What to call a wallet in the traced path, in the investigator's language.
 *
 * The backend names a consolidation hit "Unknown exchange (consolidation
 * pattern)" - accurate, but it reads like debug output. Here it becomes plain
 * language that still refuses to name a company, because the whole point of
 * that result is that no company has been identified.
 */
export function describeRole(node, isStart) {
  if (isStart) return 'Suspect wallet'
  if (!node) return 'Intermediate wallet'
  if (node.entity_type === 'suspected_exchange') return 'Possible collection point'
  if (node.is_vasp) return node.label ?? 'Exchange'
  if (node.is_mixer) return `${node.label} · mixer`
  if (node.is_bridge) return `${node.label} · bridge`
  if (node.entity_type === 'sanctioned') return `${node.label} · OFAC sanctioned`
  return 'Intermediate wallet'
}

/**
 * Format a native-token amount. `symbol` defaults to ETH for older payloads.
 *
 * Note the field it reads is still named `value_eth` throughout the API; only
 * the displayed unit is chain-aware. See the multi-chain notes in the README.
 */
export function formatEth(value, symbol = 'ETH') {
  if (value === null || value === undefined) return '—'
  if (value >= 1000) {
    return `${value.toLocaleString('en-US', { maximumFractionDigits: 0 })} ${symbol}`
  }
  if (value >= 1) return `${value.toFixed(2)} ${symbol}`
  return `${value.toFixed(4)} ${symbol}`
}

/**
 * Block-explorer base for the chain a trace actually ran on.
 *
 * Read from the payload rather than hardcoded: on a Polygon trace an Etherscan
 * link sends the investigator to a page for an address that may not exist there,
 * which looks like the tool being wrong about the finding. Falls back to
 * Etherscan for recordings made before chains were tracked.
 */
export function explorerBase(data) {
  const base = data?.params?.explorer ?? 'https://etherscan.io'
  return base.replace(/\/$/, '')
}

export function explorerAddressUrl(data, address) {
  return `${explorerBase(data)}/address/${address}`
}

/** Display name of the chain a payload describes. */
export function chainName(data) {
  return data?.params?.chain_name ?? 'Ethereum'
}

/** The chain's gas-token symbol, for value formatting. */
export function nativeSymbol(data) {
  return data?.params?.native_symbol ?? 'ETH'
}
