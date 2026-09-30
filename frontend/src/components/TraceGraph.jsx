import { useState, useEffect, useRef, useMemo } from 'react';
import cytoscape from 'cytoscape';
import { ZoomIn, ZoomOut, Maximize2, Crosshair, Filter, Eye } from 'lucide-react';
import { CYTOSCAPE_STYLES, LAYOUT_CONFIG } from '../utils/graphStyle';
import { findPath, extractPathNodes } from '../utils/pathfinder';
import { shortAddress } from '../utils/formatters';

export default function TraceGraph({
  data,
  onSelectNode,
  onSelectEdge,
  selectedNodeId,
}) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [focusHighSignal, setFocusHighSignal] = useState(true);

  // Compute primary path
  const targetAddress = data?.summary?.address;
  const startAddress = data?.start_address;
  const primaryPathEdges = useMemo(
    () => findPath(data?.edges, startAddress, targetAddress),
    [data?.edges, startAddress, targetAddress]
  );
  const primaryPathNodes = useMemo(
    () => extractPathNodes(primaryPathEdges, startAddress),
    [primaryPathEdges, startAddress]
  );

  // Filter nodes & edges for High-Signal Focus Mode
  const { displayNodes, displayEdges, hiddenCount } = useMemo(() => {
    if (!data?.nodes || !data?.edges) {
      return { displayNodes: [], displayEdges: [], hiddenCount: 0 };
    }

    if (!focusHighSignal) {
      return {
        displayNodes: data.nodes,
        displayEdges: data.edges,
        hiddenCount: 0,
      };
    }

    const primaryNodeKeys = new Set(primaryPathNodes.map((n) => n.toLowerCase()));
    const flaggedAddressSet = new Set(
      (data.risk_flags || []).map((f) => f.address?.toLowerCase()).filter(Boolean)
    );

    // Keep only high-value forensic nodes:
    // - Suspect origin
    // - Every hop on the primary path to the exchange
    // - Regulated VASP / Exchanges
    // - Suspected Exchange hubs
    // - Mixers and Bridges
    // - Sanctioned wallets
    // - Explicitly labeled entities or flagged risk addresses
    const highSignalNodes = data.nodes.filter((n) => {
      const idLower = n.id.toLowerCase();
      const isStart = n.is_start || idLower === startAddress?.toLowerCase();
      const onPath = primaryNodeKeys.has(idLower);
      const isVasp = n.is_vasp || n.entity_type === 'exchange';
      const isSuspectedExchange = n.entity_type === 'suspected_exchange';
      const isMixer = n.is_mixer;
      const isBridge = n.is_bridge;
      const isSanctioned = n.entity_type === 'sanctioned';
      const hasLabel = Boolean(n.label);
      const isFlagged = flaggedAddressSet.has(idLower);

      return (
        isStart ||
        onPath ||
        isVasp ||
        isSuspectedExchange ||
        isMixer ||
        isBridge ||
        isSanctioned ||
        hasLabel ||
        isFlagged
      );
    });

    const highSignalNodeIds = new Set(highSignalNodes.map((n) => n.id.toLowerCase()));

    // Keep edges between visible nodes
    const highSignalEdges = data.edges.filter(
      (e) =>
        highSignalNodeIds.has(e.source.toLowerCase()) &&
        highSignalNodeIds.has(e.target.toLowerCase())
    );

    // Guarantee all primary path edges are present
    for (const pe of primaryPathEdges) {
      const key = `${pe.source.toLowerCase()}->${pe.target.toLowerCase()}`;
      if (!highSignalEdges.some((e) => `${e.source.toLowerCase()}->${e.target.toLowerCase()}` === key)) {
        highSignalEdges.push(pe);
      }
    }

    const hiddenCount = data.nodes.length - highSignalNodes.length;

    return {
      displayNodes: highSignalNodes.length > 0 ? highSignalNodes : data.nodes,
      displayEdges: highSignalEdges,
      hiddenCount: Math.max(0, hiddenCount),
    };
  }, [data, focusHighSignal, primaryPathNodes, primaryPathEdges, startAddress]);

  useEffect(() => {
    if (!containerRef.current || !displayNodes.length) return;

    const primaryEdgeKeys = new Set(
      primaryPathEdges.map((e) => `${e.source.toLowerCase()}->${e.target.toLowerCase()}`)
    );
    const primaryNodeKeys = new Set(primaryPathNodes.map((n) => n.toLowerCase()));

    // Prepare Cytoscape elements
    const elements = [
      // Nodes
      ...displayNodes.map((n) => {
        const idLower = n.id.toLowerCase();
        const isStart = n.is_start || idLower === startAddress?.toLowerCase();
        const onPath = primaryNodeKeys.has(idLower);

        // Clear, readable forensic label for every visible node
        let displayLabel;
        if (isStart) {
          displayLabel = 'SUSPECT';
        } else if (n.label) {
          displayLabel = n.label.toUpperCase();
        } else if (n.is_vasp && n.entity_type === 'exchange') {
          displayLabel = (n.entity || data?.summary?.exchange || 'VASP').toUpperCase();
        } else if (n.entity_type === 'suspected_exchange') {
          displayLabel = 'DEPOSIT HUB?';
        } else if (n.is_mixer) {
          displayLabel = (n.entity || 'MIXER').toUpperCase();
        } else if (n.is_bridge) {
          displayLabel = (n.entity || 'BRIDGE').toUpperCase();
        } else if (n.entity_type === 'sanctioned') {
          displayLabel = 'SANCTIONED';
        } else {
          displayLabel = shortAddress(n.id, 6, 4);
        }

        return {
          group: 'nodes',
          data: {
            ...n,
            id: n.id,
            displayLabel,
            on_primary_path: onPath,
          },
        };
      }),

      // Edges
      ...displayEdges.map((e, idx) => {
        const key = `${e.source.toLowerCase()}->${e.target.toLowerCase()}`;
        const onPath = primaryEdgeKeys.has(key);

        return {
          group: 'edges',
          data: {
            ...e,
            id: `e-${idx}-${e.source}-${e.target}`,
            source: e.source,
            target: e.target,
            on_primary_path: onPath,
          },
        };
      }),
    ];

    // Initialize Cytoscape with Top-to-Bottom Layout
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: CYTOSCAPE_STYLES,
      layout: LAYOUT_CONFIG(startAddress),
      minZoom: 0.2,
      maxZoom: 3.5,
      wheelSensitivity: 0.25,
      boxSelectionEnabled: false,
    });

    cyRef.current = cy;

    // Node click handler
    cy.on('tap', 'node', (evt) => {
      const nodeData = evt.target.data();
      onSelectNode(nodeData);
    });

    // Edge click handler
    cy.on('tap', 'edge', (evt) => {
      const edgeData = evt.target.data();
      onSelectEdge(edgeData);
    });

    // Background tap clears selection
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        onSelectNode(null);
        onSelectEdge(null);
      }
    });

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [displayNodes, displayEdges, startAddress]);

  // Sync external selection with Cytoscape
  useEffect(() => {
    if (!cyRef.current) return;
    const cy = cyRef.current;

    cy.elements().unselect();
    if (selectedNodeId) {
      cy.$(`node[id = "${selectedNodeId}"]`).select();
    }
  }, [selectedNodeId]);

  // Graph Controls
  const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.25);
  const handleZoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() * 0.8);
  const handleFit = () => cyRef.current?.fit(undefined, 40);
  const handleCenterSuspect = () => {
    if (!cyRef.current || !startAddress) return;
    const node = cyRef.current.$(`node[id = "${startAddress}"]`);
    if (node.length > 0) {
      cyRef.current.center(node);
      cyRef.current.zoom(1.15);
    }
  };

  const nodeStats = {
    suspect: 1,
    vasps: displayNodes.filter((n) => n.is_vasp && n.entity_type === 'exchange').length,
    leads: displayNodes.filter((n) => n.entity_type === 'suspected_exchange').length,
    mixers: displayNodes.filter((n) => n.is_mixer).length,
    bridges: displayNodes.filter((n) => n.is_bridge).length,
    unhosted: displayNodes.filter((n) => !n.is_vasp && !n.is_mixer && !n.is_bridge && !n.is_start).length,
  };

  return (
    <div className="relative w-full h-full min-h-[580px] lg:min-h-[640px] bg-white dark:bg-zinc-950 rounded-2xl border border-slate-200 dark:border-zinc-800/80 overflow-hidden shadow-sm dark:shadow-2xl flex flex-col">
      {/* Top Floating Control Bar */}
      <div className="absolute top-4 left-4 right-4 z-20 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
        {/* Left: Navigation Tools */}
        <div className="flex items-center gap-1.5 bg-white/95 dark:bg-zinc-900/90 border border-slate-200 dark:border-zinc-800 rounded-xl p-1.5 shadow-lg backdrop-blur-md pointer-events-auto">
          <button
            type="button"
            onClick={handleZoomIn}
            className="p-1.5 text-slate-700 dark:text-zinc-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-lg transition-colors cursor-pointer"
            title="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={handleZoomOut}
            className="p-1.5 text-slate-700 dark:text-zinc-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-lg transition-colors cursor-pointer"
            title="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <div className="h-4 w-px bg-slate-200 dark:bg-zinc-800 mx-0.5" />
          <button
            type="button"
            onClick={handleFit}
            className="p-1.5 text-slate-700 dark:text-zinc-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-lg transition-colors cursor-pointer"
            title="Fit to Screen"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={handleCenterSuspect}
            className="p-1.5 text-slate-700 dark:text-zinc-300 hover:text-cyan-600 dark:hover:text-cyan-400 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-lg transition-colors cursor-pointer"
            title="Center Suspect Origin"
          >
            <Crosshair className="w-4 h-4" />
          </button>
        </div>

        {/* Right: High-Signal Focus Filter & Path Pill */}
        <div className="flex items-center gap-2 pointer-events-auto">
          {/* Segmented Filter Control */}
          <div className="flex items-center bg-white/95 dark:bg-zinc-900/90 border border-slate-200 dark:border-zinc-800 rounded-xl p-1 shadow-lg backdrop-blur-md text-xs">
            <button
              type="button"
              onClick={() => setFocusHighSignal(true)}
              className={`px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
                focusHighSignal
                  ? 'bg-cyan-500/20 text-cyan-700 dark:text-cyan-300 border border-cyan-500/40 shadow-xs'
                  : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200'
              }`}
              title="Filter out low-volume dust nodes to reveal high-risk flow clearly"
            >
              <Filter className="w-3.5 h-3.5" />
              <span>High-Signal Focus ({displayNodes.length})</span>
            </button>

            <button
              type="button"
              onClick={() => setFocusHighSignal(false)}
              className={`px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
                !focusHighSignal
                  ? 'bg-slate-200 dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 border border-slate-300 dark:border-zinc-700 shadow-xs'
                  : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200'
              }`}
              title="Show all unfiltered nodes in graph"
            >
              <Eye className="w-3.5 h-3.5" />
              <span>All Nodes ({data?.nodes?.length || 0})</span>
            </button>
          </div>

          {/* Hidden dust nodes notice pill */}
          {focusHighSignal && hiddenCount > 0 && (
            <div className="hidden xl:flex items-center px-2.5 py-1.5 rounded-xl bg-white/90 dark:bg-zinc-900/90 border border-slate-200 dark:border-zinc-800 text-[11px] font-mono text-slate-500 dark:text-zinc-400 shadow-sm backdrop-blur-md">
              <span>Hiding {hiddenCount} dust nodes</span>
            </div>
          )}

          {/* Active Trail Pill */}
          {primaryPathNodes.length > 1 && (
            <div className="hidden sm:flex items-center gap-2 bg-white/95 dark:bg-zinc-900/90 border border-cyan-500/30 rounded-xl px-3 py-1.5 shadow-lg backdrop-blur-md">
              <div className="w-2 h-2 rounded-full bg-cyan-500 animate-ping" />
              <span className="text-xs font-mono text-cyan-700 dark:text-cyan-300 font-semibold">
                Trail: {primaryPathNodes.length - 1} Hops ({primaryPathNodes.length} Wallets)
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Cytoscape Canvas Container */}
      <div ref={containerRef} className="w-full flex-1 cursor-grab active:cursor-grabbing" />

      {/* Forensic Category Legend at Bottom */}
      <div className="border-t border-slate-200 dark:border-zinc-800/80 bg-slate-50/95 dark:bg-zinc-900/90 backdrop-blur-md px-4 py-2.5 z-20 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-3 sm:gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded-full bg-red-600 ring-2 ring-red-400/40" />
            <span className="text-slate-800 dark:text-zinc-300 font-medium">Suspect</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded-full bg-emerald-600 ring-2 ring-emerald-400/40" />
            <span className="text-slate-800 dark:text-zinc-300 font-medium">VASP ({nodeStats.vasps})</span>
          </span>
          {nodeStats.leads > 0 && (
            <span className="flex items-center gap-1.5">
              <span className="w-3.5 h-3.5 rounded-full bg-emerald-800 border border-emerald-400 border-dashed" />
              <span className="text-slate-800 dark:text-zinc-300 font-medium">Deposit Hub ({nodeStats.leads})</span>
            </span>
          )}
          {nodeStats.mixers > 0 && (
            <span className="flex items-center gap-1.5">
              <span className="w-3.5 h-3.5 rounded-full bg-amber-600 ring-2 ring-amber-400/40" />
              <span className="text-slate-800 dark:text-zinc-300 font-medium">Mixer ({nodeStats.mixers})</span>
            </span>
          )}
          {nodeStats.bridges > 0 && (
            <span className="flex items-center gap-1.5">
              <span className="w-3.5 h-3.5 rounded-full bg-violet-600 ring-2 ring-violet-400/40" />
              <span className="text-slate-800 dark:text-zinc-300 font-medium">Bridge ({nodeStats.bridges})</span>
            </span>
          )}
          <span className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded-full bg-slate-600" />
            <span className="text-slate-600 dark:text-zinc-400">Unhosted ({nodeStats.unhosted})</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-5 h-1 bg-cyan-500 rounded-full" />
            <span className="text-cyan-700 dark:text-cyan-300 font-mono text-[11px] font-semibold">Traced Trail</span>
          </span>
        </div>

        <div className="text-[11px] text-slate-500 dark:text-zinc-400 font-mono hidden md:block">
          Top-down flow · Click any wallet or hop to inspect forensics
        </div>
      </div>
    </div>
  );
}
