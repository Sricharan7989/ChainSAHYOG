/**
 * Cytoscape stylesheet and layout configuration for ChainSAHYOG.
 * Tactical Forensic Theme with High-Contrast Nodes and Crisp Typography.
 */

export const CYTOSCAPE_STYLES = [
  // Base Node Style (Unhosted / Intermediary)
  {
    selector: 'node',
    style: {
      'shape': 'ellipse',
      'width': 46,
      'height': 46,
      'background-color': '#334155', // slate-700
      'border-width': 2.5,
      'border-color': '#64748b',     // slate-500
      'label': 'data(displayLabel)',
      'font-family': 'Inter, system-ui, sans-serif',
      'font-size': '12px',
      'font-weight': 700,
      'color': '#f8fafc',           // slate-50
      'text-valign': 'bottom',
      'text-margin-y': 7,
      'text-background-opacity': 0.92,
      'text-background-color': '#09090b', // zinc-950
      'text-background-padding': '4px',
      'text-background-shape': 'roundrectangle',
      'text-border-width': 1,
      'text-border-color': '#3f3f46',
      'text-max-width': '140px',
      'text-wrap': 'ellipsis',
      'transition-property': 'background-color, border-color, width, height, border-width, shadow-blur',
      'transition-duration': '0.2s',
    },
  },

  // Start / Suspect Wallet (Loot Origin)
  {
    selector: 'node[?is_start]',
    style: {
      'width': 58,
      'height': 58,
      'background-color': '#dc2626', // red-600
      'border-color': '#fca5a5',     // red-300
      'border-width': 3.5,
      'border-opacity': 0.95,
      'color': '#fef2f2',
      'text-border-color': '#ef4444',
      'shadow-blur': 16,
      'shadow-color': '#ef4444',
      'shadow-opacity': 0.5,
      'z-index': 25,
    },
  },

  // Confirmed VASP / Regulated Exchange
  {
    selector: 'node[?is_vasp][entity_type = "exchange"]',
    style: {
      'width': 58,
      'height': 58,
      'background-color': '#059669', // emerald-600
      'border-color': '#a7f3d0',     // emerald-200
      'border-width': 3.5,
      'color': '#ecfdf5',
      'text-border-color': '#10b981',
      'shadow-blur': 16,
      'shadow-color': '#10b981',
      'shadow-opacity': 0.5,
      'z-index': 25,
    },
  },

  // Suspected Exchange (Consolidation Hub)
  {
    selector: 'node[entity_type = "suspected_exchange"]',
    style: {
      'width': 50,
      'height': 50,
      'background-color': '#065f46', // emerald-800
      'border-color': '#34d399',     // emerald-400
      'border-style': 'dashed',
      'border-width': 3,
      'color': '#ecfdf5',
      'text-border-color': '#059669',
      'z-index': 20,
    },
  },

  // Mixer Node (Severe Obfuscator)
  {
    selector: 'node[?is_mixer]',
    style: {
      'width': 50,
      'height': 50,
      'background-color': '#d97706', // amber-600
      'border-color': '#fde68a',     // amber-200
      'border-width': 3,
      'color': '#fffbeb',
      'text-border-color': '#f59e0b',
      'shadow-blur': 14,
      'shadow-color': '#f59e0b',
      'shadow-opacity': 0.45,
      'z-index': 22,
    },
  },

  // Cross-Chain Bridge Node
  {
    selector: 'node[?is_bridge]',
    style: {
      'width': 50,
      'height': 50,
      'background-color': '#7c3aed', // violet-600
      'border-color': '#ddd6fe',     // violet-200
      'border-width': 3,
      'color': '#f5f3ff',
      'text-border-color': '#8b5cf6',
      'shadow-blur': 14,
      'shadow-color': '#8b5cf6',
      'shadow-opacity': 0.45,
      'z-index': 22,
    },
  },

  // OFAC Sanctioned Entity
  {
    selector: 'node[entity_type = "sanctioned"]',
    style: {
      'width': 54,
      'height': 54,
      'background-color': '#b91c1c',
      'border-color': '#fee2e2',
      'border-style': 'double',
      'border-width': 5,
      'color': '#fee2e2',
      'text-border-color': '#ef4444',
      'shadow-blur': 18,
      'shadow-color': '#dc2626',
      'shadow-opacity': 0.6,
      'z-index': 30,
    },
  },

  // Selected Node State
  {
    selector: 'node:selected',
    style: {
      'border-width': 4.5,
      'border-color': '#38bdf8', // sky-400
      'border-opacity': 1,
      'shadow-blur': 22,
      'shadow-color': '#38bdf8',
      'shadow-opacity': 0.8,
      'shadow-offset-x': 0,
      'shadow-offset-y': 0,
    },
  },

  // On-Primary-Path Node
  {
    selector: 'node[?on_primary_path]',
    style: {
      'border-color': '#38bdf8',
      'border-width': 3.5,
      'shadow-blur': 16,
      'shadow-color': '#38bdf8',
      'shadow-opacity': 0.5,
    },
  },

  // Base Edge Style
  {
    selector: 'edge',
    style: {
      'width': 2,
      'line-color': '#475569',       // slate-600
      'target-arrow-color': '#475569',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'arrow-scale': 0.9,
      'opacity': 0.7,
      'transition-property': 'width, line-color, target-arrow-color, opacity',
      'transition-duration': '0.2s',
    },
  },

  // Highlighted Primary Path Edge (The Gold Line to VASP)
  {
    selector: 'edge[?on_primary_path]',
    style: {
      'width': 4.5,
      'line-color': '#06b6d4',       // cyan-500
      'target-arrow-color': '#06b6d4',
      'arrow-scale': 1.3,
      'opacity': 1.0,
      'z-index': 18,
      'line-style': 'solid',
    },
  },

  // Selected / Hovered Edge
  {
    selector: 'edge:selected',
    style: {
      'width': 5,
      'line-color': '#67e8f9',
      'target-arrow-color': '#67e8f9',
      'opacity': 1,
      'z-index': 20,
    },
  },
];

export const LAYOUT_CONFIG = (startAddress) => ({
  name: 'breadthfirst',
  directed: true,
  circle: false,
  roots: startAddress ? [`node[id = "${startAddress}"]`] : undefined,
  padding: 40,
  spacingFactor: 1.45,
  animate: true,
  animationDuration: 400,
  avoidOverlap: true,
  nodeDimensionsIncludeLabels: true,
});
