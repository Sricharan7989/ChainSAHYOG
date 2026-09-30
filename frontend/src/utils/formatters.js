/**
 * Formatting utilities for cryptocurrency addresses, asset values, and forensics.
 */

export function shortAddress(address, lead = 6, tail = 4) {
  if (!address || typeof address !== 'string') return '';
  if (address.length <= lead + tail) return address;
  return `${address.slice(0, lead)}…${address.slice(-tail)}`;
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

export function getExplorerUrl(explorerBase, address) {
  const base = explorerBase || 'https://etherscan.io';
  return `${base.replace(/\/$/, '')}/address/${address}`;
}

export function getTxUrl(explorerBase, txHash) {
  const base = explorerBase || 'https://etherscan.io';
  return `${base.replace(/\/$/, '')}/tx/${txHash}`;
}

export function getRiskBadgeConfig(severity) {
  switch (severity?.toLowerCase()) {
    case 'critical':
      return {
        bg: 'bg-red-500/10 text-red-400 border-red-500/30',
        dot: 'bg-red-500',
        label: 'CRITICAL',
      };
    case 'high':
      return {
        bg: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
        dot: 'bg-amber-500',
        label: 'HIGH RISK',
      };
    case 'medium':
      return {
        bg: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
        dot: 'bg-purple-500',
        label: 'MEDIUM RISK',
      };
    default:
      return {
        bg: 'bg-zinc-800 text-zinc-300 border-zinc-700',
        dot: 'bg-zinc-400',
        label: 'NOTICE',
      };
  }
}
