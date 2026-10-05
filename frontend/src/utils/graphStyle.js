/**
 * Cytoscape stylesheet and layout configuration for ChainSAHYOG.
 * Tactical Forensic Theme — Simplified 4-Category Model:
 * 1. Suspect (Red)
 * 2. Conduit (Neutral Dark Slate)
 * 3. Obfuscator / Mixer / Bridge (Amber)
 * 4. Exchange / VASP (Emerald)
 */

export const CYTOSCAPE_STYLES = [
  // 1. BASE NODE / CONDUIT (Unhosted Transfer Wallets)
  {
    selector: 'node',
    style: {
      'shape': 'ellipse',
      'width': 44,
      'height': 44,
      'background-color': '#18181b', 
      'border-width': 2.5,
      'border-color': '#3f3f46',     
      'label': 'data(displayLabel)',
      'font-family': 'Inter, system-ui, sans-serif',
      'font-size': '11px',
      'font-weight': 700,
      'color': '#f5f5f5',           
      'text-valign': 'bottom',
      'text-margin-y': 7,
      'text-background-opacity': 1,
      'text-background-color': '#0a0a0a', 
      'text-background-padding': '4px',
      'text-background-shape': 'rectangle',
      'text-border-width': 1,
      'text-border-color': '#3f3f46',
      'text-max-width': '140px',
      'text-wrap': 'ellipsis',
      'transition-property': 'background-color, border-color, width, height, border-width, shadow-blur',
      'transition-duration': '0.2s',
    },
  },

  // SILENT / UNLABELED SECONDARY CONDUITS ("Other grey nodes")
  {
    selector: 'node[?is_silent]',
    style: {
      'width': 32,
      'height': 32,
      'background-color': '#18181b',
      'border-width': 2,
      'border-color': '#333338',
      'label': '',
      'text-background-opacity': 0,
      'text-border-width': 0,
    },
  },

  // FOLDED / COLLAPSED CONDUITS GROUP
  {
    selector: 'node[?is_collapsed_group]',
    style: {
      'shape': 'rectangle',
      'width': 220,
      'height': 40,
      'background-color': '#111111',
      'border-width': 2,
      'border-color': '#627EEA',
      'border-style': 'dashed',
      'label': 'data(displayLabel)',
      'color': '#627EEA',
      'font-size': '11px',
      'font-family': 'monospace',
      'font-weight': 700,
      'text-valign': 'center',
      'text-halign': 'center',
      'text-margin-y': 0,
      'text-background-opacity': 0,
      'z-index': 26,
    },
  },

  // 2. SUSPECT (Origin of Illicit Funds)
  {
    selector: 'node[?is_start]',
    style: {
      'width': 54,
      'height': 54,
      'background-color': '#dc2626', // red-600
      'border-color': '#fca5a5',     // red-300
      'border-width': 3.5,
      'border-opacity': 0.95,
      'color': '#fef2f2',
      'text-border-color': '#ef4444',
      'shadow-blur': 14,
      'shadow-color': '#ef4444',
      'shadow-opacity': 0.5,
      'z-index': 25,
    },
  },

  // 3. TARGET EXCHANGE / VASP (Regulated Destination)
  {
    selector: 'node[?is_vasp]',
    style: {
      'width': 54,
      'height': 54,
      'background-color': '#059669', // emerald-600
      'border-color': '#a7f3d0',     // emerald-200
      'border-width': 3.5,
      'color': '#ecfdf5',
      'text-border-color': '#10b981',
      'shadow-blur': 14,
      'shadow-color': '#10b981',
      'shadow-opacity': 0.5,
      'z-index': 25,
    },
  },

  // 4. OBFUSCATOR / MIXER / BRIDGE / RISK HUB
  {
    selector: 'node[?is_obfuscator]',
    style: {
      'width': 48,
      'height': 48,
      'background-color': '#d97706', // amber-600
      'border-color': '#fde68a',     // amber-200
      'border-width': 3,
      'color': '#fffbeb',
      'text-border-color': '#f59e0b',
      'shadow-blur': 12,
      'shadow-color': '#f59e0b',
      'shadow-opacity': 0.45,
      'z-index': 22,
    },
  },

  // SELECTED NODE
  {
    selector: 'node:selected',
    style: {
      'border-width': 4,
      'border-color': '#627EEA', 
      'border-opacity': 1,
      'shadow-blur': 0,
      'shadow-color': '#627EEA',
      'shadow-opacity': 1,
      'shadow-offset-x': 3,
      'shadow-offset-y': 3,
    },
  },

  // PRIMARY TRAIL NODE
  {
    selector: 'node[?on_primary_path]',
    style: {
      'border-color': '#627EEA',
      'border-width': 3,
      'shadow-blur': 0,
      'shadow-color': '#627EEA',
      'shadow-opacity': 1,
      'shadow-offset-x': 3,
      'shadow-offset-y': 3,
    },
  },

  // BASE EDGE (Side-Branches)
  {
    selector: 'edge',
    style: {
      'width': 2,
      'line-color': '#3a3a3c',
      'target-arrow-color': '#3a3a3c',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'arrow-scale': 0.85,
      'opacity': 0.85,
      'transition-property': 'width, line-color, target-arrow-color, opacity',
      'transition-duration': '0.2s',
    },
  },

  // HIGHLIGHTED PRIMARY PATH EDGE (The Vertical Straight Highway)
  {
    selector: 'edge[?on_primary_path]',
    style: {
      'width': 4,
      'line-color': '#627EEA',
      'target-arrow-color': '#627EEA',
      'arrow-scale': 1.15,
      'opacity': 1.0,
      'z-index': 18,
      'curve-style': 'straight',
      'line-style': 'solid',
      'label': 'data(displayAmount)',
      'font-size': '10px',
      'font-family': 'Inter, monospace, sans-serif',
      'font-weight': 700,
      'color': '#ffffff',
      'text-background-opacity': 1,
      'text-background-color': '#0a0a0a',
      'text-background-padding': '3px',
      'text-background-shape': 'rectangle',
      'text-border-width': 1,
      'text-border-color': '#627EEA',
      'text-rotation': 'none',
    },
  },

  // CROSS-CHAIN EDGE (Bridge crossing) — NOT a transaction.
  //
  // Deliberately unlike every other edge: dashed, cyan, thicker, and labelled
  // with the chain it crossed into. A crossing is an inference - the deposit is on
  // record, the arrival on the other side is matched by amount and timing - so it
  // must not look like the observed transfers around it. Drawing it as another
  // solid arrow would quietly upgrade a judgement call into a fact.
  {
    selector: 'edge[?is_cross_chain]',
    style: {
      'width': 4.5,
      'line-color': '#22d3ee',
      'target-arrow-color': '#22d3ee',
      'line-style': 'dashed',
      'arrow-scale': 1.2,
      'opacity': 1.0,
      'z-index': 21,
      'label': 'data(cross_chain_label)',
      'font-size': '10px',
      'font-family': 'Inter, monospace, sans-serif',
      'font-weight': 800,
      'color': '#a5f3fc',
      'text-background-opacity': 1,
      'text-background-color': '#083344',
      'text-background-padding': '3px',
      'text-background-shape': 'rectangle',
      'text-border-width': 1,
      'text-border-color': '#22d3ee',
      'text-rotation': 'none',
    },
  },

  // WALLET REACHED AFTER A CHAIN CROSSING.
  // The chain name is already in the label; the border keeps it findable while
  // the eye is scanning the spine rather than reading.
  {
    selector: 'node[?is_off_chain]',
    style: {
      'border-style': 'dashed',
      'border-color': '#22d3ee',
      'text-border-color': '#22d3ee',
      'text-border-width': 1.5,
    },
  },

  // SELECTED / HOVERED EDGE
  {
    selector: 'edge:selected',
    style: {
      'width': 5,
      'line-color': '#627EEA',
      'target-arrow-color': '#627EEA',
      'opacity': 1,
      'z-index': 20,
      'label': 'data(displayAmount)',
      'font-size': '10px',
      'font-weight': 700,
      'color': '#ffffff',
      'text-background-opacity': 1,
      'text-background-color': '#0a0a0a',
      'text-background-padding': '3px',
      'text-background-shape': 'rectangle',
      'text-border-width': 1,
      'text-border-color': '#627EEA',
      'text-rotation': 'none',
    },
  },
];

export const LAYOUT_CONFIG = () => ({
  name: 'preset',
  animate: true,
  animationDuration: 300,
});
