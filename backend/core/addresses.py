"""
Per-chain address handling: one normaliser and one validator per address family.

WHY THIS EXISTS. Every address used to be keyed by `address.strip().lower()`.
That is correct on EVM chains, where hex is case-insensitive and the mixed case
of an EIP-55 address is only a checksum. It silently corrupts the other two
families this project will trace:

  * Tron base58 (T...) is case-sensitive. Lowercasing produces a different
    string that fails its checksum - or, in principle, a different address.
    Tron also has a hex form (41 + 20 bytes) that is the SAME address, and the
    two must resolve to one wallet, not two.
  * Bitcoin legacy base58 (1..., 3...) is case-sensitive in the same way.
    Bech32 (bc1...) is not: it is defined case-insensitive, valid in all-lower
    or all-upper, and lowercase is its canonical form.

So every address is normalised and validated FOR ITS CHAIN, here and nowhere
else. The format check is also the guard that stops an Ethereum label from ever
matching a Tron or Bitcoin address: an address that does not parse for the
chain it is looked up on cannot match anything on that chain.

CANONICAL FORMS
  evm      0x + 40 lowercase hex
  tron     base58check, T... (34 chars). Chosen over hex because it is what
           Tronscan, wallets, exchange deposit pages and the OFAC SDN list print,
           so a stored address can be compared by eye with any public source.
           The hex form is derived on demand (tron_hex) for APIs that want it.
  bitcoin  legacy base58 exactly as given (checksum verified); bech32/bech32m
           lowercased (checksum verified). Mainnet only.

Checksums are verified for base58check and bech32. EIP-55 mixed-case checksums
are NOT verified (that needs Keccak-256, which hashlib does not provide); an EVM
address is accepted on shape, as it always was.
"""

from __future__ import annotations

import hashlib
import re

# --- Families -----------------------------------------------------------------

EVM, TRON, BITCOIN = "evm", "tron", "bitcoin"

# Every chain slug this project knows how to KEY, including the two it cannot
# trace yet. Adding a chain is a row here and a row in config.CHAINS.
FAMILY_BY_CHAIN: dict[str, str] = {
    "ethereum": EVM,
    "polygon": EVM,
    "bnb": EVM,
    "arbitrum": EVM,
    "optimism": EVM,
    "base": EVM,
    "tron": TRON,
    "bitcoin": BITCOIN,
}

CASE_SENSITIVE_FAMILIES = {TRON, BITCOIN}


class InvalidAddress(ValueError):
    """An address that does not parse for the chain it was given on."""


def family(chain: str | None) -> str | None:
    """The address family of a chain slug, or None for a chain we cannot key."""
    return FAMILY_BY_CHAIN.get((chain or "ethereum").strip().lower())


def is_case_sensitive(chain: str | None) -> bool:
    """True where changing an address's case changes (or breaks) the address."""
    return family(chain) in CASE_SENSITIVE_FAMILIES


# --- base58check (Tron, Bitcoin legacy) -----------------------------------------

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX = {c: i for i, c in enumerate(_B58)}


def _b58decode_check(text: str) -> bytes | None:
    """Payload of a base58check string, or None if it is malformed or fails its checksum."""
    if not text or any(c not in _B58_INDEX for c in text):
        return None
    n = 0
    for c in text:
        n = n * 58 + _B58_INDEX[c]
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    raw = b"\x00" * (len(text) - len(text.lstrip("1"))) + raw
    if len(raw) < 5:
        return None
    payload, checksum = raw[:-4], raw[-4:]
    if hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4] != checksum:
        return None
    return payload


def _b58encode_check(payload: bytes) -> str:
    raw = payload + hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    n = int.from_bytes(raw, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    return "1" * (len(raw) - len(raw.lstrip(b"\x00"))) + out


# --- bech32 / bech32m (Bitcoin segwit) -------------------------------------------

_BECH32 = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_CONST, _BECH32M_CONST = 1, 0x2BC830A3


def _bech32_polymod(values: list[int]) -> int:
    gen = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    chk = 1
    for v in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i in range(5):
            chk ^= gen[i] if (top >> i) & 1 else 0
    return chk


def _convertbits(data: list[int], frombits: int, tobits: int) -> list[int] | None:
    acc = bits = 0
    out, maxv = [], (1 << tobits) - 1
    for value in data:
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            out.append((acc >> bits) & maxv)
    if bits >= frombits or ((acc << (tobits - bits)) & maxv):
        return None
    return out


def _segwit_ok(text: str) -> bool:
    """BIP-173 / BIP-350 mainnet segwit address check on an already-lowercased string."""
    hrp, sep, data = text.rpartition("1")
    if hrp != "bc" or not sep or len(data) < 6 or any(c not in _BECH32 for c in data):
        return False
    values = [_BECH32.index(c) for c in data]
    const = _bech32_polymod([ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp] + values)
    version, program5 = values[0], values[1:-6]
    if version > 16:
        return False
    # v0 uses bech32; v1 and later use bech32m. The wrong one is invalid.
    if const != (_BECH32_CONST if version == 0 else _BECH32M_CONST):
        return False
    program = _convertbits(program5, 5, 8)
    if program is None or not 2 <= len(program) <= 40:
        return False
    return not (version == 0 and len(program) not in (20, 32))


# --- Per-family normalisers -------------------------------------------------------

_EVM_RE = re.compile(r"0[xX][0-9a-fA-F]{40}")  # hex, prefix included, is case-insensitive
_TRON_HEX_RE = re.compile(r"41[0-9a-fA-F]{40}")


def _normalize_evm(a: str) -> str | None:
    return a.lower() if _EVM_RE.fullmatch(a) else None


def _normalize_tron(a: str) -> str | None:
    if _TRON_HEX_RE.fullmatch(a):
        # The hex form of the same account: 0x41 + 20 bytes. Re-encoded so both
        # spellings key the same wallet.
        return _b58encode_check(bytes.fromhex(a))
    payload = _b58decode_check(a)
    if payload is None or len(payload) != 21 or payload[0] != 0x41:
        return None
    return a  # base58 is canonical, exactly as given: case is part of it


def _normalize_bitcoin(a: str) -> str | None:
    if a[:3].lower() == "bc1":
        # Bech32 is case-insensitive but must not be MIXED case (BIP-173).
        if a != a.lower() and a != a.upper():
            return None
        low = a.lower()
        return low if _segwit_ok(low) else None
    payload = _b58decode_check(a)
    # 0x00 = P2PKH (1...), 0x05 = P2SH (3...). Mainnet only.
    if payload is None or len(payload) != 21 or payload[0] not in (0x00, 0x05):
        return None
    return a


_NORMALIZERS = {EVM: _normalize_evm, TRON: _normalize_tron, BITCOIN: _normalize_bitcoin}


# --- Public API -----------------------------------------------------------------


def try_normalize(address: str | None, chain: str | None) -> str | None:
    """The canonical form of `address` on `chain`, or None if it is not valid there."""
    fam = family(chain)
    if fam is None or not isinstance(address, str):
        return None
    a = address.strip()
    return _NORMALIZERS[fam](a) if a else None


def normalize(address: str | None, chain: str | None) -> str:
    """The canonical form of `address` on `chain`. Raises InvalidAddress if it does not parse."""
    out = try_normalize(address, chain)
    if out is None:
        raise InvalidAddress(
            f"{address!r} is not a valid {describe(chain)} address"
            if family(chain)
            else f"no address format is defined for chain {chain!r}"
        )
    return out


def is_valid(address: str | None, chain: str | None) -> bool:
    """True when `address` parses for `chain`. Format and checksum only, not existence."""
    return try_normalize(address, chain) is not None


def same(a: str | None, b: str | None, chain: str | None) -> bool:
    """Whether two spellings name the same wallet on `chain`. Invalid never matches."""
    na, nb = try_normalize(a, chain), try_normalize(b, chain)
    return na is not None and na == nb


def families_for(address: str | None) -> set[str]:
    """Which families an address parses under, regardless of chain. For error messages."""
    return {fam for fam in _NORMALIZERS if try_normalize(address, _any_chain(fam)) is not None}


def tron_hex(address: str) -> str:
    """The 41-prefixed hex form of a Tron address, for APIs that take hex."""
    payload = _b58decode_check(normalize(address, "tron"))
    return payload.hex()


def describe(chain: str | None) -> str:
    """Human description of what a valid address looks like on a chain."""
    return {
        EVM: "EVM (0x followed by 40 hex characters)",
        TRON: "Tron (base58 T... with a valid checksum, or hex 41 followed by 40 hex characters)",
        BITCOIN: "Bitcoin mainnet (legacy 1.../3... or bech32 bc1..., with a valid checksum)",
    }.get(family(chain) or "", f"{chain}")


def _any_chain(fam: str) -> str:
    return next(slug for slug, f in FAMILY_BY_CHAIN.items() if f == fam)
