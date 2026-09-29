// The money-flow graph. Cytoscape renders the wallets and the transfers
// between them; colour carries the meaning an investigator needs at a glance:
// where the trace started, what is an exchange, and what is a mixer or bridge.

import { useEffect, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import { explorerAddressUrl, findingPath, pathEdges } from '../trace-path.js'

const STYLE = [
  {
    selector: 'node',
    style: {
      'background-color': '#94a3b8',
      label: 'data(display)',
      color: '#475569',
      'font-size': '9px',
      'text-valign': 'bottom',
      'text-margin-y': 4,
      width: 16,
      height: 16,
    },
  },
  {
    selector: 'node[kind = "start"]',
    style: { 'background-color': '#dc2626', width: 30, height: 30, color: '#b91c1c', 'font-size': '11px', 'font-weight': 'bold' },
  },
  {
    selector: 'node[kind = "vasp"]',
    style: { 'background-color': '#16a34a', width: 30, height: 30, color: '#15803d', 'font-size': '11px', 'font-weight': 'bold' },
  },
  {
    selector: 'node[kind = "suspect_vasp"]',
    style: { 'background-color': '#f0fdf4', 'border-color': '#16a34a', 'border-width': 3, width: 22, height: 22 },
  },
  {
    selector: 'node[kind = "mixer"]',
    style: { 'background-color': '#ea580c', width: 26, height: 26, color: '#c2410c', 'font-size': '10px', 'font-weight': 'bold' },
  },
  {
    selector: 'node[kind = "bridge"]',
    style: { 'background-color': '#7c3aed', width: 26, height: 26, color: '#6d28d9', 'font-size': '10px', 'font-weight': 'bold' },
  },
  {
    selector: 'node[kind = "sanctioned"]',
    style: { 'background-color': '#7f1d1d', 'border-color': '#fecaca', 'border-width': 2, width: 24, height: 24, color: '#7f1d1d', 'font-size': '10px', 'font-weight': 'bold' },
  },
  {
    // A cluster stands for several wallets, so it is drawn larger and squarer
    // than a single wallet - the shape says "this is a group", not one address.
    selector: 'node[isCluster = 1]',
    style: {
      shape: 'round-rectangle',
      width: 'label',
      height: 26,
      padding: '8px',
      'font-size': '10px',
      'font-weight': 'bold',
      'text-valign': 'center',
      'text-margin-y': 0,
      'border-width': 2,
      'border-color': '#0f172a',
      color: '#0f172a',
    },
  },
  {
    selector: 'edge',
    style: {
      width: 1,
      'line-color': '#cbd5e1',
      'target-arrow-color': '#cbd5e1',
      'target-arrow-shape': 'triangle',
      'arrow-scale': 0.7,
      'curve-style': 'bezier',
    },
  },
  {
    // The route the Finding panel is describing, lit up so the two views agree.
    selector: 'edge[onPath = 1]',
    style: { width: 3, 'line-color': '#dc2626', 'target-arrow-color': '#dc2626', 'z-index': 10 },
  },
  { selector: 'node[onPath = 1]', style: { 'border-color': '#dc2626', 'border-width': 2 } },
]

// A cluster has a type but no per-node flags, so map the type directly.
function nodeKindForType(entityType) {
  if (entityType === 'sanctioned') return 'sanctioned'
  if (entityType === 'mixer') return 'mixer'
  if (entityType === 'bridge') return 'bridge'
  if (entityType === 'suspected_exchange') return 'suspect_vasp'
  return 'vasp'
}


function nodeKind(node) {
  if (node.is_start) return 'start'
  if (node.entity_type === 'sanctioned') return 'sanctioned'
  if (node.is_mixer) return 'mixer'
  if (node.is_bridge) return 'bridge'
  if (node.entity_type === 'suspected_exchange') return 'suspect_vasp'
  if (node.is_vasp) return 'vasp'
  return 'plain'
}

export default function TraceGraph({ data }) {
  const container = useRef(null)
  const cyRef = useRef(null)
  // Which clusters the investigator has opened. Collapsed is the default: the
  // graph should first answer "which businesses", not "which 400 addresses".
  const [expanded, setExpanded] = useState(() => new Set())

  useEffect(() => {
    if (!container.current || !data) return

    // The route comes from the backend payload, so the highlighted path and the
    // path printed in the PDF are always the same route.
    const routeAddresses = findingPath(data)
    const onPath = new Set(routeAddresses)
    const routeEdges = new Set(
      pathEdges(data, routeAddresses)
        .filter(Boolean)
        .map((e) => `${e.source}->${e.target}`),
    )

    // --- entity clusters -------------------------------------------------
    // A cluster is drawn as ONE node until the investigator expands it, because
    // five Binance wallets are one business. Expanding restores the individual
    // members so any single address can still be opened on the explorer.
    const clusters = data.clusters ?? []
    const memberToCluster = new Map()
    for (const cluster of clusters) {
      if (expanded.has(cluster.cluster_id)) continue
      if (cluster.member_count < 2) continue // a single wallet gains nothing
      for (const member of cluster.members) {
        memberToCluster.set(member, cluster)
      }
    }
    const idFor = (address) => memberToCluster.get(address)?.cluster_id ?? address

    const clusterNodes = clusters
      .filter((c) => !expanded.has(c.cluster_id) && c.member_count >= 2)
      .map((cluster) => ({
        data: {
          id: cluster.cluster_id,
          display: `${cluster.named ? cluster.entity : 'collection point?'} ×${cluster.member_count}`,
          kind: cluster.entity_type === 'suspected_exchange' ? 'suspect_vasp' : nodeKindForType(cluster.entity_type),
          isCluster: 1,
          onPath: cluster.members.some((m) => onPath.has(m)) ? 1 : 0,
        },
      }))

    const walletNodes = data.nodes
      .filter((node) => !memberToCluster.has(node.id))
      .map((node) => ({
        data: {
          id: node.id,
          // Only labelled entities and the start wallet get text. Labelling all
          // 400 anonymous wallets would be noise, not information.
          display: node.is_start
            ? 'SUSPECT'
            : node.entity_type === 'suspected_exchange'
              ? 'collection point?'
              : (node.label ?? ''),
          kind: nodeKind(node),
          isCluster: 0,
          onPath: onPath.has(node.id) ? 1 : 0,
        },
      }))

    // Edges are rewired onto cluster nodes, and edges that fall entirely inside
    // one collapsed cluster are dropped - an exchange shuffling between its own
    // wallets is not part of the money trail.
    const edgeMap = new Map()
    for (const edge of data.edges) {
      const source = idFor(edge.source)
      const target = idFor(edge.target)
      if (source === target) continue
      const id = `${source}->${target}`
      const highlighted = routeEdges.has(`${edge.source}->${edge.target}`)
      const existing = edgeMap.get(id)
      if (existing) {
        existing.data.onPath = existing.data.onPath || (highlighted ? 1 : 0)
        continue
      }
      edgeMap.set(id, { data: { id, source, target, onPath: highlighted ? 1 : 0 } })
    }

    const elements = [...walletNodes, ...clusterNodes, ...edgeMap.values()]

    const cy = cytoscape({
      container: container.current,
      elements,
      style: STYLE,
      layout: {
        name: 'breadthfirst',
        directed: true,
        roots: [data.start_address],
        spacingFactor: 1.1,
        padding: 24,
      },
      minZoom: 0.15,
      maxZoom: 3,
    })

    cy.on('tap', 'node', (evt) => {
      const id = evt.target.id()
      if (evt.target.data('isCluster')) {
        // First click expands the group rather than navigating away: the member
        // addresses are what an investigator needs next.
        setExpanded((prev) => new Set(prev).add(id))
        return
      }
      // Chain-aware: a Polygon wallet must not open an Etherscan page.
      window.open(explorerAddressUrl(data, id), '_blank')
    })

    cyRef.current = cy
    return () => cy.destroy()
  }, [data, expanded])

  if (!data) {
    return (
      <div className="graph graph-empty">
        <p className="muted">The money-flow graph will appear here.</p>
      </div>
    )
  }

  return (
    <div className="graph-wrap">
      <div className="graph" ref={container} />
      <div className="legend">
        <span><i className="dot dot-start" /> Suspect wallet</span>
        <span><i className="dot dot-plain" /> Unhosted wallet</span>
        <span><i className="dot dot-vasp" /> Exchange</span>
        <span><i className="dot dot-mixer" /> Mixer</span>
        <span><i className="dot dot-bridge" /> Bridge</span>
        <span><i className="dot dot-sanctioned" /> Sanctioned</span>
        {expanded.size > 0 && (
          <button
            type="button"
            className="legend-reset"
            onClick={() => setExpanded(new Set())}
          >
            collapse {expanded.size} expanded cluster{expanded.size === 1 ? '' : 's'}
          </button>
        )}
        <span className="legend-hint">
          {data.stats.nodes} wallets · {(data.clusters ?? []).length} clusters ·
          click a group to expand, a wallet to open the explorer
        </span>
      </div>
    </div>
  )
}
