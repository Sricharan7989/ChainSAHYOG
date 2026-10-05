/**
 * Formatting utilities for cryptocurrency addresses, asset values, and forensics.
 */

/**
 * Split a graph node id into its chain and its bare address.
 *
 * Once a trace crosses a chain the backend distinguishes the same address on two
 * chains, and node ids become "arbitrum:0xabc...". Everything the reader sees has
 * to work on the bare address - an explorer link with the prefix would 404, and a
 * shortened "arbitrum:0xabcd…7890" would be a string that resolves to nothing.
 */
export function splitNodeId(nodeId) {
  const id = typeof nodeId === 'string' ? nodeId : '';
  const cut = id.indexOf(':');
  if (cut === -1) return { chain: '', address: id };
  return { chain: id.slice(0, cut), address: id.slice(cut + 1) };
}

/** The bare address of a node id, with any chain prefix removed. */
export function bareAddress(nodeId) {
  return splitNodeId(nodeId).address;
}

export function shortAddress(address, lead = 6, tail = 4) {
  const { address: bare } = splitNodeId(address);
  if (!bare || typeof bare !== 'string') return '';
  if (bare.length <= lead + tail) return bare;
  return `${bare.slice(0, lead)}…${bare.slice(-tail)}`;
}

export function formatNumber(num, maxDecimals = 4) {
  if (num === null || num === undefined || isNaN(num)) return '0';
  return Number(num).toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: maxDecimals,
  });
}

export function formatAssets(assetsMap) {
  if (!assetsMap || typeof assetsMap !== 'object') return 'None';
  const entries = Object.entries(assetsMap).filter(([, val]) => val > 0);
  if (entries.length === 0) return '0.00';
  return entries
    .map(([symbol, val]) => `${formatNumber(val, symbol === 'ETH' || symbol === 'POL' || symbol === 'BNB' ? 4 : 2)} ${symbol}`)
    .join(' · ');
}

export function formatTimestamp(timestampSec) {
  if (!timestampSec) return 'Unknown date';
  const date = new Date(timestampSec * 1000);
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Public block explorers, per chain.
 *
 * A link is a claim that the reader can go and check our work. Pointing an
 * Arbitrum address at Etherscan produces a page that loads fine and shows an
 * unrelated account, which is worse than a dead link - so a crossed route must
 * change explorer, not just change wording.
 */
const CHAIN_EXPLORERS = {
  ethereum: 'https://etherscan.io',
  arbitrum: 'https://arbiscan.io',
  polygon: 'https://polygonscan.com',
  bnb: 'https://bscscan.com',
  tron: 'https://tronscan.org',
};

// Tronscan is a single-page app: its pages live under "#/", with "transaction"
// rather than "tx". A link built the EVM way would load Tronscan's home page.
const isTronscan = (base) => /tronscan\.org/.test(base || '');

/** The explorer for a chain, falling back to the one the trace started on. */
export function explorerForChain(chain, fallback) {
  const key = (chain || '').toLowerCase();
  return CHAIN_EXPLORERS[key] || fallback || CHAIN_EXPLORERS.ethereum;
}

export function getExplorerUrl(explorerBase, address) {
  const bare = bareAddress(address);
  const base = (explorerBase || 'https://etherscan.io').replace(/\/$/, '');
  if (isTronscan(base)) return `${base}/#/address/${bare}`;
  return `${base}/address/${bare}`;
}

/**
 * Explorer URL for a graph node, picking the explorer that matches the node's own
 * chain. Use this instead of getExplorerUrl wherever a node id is available.
 */
export function explorerUrlForNode(explorerBase, nodeId) {
  const { chain, address } = splitNodeId(nodeId);
  return getExplorerUrl(explorerForChain(chain, explorerBase), address);
}

export function getTxUrl(explorerBase, txHash) {
  const base = (explorerBase || 'https://etherscan.io').replace(/\/$/, '');
  if (isTronscan(base)) return `${base}/#/transaction/${txHash}`;
  return `${base}/tx/${txHash}`;
}

export function getRiskBadgeConfig(severity) {
  switch (severity?.toLowerCase()) {
    case 'critical':
      return {
        bg: 'bg-[#0a0a0a] text-red-500 border-red-500/50',
        dot: 'bg-red-500',
        label: 'CRITICAL',
      };
    case 'high':
      return {
        bg: 'bg-[#0a0a0a] text-amber-500 border-amber-500/50',
        dot: 'bg-amber-500',
        label: 'HIGH RISK',
      };
    case 'medium':
      return {
        bg: 'bg-[#0a0a0a] text-[#627EEA] border-[#627EEA]',
        dot: 'bg-[#627EEA]',
        label: 'MEDIUM RISK',
      };
    default:
      return {
        bg: 'bg-[#0a0a0a] text-[#a3a3a3] border-[#2a2a2a]',
        dot: 'bg-[#a3a3a3]',
        label: 'NOTICE',
      };
  }
}
