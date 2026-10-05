/**
 * Address keys and format checks, per chain family.
 *
 * Mirrors backend/core/addresses.py so the UI never lowercases an address on a
 * chain where case is part of it (Tron base58, legacy Bitcoin). The backend is
 * authoritative: it verifies checksums and returns canonical node ids; this only
 * compares them safely and gives the search box a shape check before submit.
 */

const FAMILY_BY_CHAIN = {
  1: 'evm', 137: 'evm', 56: 'evm', 42161: 'evm', 10: 'evm', 8453: 'evm',
  728126428: 'tron',
  ethereum: 'evm', polygon: 'evm', bnb: 'evm', arbitrum: 'evm', optimism: 'evm', base: 'evm',
  tron: 'tron',
  bitcoin: 'bitcoin',
};

const EVM_RE = /^0[xX][0-9a-fA-F]{40}$/;

// Shape only. Checksums are verified server-side.
const SHAPE = {
  evm: EVM_RE,
  tron: /^(T[1-9A-HJ-NP-Za-km-z]{33}|41[0-9a-fA-F]{40})$/,
  bitcoin: /^([13][1-9A-HJ-NP-Za-km-z]{25,34}|(bc1|BC1)[02-9ac-hj-np-zAC-HJ-NP-Z]{6,87})$/,
};

const DESCRIPTION = {
  evm: 'a 42-character hexadecimal EVM address beginning with 0x',
  tron: 'a Tron address (base58 starting with T, or hex starting with 41)',
  bitcoin: 'a Bitcoin mainnet address (1..., 3... or bc1...)',
};

export function addressFamily(chain) {
  return FAMILY_BY_CHAIN[chain ?? 1] || 'evm';
}

/**
 * The comparison key for an address or graph node id ("polygon:0x..."). EVM hex
 * is lowercased because its case is only a checksum; anything else is kept
 * exactly, because there the case IS the address.
 */
export function addrKey(id) {
  if (id === null || id === undefined) return id;
  const text = String(id);
  const colon = text.indexOf(':');
  const bare = colon === -1 ? text : text.slice(colon + 1);
  return EVM_RE.test(bare) ? text.toLowerCase() : text;
}

export function sameAddress(a, b) {
  return !!a && !!b && addrKey(a) === addrKey(b);
}

export function looksLikeAddress(address, chain) {
  return SHAPE[addressFamily(chain)].test((address || '').trim());
}

export function describeAddressFormat(chain) {
  return DESCRIPTION[addressFamily(chain)];
}
