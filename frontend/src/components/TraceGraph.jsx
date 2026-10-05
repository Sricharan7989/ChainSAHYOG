import { useState, useEffect, useRef, useMemo } from 'react';
import cytoscape from 'cytoscape';
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Crosshair,
  Filter,
  Eye,
  ChevronsUpDown,
} from 'lucide-react';
import { CYTOSCAPE_STYLES, LAYOUT_CONFIG } from '../utils/graphStyle';
import { findPath, extractPathNodes } from '../utils/pathfinder';
import { shortAddress, splitNodeId } from '../utils/formatters';
import { addrKey } from '../utils/address';

/**
 * Interactive Background Matrix: Subtle forensic grid dots that gently displace
 * with an inverse-square magnetic force field effect on cursor hover.
 */
function MagneticDottedCanvas({ containerRef, cyRef }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId;
    let width = 0;
    let height = 0;
    const WORLD_SPACING = 34; // Base distance between grid dots in world coordinates
    const RADIUS = 115;       // Interaction radius for magnetic field
    const MAX_DISP = 14;      // Max displacement in pixels

    const mouse = { x: -9999, y: -9999, active: false };

    const updateSize = () => {
      const rect = container.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);
    };

    updateSize();

    const handleMouseMove = (e) => {
      const rect = container.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
      mouse.active = true;
    };

    const handleMouseLeave = () => {
      mouse.active = false;
      mouse.x = -9999;
      mouse.y = -9999;
    };

    container.addEventListener('mousemove', handleMouseMove);
    container.addEventListener('mouseleave', handleMouseLeave);

    const resizeObserver = new ResizeObserver(() => {
      updateSize();
    });
    resizeObserver.observe(container);

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // Read live zoom and pan from Cytoscape
      const cy = cyRef.current;
      const zoom = cy ? cy.zoom() : 0.8;
      const pan = cy ? cy.pan() : { x: 0, y: 0 };

      // Multi-scale grid step: as you zoom in, dots spread out; as you zoom out, dots contract
      let effectiveWorldStep = WORLD_SPACING;
      while (effectiveWorldStep * zoom < 18) {
        effectiveWorldStep *= 2;
      }
      const step = effectiveWorldStep * zoom;

      // Dot radius scales with zoom
      const dotRadius = Math.max(0.85, Math.min(2.8, 1.35 * Math.sqrt(zoom)));

      // Align grid offsets with Cytoscape pan
      const startX = ((pan.x % step) + step) % step;
      const startY = ((pan.y % step) + step) % step;

      const mx = mouse.x;
      const my = mouse.y;
      const isActive = mouse.active;

      // Draw dynamic world grid dots
      for (let bx = startX - step; bx <= width + step; bx += step) {
        for (let by = startY - step; by <= height + step; by += step) {
          let drawX = bx;
          let drawY = by;
          let isClose = false;

          if (isActive) {
            const dx = bx - mx;
            const dy = by - my;
            const dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < RADIUS && dist > 0) {
              isClose = true;
              const factor = 1 - dist / RADIUS;
              const force = factor * factor * MAX_DISP;
              const angle = Math.atan2(dy, dx);
              drawX = bx + Math.cos(angle) * force;
              drawY = by + Math.sin(angle) * force;
            }
          }

          ctx.beginPath();
          if (isClose) {
            ctx.arc(drawX, drawY, dotRadius * 1.45, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(98, 126, 234, 0.6)';
          } else {
            ctx.arc(drawX, drawY, dotRadius, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(160, 160, 180, 0.12)';
          }
          ctx.fill();
        }
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      container.removeEventListener('mousemove', handleMouseMove);
      container.removeEventListener('mouseleave', handleMouseLeave);
      resizeObserver.disconnect();
    };
  }, [containerRef, cyRef]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full pointer-events-none z-0"
    />
  );
}

/**
 * Format token/ETH transfer value on graph edges without clutter
 */
function formatEdgeAmount(edge) {
  if (!edge) return '';
  const val = edge.value_eth ?? edge.value;
  if (val === undefined || val === null) return '';
  const num = Number(val);
  if (isNaN(num) || num <= 0) return '';
  const asset = edge.asset || 'ETH';
  let formatted;
  if (num >= 1000) {
    formatted = Math.round(num).toLocaleString();
  } else if (num >= 1) {
    formatted = num.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  } else {
    formatted = num.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 4 });
  }
  return `${formatted} ${asset}`;
}

export default function TraceGraph({
  data,
  onSelectNode,
  onSelectEdge,
  onPositionChange,
  selectedNodeId,
  selectedEdgeId,
}) {
  const containerRef = useRef(null);
  const cyMountRef = useRef(null);
  const cyRef = useRef(null);
  const onSelectNodeRef = useRef(onSelectNode);
  const onSelectEdgeRef = useRef(onSelectEdge);
  const onPositionChangeRef = useRef(onPositionChange);
  const selectedNodeIdRef = useRef(selectedNodeId);
  const prevMountedAddressRef = useRef(null);
  const savedViewRef = useRef(null);

  useEffect(() => {
    onSelectNodeRef.current = onSelectNode;
    onSelectEdgeRef.current = onSelectEdge;
    onPositionChangeRef.current = onPositionChange;
    selectedNodeIdRef.current = selectedNodeId;
  });

  // High-signal focus mode (Money Trail vs Full Network)
  const [focusHighSignal, setFocusHighSignal] = useState(true);

  // Compute primary money trail path
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

  // Auto-fold intermediate conduits if trail exceeds 5 nodes for zero-zoom readability
  const canFold = primaryPathNodes.length > 5;
  const [isFoldedOverride, setIsFoldedOverride] = useState(null);
  const [prevStart, setPrevStart] = useState(startAddress);

  if (startAddress !== prevStart) {
    setPrevStart(startAddress);
    setIsFoldedOverride(null);
  }

  const isFolded = isFoldedOverride !== null ? isFoldedOverride : canFold;

  // Filter nodes & edges: Strictly eliminate isolated orphan nodes
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

    const primaryNodeKeys = new Set(primaryPathNodes.map((n) => addrKey(n)));

    // 1. Gather all primary path edges
    const highSignalEdges = [...primaryPathEdges];
    const addedEdgeKeys = new Set(
      primaryPathEdges.map((e) => `${addrKey(e.source)}->${addrKey(e.target)}`)
    );

    // 2. Gather branch edges that directly connect to a primary path node
    data.edges.forEach((e) => {
      const src = addrKey(e.source);
      const dst = addrKey(e.target);
      const key = `${src}->${dst}`;
      if (addedEdgeKeys.has(key)) return;

      if (primaryNodeKeys.has(src) || primaryNodeKeys.has(dst)) {
        highSignalEdges.push(e);
        addedEdgeKeys.add(key);
      }
    });

    // 3. Keep ONLY nodes that have at least one connected edge (No orphan/floating nodes!)
    const connectedNodeIds = new Set();
    highSignalEdges.forEach((e) => {
      connectedNodeIds.add(addrKey(e.source));
      connectedNodeIds.add(addrKey(e.target));
    });
    if (startAddress) connectedNodeIds.add(addrKey(startAddress));

    const activeNodes = data.nodes.filter((n) => connectedNodeIds.has(addrKey(n.id)));
    const hiddenCount = data.nodes.length - activeNodes.length;

    return {
      displayNodes: activeNodes.length > 0 ? activeNodes : data.nodes,
      displayEdges: highSignalEdges,
      hiddenCount: Math.max(0, hiddenCount),
    };
  }, [data, focusHighSignal, primaryPathNodes, primaryPathEdges, startAddress]);

  // The chain the investigation started on. The first chain traced is the one the
  // investigator entered on; anything off it was reached by a bridge crossing, and
  // has to be marked as such. Computed here, outside the layout memo, so the memo
  // can depend on it properly.
  const tracedChains = data?.cross_chain?.chains_traced || [];
  const primaryChainSlug = tracedChains[0] || data?.chain?.slug || '';

  // Compute Vertical Layout coordinates and simplified elements
  const elements = useMemo(() => {
    if (!displayNodes.length) return [];

    const ROW_HEIGHT = 135;
    const START_Y = 65;
    const SPINE_X = 260;

    const primaryEdgeKeys = new Set(
      primaryPathEdges.map((e) => `${addrKey(e.source)}->${addrKey(e.target)}`)
    );
    const primaryNodeKeys = new Set(primaryPathNodes.map((n) => addrKey(n)));

    // 1. Build the Vertical Spine
    let effectiveSpine = [];
    const foldedMiddleIds = new Set();

    if (canFold && isFolded) {
      const head = primaryPathNodes.slice(0, 2);
      const middle = primaryPathNodes.slice(2, -2);
      const tail = primaryPathNodes.slice(-2);

      middle.forEach((addr) => foldedMiddleIds.add(addrKey(addr)));

      effectiveSpine = [
        ...head.map((addr) => ({ type: 'wallet', address: addr })),
        {
          type: 'collapsed_group',
          id: '__collapsed_conduits__',
          hiddenCount: middle.length,
          hiddenNodes: middle,
        },
        ...tail.map((addr) => ({ type: 'wallet', address: addr })),
      ];
    } else {
      effectiveSpine = primaryPathNodes.map((addr) => ({ type: 'wallet', address: addr }));
    }

    const spinePositions = new Map();
    const spineRowMap = new Map();

    effectiveSpine.forEach((item, idx) => {
      const y = START_Y + idx * ROW_HEIGHT;
      if (item.type === 'collapsed_group') {
        spinePositions.set(item.id, { x: SPINE_X, y });
        spineRowMap.set(item.id, idx);
      } else {
        const addrLower = addrKey(item.address);
        spinePositions.set(addrLower, { x: SPINE_X, y });
        spineRowMap.set(addrLower, idx);
      }
    });

    // 2. Compute Node Elements with Simplified 4-Category Taxonomy
    const nodeElements = [];
    const renderedNodeIds = new Set();
    const rowBranchCounters = new Map();

    displayNodes.forEach((n) => {
      const idLower = addrKey(n.id);
      if (foldedMiddleIds.has(idLower)) return;

      const isStart = n.is_start || idLower === addrKey(startAddress);
      const onPath = primaryNodeKeys.has(idLower);
      const isVasp = Boolean(n.is_vasp || n.entity_type === 'exchange');
      const isObfuscator = Boolean(
        n.is_mixer ||
        n.is_bridge ||
        n.entity_type === 'suspected_exchange' ||
        n.entity_type === 'sanctioned'
      );

      // A wallet reached after a chain crossing is not the same finding as one
      // reached on the chain we started on. Marking it lets the reader see that
      // the route left the chain they were investigating, which is the whole point
      // of following it.
      const nodeChain = n.chain || splitNodeId(n.id).chain || '';
      const isOffChain = Boolean(nodeChain) && nodeChain !== primaryChainSlug;

      const isSilent = !isStart && !isVasp && !isObfuscator && !onPath;

      // Simplified labels: Suspect -> Target Exchange -> Mixer/Bridge -> Primary Trail Conduit -> Silent Grey Dots
      let displayLabel;
      if (isStart) {
        displayLabel = 'SUSPECT';
      } else if (isVasp) {
        displayLabel = (n.entity || data?.summary?.exchange || 'EXCHANGE').toUpperCase();
      } else if (isObfuscator) {
        const kind = n.is_mixer ? 'MIXER' : n.is_bridge ? 'BRIDGE' : 'OBFUSCATOR';
        displayLabel = (n.entity || kind).toUpperCase();
      } else if (onPath) {
        displayLabel = shortAddress(n.id, 6, 4);
      } else {
        // "Other grey useless nodes": No address label, just clean grey dots
        displayLabel = '';
      }

      // Name the chain on anything not on the chain we started on. Without it a
      // reader sees the same short address twice and cannot tell that the route
      // crossed a bridge - which is the single most important thing to make
      // visible.
      if (isOffChain && displayLabel) {
        displayLabel = `${nodeChain.toUpperCase()}\n${displayLabel}`;
      }

      let pos = spinePositions.get(idLower);

      if (!pos) {
        // Guaranteed collision-free side slots
        const row = Math.min(n.depth ?? 1, Math.max(1, effectiveSpine.length - 1));
        const slotIdx = rowBranchCounters.get(row) || 0;
        rowBranchCounters.set(row, slotIdx + 1);

        const isLeft = slotIdx % 2 === 0;
        const tier = Math.floor(slotIdx / 2);
        const xOffset = isLeft ? -(180 + tier * 50) : (180 + tier * 50);
        const yOffset = (slotIdx % 3) * 25 - 15;

        pos = {
          x: SPINE_X + xOffset,
          y: START_Y + row * ROW_HEIGHT + yOffset,
        };
      }

      nodeElements.push({
        group: 'nodes',
        data: {
          ...n,
          id: n.id,
          displayLabel,
          is_start: isStart,
          is_vasp: isVasp,
          is_obfuscator: isObfuscator,
          is_silent: isSilent,
          on_primary_path: onPath,
          is_off_chain: isOffChain,
          chain_slug: nodeChain,
        },
        position: pos,
      });

      renderedNodeIds.add(idLower);
    });

    // Add Collapsed Group Node if folded
    if (canFold && isFolded) {
      const collapsedItem = effectiveSpine.find((item) => item.type === 'collapsed_group');
      if (collapsedItem) {
        const pos = spinePositions.get(collapsedItem.id);
        nodeElements.push({
          group: 'nodes',
          data: {
            id: collapsedItem.id,
            displayLabel: `[ ⬍ ${collapsedItem.hiddenCount} CONDUITS (CLICK TO UNFOLD) ]`,
            is_collapsed_group: true,
            hiddenCount: collapsedItem.hiddenCount,
            hiddenNodes: collapsedItem.hiddenNodes,
            on_primary_path: true,
          },
          position: pos,
        });
        renderedNodeIds.add(collapsedItem.id);
      }
    }

    // 3. Compute Edge Elements
    const edgeElements = [];
    const addedEdgeKeys = new Set();

    if (canFold && isFolded) {
      const headNodes = primaryPathNodes.slice(0, 2);
      const tailNodes = primaryPathNodes.slice(-2);

      // Edge 0: Head 0 -> Head 1
      if (primaryPathEdges[0]) {
        const pe = primaryPathEdges[0];
        const key = `${addrKey(pe.source)}->${addrKey(pe.target)}`;
        edgeElements.push({
          group: 'edges',
          data: {
            ...pe,
            id: `pe-0-${key}`,
            source: pe.source,
            target: pe.target,
            on_primary_path: true,
            displayAmount: formatEdgeAmount(pe),
          },
        });
        addedEdgeKeys.add(key);
      }

      // Synthetic Edge: Head 1 -> __collapsed_conduits__
      const headOutEdge = primaryPathEdges[1];
      edgeElements.push({
        group: 'edges',
        data: {
          id: 'pe-head-to-collapsed',
          source: headNodes[1],
          target: '__collapsed_conduits__',
          on_primary_path: true,
          is_collapsed_edge: true,
          displayAmount: formatEdgeAmount(headOutEdge),
        },
      });

      // Synthetic Edge: __collapsed_conduits__ -> Tail 0
      const tailInEdge = primaryPathEdges[primaryPathEdges.length - 2];
      edgeElements.push({
        group: 'edges',
        data: {
          id: 'pe-collapsed-to-tail',
          source: '__collapsed_conduits__',
          target: tailNodes[0],
          on_primary_path: true,
          is_collapsed_edge: true,
          displayAmount: formatEdgeAmount(tailInEdge),
        },
      });

      // Edge Tail 0 -> Tail 1
      const tailEdge = primaryPathEdges[primaryPathEdges.length - 1];
      if (tailEdge) {
        const key = `${addrKey(tailEdge.source)}->${addrKey(tailEdge.target)}`;
        edgeElements.push({
          group: 'edges',
          data: {
            ...tailEdge,
            id: `pe-tail-${key}`,
            source: tailEdge.source,
            target: tailEdge.target,
            on_primary_path: true,
            displayAmount: formatEdgeAmount(tailEdge),
          },
        });
        addedEdgeKeys.add(key);
      }
    } else {
      // All primary path edges intact
      primaryPathEdges.forEach((pe, idx) => {
        const key = `${addrKey(pe.source)}->${addrKey(pe.target)}`;
        edgeElements.push({
          group: 'edges',
          data: {
            ...pe,
            id: `pe-${idx}-${key}`,
            source: pe.source,
            target: pe.target,
            on_primary_path: true,
            displayAmount: formatEdgeAmount(pe),
            // Carried through so the stylesheet can draw a chain crossing
            // differently from a transfer. A crossing is an inference, not a
            // transaction, and drawing it as an ordinary arrow would overstate
            // what we actually know.
            is_cross_chain: pe.edge_type === 'cross_chain',
            cross_chain_label:
              pe.edge_type === 'cross_chain'
                ? `CROSSED TO ${(pe.to_chain || '').toUpperCase()}`
                : null,
          },
        });
        addedEdgeKeys.add(key);
      });
    }

    // Add remaining display edges (side-branches)
    displayEdges.forEach((e, idx) => {
      const srcLower = addrKey(e.source);
      const dstLower = addrKey(e.target);
      const key = `${srcLower}->${dstLower}`;

      if (addedEdgeKeys.has(key)) return;
      if (!renderedNodeIds.has(srcLower) || !renderedNodeIds.has(dstLower)) return;

      edgeElements.push({
        group: 'edges',
        data: {
          ...e,
          id: `de-${idx}-${key}`,
          source: e.source,
          target: e.target,
          on_primary_path: primaryEdgeKeys.has(key),
          displayAmount: formatEdgeAmount(e),
        },
      });
    });

    // Classify every edge from its OWN edge_type, in one place, after all the
    // branches above have run. Each branch builds edges slightly differently
    // (primary path, folded head/tail, side branch), and setting the crossing
    // flag inside each one meant any branch that forgot it drew an INFERRED
    // bridge arrival as an ordinary transfer - quietly overstating what we know.
    const classifiedEdges = edgeElements.map((el) => {
      if (el.data?.edge_type !== 'cross_chain') return el;
      return {
        ...el,
        data: {
          ...el.data,
          is_cross_chain: true,
          cross_chain_label: `CROSSED TO ${(el.data.to_chain || '').toUpperCase()}`,
        },
      };
    });

    return [...nodeElements, ...classifiedEdges];
  }, [
    displayNodes,
    displayEdges,
    primaryPathNodes,
    primaryPathEdges,
    startAddress,
    data?.summary?.exchange,
    primaryChainSlug,
    canFold,
    isFolded,
  ]);

  // Mount Cytoscape with relaxed initial zoom & locked node positions
  useEffect(() => {
    if (!cyMountRef.current || !elements.length) return;

    const cy = cytoscape({
      container: cyMountRef.current,
      elements,
      style: CYTOSCAPE_STYLES,
      layout: LAYOUT_CONFIG(),
      minZoom: 0.2,
      maxZoom: 2.5,
      wheelSensitivity: 0.25,
      boxSelectionEnabled: false,
      autoungrabify: true, // Prevents freely movable nodes; user pans canvas smoothly
    });

    cyRef.current = cy;

    const getNodeRenderedCoords = (nodeOrId) => {
      const targetNode =
        typeof nodeOrId === 'string'
          ? cy.$(`node[id = "${nodeOrId}"]`)
          : nodeOrId;
      if (!targetNode || targetNode.length === 0) return null;
      const rPos = targetNode.renderedPosition();
      const cyRect = cyMountRef.current?.getBoundingClientRect();
      const parentRect = containerRef.current?.getBoundingClientRect();
      if (!cyRect || !parentRect) return null;
      return {
        x: rPos.x,
        y: rPos.y + (cyRect.top - parentRect.top),
        containerWidth: parentRect.width,
        containerHeight: parentRect.height,
      };
    };

    // Track user zooming & panning so view position is always preserved
    cy.on('pan zoom', () => {
      savedViewRef.current = {
        zoom: cy.zoom(),
        pan: { ...cy.pan() },
      };
      const currentSelectedId = selectedNodeIdRef.current;
      if (currentSelectedId) {
        const coords = getNodeRenderedCoords(currentSelectedId);
        if (coords) onPositionChangeRef.current?.(coords);
      }
    });

    // Relaxed initial zoom on first load, or restore user's exact zoom/pan
    cy.ready(() => {
      const isNewAddress = prevMountedAddressRef.current !== startAddress;
      if (isNewAddress || !savedViewRef.current) {
        cy.fit(undefined, 85);
        if (cy.zoom() > 0.80) cy.zoom(0.80);
        cy.center();
        prevMountedAddressRef.current = startAddress;
        savedViewRef.current = {
          zoom: cy.zoom(),
          pan: { ...cy.pan() },
        };
      } else {
        // Keep exact user view intact (no reset on node selection or traversal)
        cy.zoom(savedViewRef.current.zoom);
        cy.pan(savedViewRef.current.pan);
      }
    });

    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      const nodeData = node.data();
      if (nodeData.is_collapsed_group) {
        setIsFoldedOverride(!isFolded);
        return;
      }
      const coords = getNodeRenderedCoords(node);
      onSelectNodeRef.current?.(nodeData, coords);
    });

    cy.on('tap', 'edge', (evt) => {
      const edge = evt.target;
      const edgeData = edge.data();
      if (edgeData.is_collapsed_edge) {
        setIsFoldedOverride(!isFolded);
        return;
      }
      const rPos = evt.renderedPosition || { x: evt.position.x, y: evt.position.y };
      const cyRect = cyMountRef.current?.getBoundingClientRect();
      const parentRect = containerRef.current?.getBoundingClientRect();
      const topOffset = cyRect && parentRect ? cyRect.top - parentRect.top : 0;
      const coords = {
        x: rPos.x,
        y: rPos.y + topOffset,
        containerWidth: parentRect?.width || 600,
        containerHeight: parentRect?.height || 640,
      };
      onSelectEdgeRef.current?.(edgeData, coords);
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        onSelectNodeRef.current?.(null, null);
        onSelectEdgeRef.current?.(null, null);
      }
    });

    return () => {
      if (cyRef.current) {
        savedViewRef.current = {
          zoom: cyRef.current.zoom(),
          pan: { ...cyRef.current.pan() },
        };
      }
      cy.destroy();
      cyRef.current = null;
    };
  }, [elements, startAddress, isFolded]);

  // Synchronize selection state without resetting viewport
  useEffect(() => {
    if (!cyRef.current) return;
    const cy = cyRef.current;

    cy.elements().unselect();
    if (selectedNodeId) {
      cy.$(`node[id = "${selectedNodeId}"]`).select();
    } else if (selectedEdgeId) {
      cy.$(`edge[id = "${selectedEdgeId}"]`).select();
    }
  }, [selectedNodeId, selectedEdgeId]);

  const handleZoomIn = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.25);
  const handleZoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() * 0.8);
  const handleFit = () => {
    if (!cyRef.current) return;
    cyRef.current.fit(undefined, 85);
    if (cyRef.current.zoom() > 0.80) cyRef.current.zoom(0.80);
    cyRef.current.center();
    savedViewRef.current = {
      zoom: cyRef.current.zoom(),
      pan: { ...cyRef.current.pan() },
    };
  };
  const handleCenterSuspect = () => {
    if (!cyRef.current || !startAddress) return;
    const node = cyRef.current.$(`node[id = "${startAddress}"]`);
    if (node.length > 0) {
      cyRef.current.center(node);
      savedViewRef.current = {
        zoom: cyRef.current.zoom(),
        pan: { ...cyRef.current.pan() },
      };
    }
  };

  const nodeStats = {
    suspect: 1,
    vasps: displayNodes.filter((n) => n.is_vasp || n.entity_type === 'exchange').length,
    obfuscators: displayNodes.filter(
      (n) => n.is_mixer || n.is_bridge || n.entity_type === 'suspected_exchange' || n.entity_type === 'sanctioned'
    ).length,
    conduits: displayNodes.filter(
      (n) =>
        !n.is_vasp &&
        !n.is_mixer &&
        !n.is_bridge &&
        !n.is_start &&
        !n.is_collapsed_group &&
        n.entity_type !== 'exchange' &&
        n.entity_type !== 'suspected_exchange' &&
        n.entity_type !== 'sanctioned'
    ).length,
  };

  return (
    <div className="relative w-full h-full min-h-[580px] lg:min-h-[640px] bg-[#0a0a0a] border border-[#262626] overflow-hidden flex flex-col brutal-shadow-dark">
      {/* TOP CONTROLS & COMPACT LEGEND HEADER */}
      <div className="bg-[#111111] border-b border-[#262626] z-20 shrink-0">
        {/* Row 1: Tools & View Toggles */}
        <div className="px-3 py-2 flex flex-wrap items-center justify-between gap-2 border-b border-[#1f1f1f]">
          {/* Left: Navigation Tools */}
          <div className="flex items-center gap-1 bg-[#1a1a1a] border border-[#262626] p-1">
            <button
              type="button"
              onClick={handleZoomIn}
              className="p-1.5 text-[#a3a3a3] hover:text-white hover:bg-[#262626] transition-colors cursor-pointer border border-[#333333]"
              title="Zoom In"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={handleZoomOut}
              className="p-1.5 text-[#a3a3a3] hover:text-white hover:bg-[#262626] transition-colors cursor-pointer border border-[#333333]"
              title="Zoom Out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <div className="h-4 w-px bg-[#333333] mx-0.5" />
            <button
              type="button"
              onClick={handleFit}
              className="p-1.5 text-[#a3a3a3] hover:text-white hover:bg-[#262626] transition-colors cursor-pointer border border-[#333333]"
              title="Fit to Screen (Comfortable Zoom)"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={handleCenterSuspect}
              className="p-1.5 text-[#a3a3a3] hover:text-[#627EEA] hover:bg-[#262626] transition-colors cursor-pointer border border-[#333333]"
              title="Center Suspect Origin"
            >
              <Crosshair className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Right: Folding Toggle, View Mode, and Trail Status */}
          <div className="flex flex-wrap items-center gap-2">
            {canFold && (
              <button
                type="button"
                onClick={() => setIsFoldedOverride(!isFolded)}
                className={`px-2.5 py-1 text-xs font-mono font-bold flex items-center gap-1.5 transition-all cursor-pointer brutal-press border ${
                  isFolded
                    ? 'bg-[#1a1a1a] text-[#627EEA] border-[#627EEA] shadow-[2px_2px_0px_#627EEA]'
                    : 'bg-[#111111] text-[#a3a3a3] border-[#262626] hover:text-white'
                }`}
                title={isFolded ? 'Unfold all intermediate conduits along the path' : 'Fold middle conduits'}
              >
                <ChevronsUpDown className="w-3.5 h-3.5" />
                <span>{isFolded ? `Unfold Trail (${primaryPathNodes.length} Wallets)` : 'Fold Middle Conduits'}</span>
              </button>
            )}

            <div className="flex items-center bg-[#1a1a1a] border border-[#262626] p-0.5 text-xs">
              <button
                type="button"
                onClick={() => setFocusHighSignal(true)}
                className={`px-2.5 py-1 font-mono font-semibold flex items-center gap-1.5 transition-all cursor-pointer brutal-press ${
                  focusHighSignal
                    ? 'bg-[#111111] text-[#627EEA] border border-[#627EEA] shadow-[2px_2px_0px_#627EEA]'
                    : 'text-[#a3a3a3] hover:text-white border border-transparent'
                }`}
                title="Show direct top-to-bottom money highway to exchange"
              >
                <Filter className="w-3.5 h-3.5" />
                <span>Money Trail ({displayNodes.length})</span>
              </button>

              <button
                type="button"
                onClick={() => setFocusHighSignal(false)}
                className={`px-2.5 py-1 font-mono font-semibold flex items-center gap-1.5 transition-all cursor-pointer brutal-press ${
                  !focusHighSignal
                    ? 'bg-[#111111] text-[#f5f5f5] border border-[#333333]'
                    : 'text-[#a3a3a3] hover:text-white border border-transparent'
                }`}
                title="Show complete network with all side-branches"
              >
                <Eye className="w-3.5 h-3.5" />
                <span>Full Network ({data?.nodes?.length || 0})</span>
              </button>
            </div>

            {focusHighSignal && hiddenCount > 0 && (
              <div className="hidden xl:flex items-center px-2 py-0.5 bg-[#111111] border border-[#262626] text-[10px] font-mono text-[#888888]">
                <span>Hiding {hiddenCount} noise nodes</span>
              </div>
            )}

            {primaryPathNodes.length > 1 && (
              <div className="hidden sm:flex items-center gap-2 bg-[#111111] border border-[#627EEA] px-2.5 py-1 shadow-[2px_2px_0px_#627EEA]">
                <div className="w-2 h-2 rounded-full bg-[#627EEA] animate-ping" />
                <span className="text-xs font-mono text-[#627EEA] font-bold">
                  Trail: {primaryPathNodes.length - 1} Hops
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Row 2: Top-Positioned Simplified 4-Category Legend */}
        <div className="px-3.5 py-1.5 bg-[#0e0e0e] flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-3 sm:gap-4 font-mono text-[11px]">
            <span className="flex items-center gap-1.5" title="Origin of illicit funds">
              <span className="w-2.5 h-2.5 bg-red-600 border border-red-400" />
              <span className="text-[#f5f5f5] font-semibold">Suspect</span>
            </span>
            <span className="flex items-center gap-1.5" title="Unhosted transfer wallet">
              <span className="w-2.5 h-2.5 bg-[#18181b] border border-[#52525b]" />
              <span className="text-[#a3a3a3]">Conduit ({nodeStats.conduits})</span>
            </span>
            {nodeStats.obfuscators > 0 && (
              <span className="flex items-center gap-1.5" title="Mixer, bridge, or high-risk hub">
                <span className="w-2.5 h-2.5 bg-amber-600 border border-amber-400" />
                <span className="text-[#fbbf24] font-semibold">Mixer / Bridge ({nodeStats.obfuscators})</span>
              </span>
            )}
            <span className="flex items-center gap-1.5" title="Target exchange where KYC can unmask suspect">
              <span className="w-2.5 h-2.5 bg-emerald-600 border border-emerald-400" />
              <span className="text-[#34d399] font-semibold">Target Exchange</span>
            </span>
            <span className="flex items-center gap-1.5" title="Direct traced forward path">
              <span className="w-4 h-1 bg-[#627EEA]" />
              <span className="text-[#627EEA] font-semibold">Traced Trail</span>
            </span>
          </div>

          <div className="text-[10px] text-[#71717a] font-mono hidden md:block">
            Top-down vertical flow · Click any wallet to inspect forensics
          </div>
        </div>
      </div>

      {/* GRAPH CANVAS WITH INTERACTIVE MAGNETIC DOTTED MATRIX BACKGROUND */}
      <div
        ref={containerRef}
        className="w-full flex-1 relative cursor-grab active:cursor-grabbing overflow-hidden"
      >
        <MagneticDottedCanvas containerRef={containerRef} cyRef={cyRef} />
        <div ref={cyMountRef} className="w-full h-full relative z-10 bg-transparent" />
      </div>
    </div>
  );
}
