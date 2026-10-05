/**
 * API Client for the ChainSAHYOG VASP Attribution Engine.
 * 
 * Proxied through Vite (/api/* -> http://127.0.0.1:8000/*).
 */

const API_BASE = '/api';

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error(`Health probe failed: HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchDemos() {
  const res = await fetch(`${API_BASE}/demos`);
  if (!res.ok) {
    throw new Error(`Failed to load demos: HTTP ${res.status}`);
  }
  return res.json();
}

export async function runTrace({
  address,
  chainId = 1,
  maxDepth = 4,
  dustThreshold = 0.001,
  mode = 'auto',
  save = false,
  asOfBlock = null,
}) {
  const params = new URLSearchParams({
    address: address.trim(),
    chain_id: chainId.toString(),
    max_depth: maxDepth.toString(),
    dust_threshold: dustThreshold.toString(),
    mode,
    save: save.toString(),
  });
  // Pin the trace to a past height; omitted, the backend pins it to the head.
  if (asOfBlock !== null && asOfBlock !== '' && asOfBlock !== undefined) {
    params.set('as_of_block', String(asOfBlock));
  }

  const res = await fetch(`${API_BASE}/trace?${params.toString()}`);
  
  if (!res.ok) {
    let errorMessage = `HTTP error ${res.status}`;
    try {
      const errorData = await res.json();
      if (errorData?.detail) {
        errorMessage = errorData.detail;
      }
    } catch {
      // Non-JSON response
    }
    throw new Error(errorMessage);
  }

  return res.json();
}

export function getReportUrl({
  address,
  chainId = 1,
  maxDepth = 4,
  dustThreshold = 0.001,
  mode = 'auto',
  asOfBlock = null,
}) {
  const params = new URLSearchParams({
    address: address.trim(),
    chain_id: chainId.toString(),
    max_depth: maxDepth.toString(),
    dust_threshold: dustThreshold.toString(),
    mode,
  });
  if (asOfBlock !== null && asOfBlock !== undefined) params.set('as_of_block', String(asOfBlock));
  return `${API_BASE}/report?${params.toString()}`;
}
