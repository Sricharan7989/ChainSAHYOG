// Talks to the FastAPI backend. Requests go through Vite's /api proxy, so no
// host is hardcoded here and the API key never comes near the browser.

export async function runTrace(address, { maxDepth = 4, mode = 'auto', chainId = 1 } = {}) {
  const query = new URLSearchParams({
    address,
    max_depth: String(maxDepth),
    mode,
    chain_id: String(chainId),
  })
  const response = await fetch(`/api/trace?${query}`)

  if (!response.ok) {
    // FastAPI puts the human-readable reason in `detail`. Surfacing it beats a
    // bare status code - an investigator needs to know whether they mistyped an
    // address or whether the chain data source is down.
    let detail = `Trace failed (HTTP ${response.status})`
    try {
      const body = await response.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : detail
    } catch {
      // response had no JSON body; keep the status-based message
    }
    throw new Error(detail)
  }

  return response.json()
}

/** Recorded traces the backend can replay instantly. Used for the demo picker. */
export async function listDemos() {
  try {
    const response = await fetch('/api/demos')
    if (!response.ok) return []
    const body = await response.json()
    return body.demos ?? []
  } catch {
    // The demo list is a convenience; never let it break the app.
    return []
  }
}

/**
 * URL of the PDF report for a trace.
 *
 * A plain link rather than a fetch-and-blob: the backend already sends
 * Content-Disposition with a filed-ready filename, so the browser's own
 * download handling gives the investigator the right name for free.
 */
export function reportUrl(address, { maxDepth = 4, chainId = 1 } = {}) {
  const query = new URLSearchParams({
    address,
    max_depth: String(maxDepth),
    chain_id: String(chainId),
  })
  return `/api/report?${query}`
}

/**
 * Chains this backend can trace, for the selector.
 *
 * Read from /health rather than hardcoded in the UI: the backend's registry is
 * the authority on what is supported, and offering a chain the server rejects
 * would be worse than offering none.
 */
export async function listChains() {
  try {
    const response = await fetch('/api/health')
    if (!response.ok) return []
    const body = await response.json()
    return body.chains?.supported ?? []
  } catch {
    return []
  }
}
