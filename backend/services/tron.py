"""
TronGrid client: Tron history behind the same interface as EtherscanClient.

The tracer asks any client for the same things - a wallet's transfers as of a
height, the chain head, a block's timestamp, the block at a time, and a
wallet's chain-wide sender count - so it walks Tron exactly as it walks an EVM
chain. This module answers those questions for Tron, keyless, through
TronGrid's public API, accepting its lower throttle.

WHAT IS FOLLOWED
  * Native TRX: TransferContract rows only, and only successful ones. Every
    other contract type (resource delegation, freezing, votes, smart-contract
    calls) moves no TRX between wallets in a way the trail can follow, and is
    counted as filtered, never followed.
  * TRC-20: transfers of tokens on config.TOKEN_CONTRACTS for Tron, matched on
    the CONTRACT ADDRESS, never the symbol. USDT is pinned to
    TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t at 6 decimals - our own figure, not the
    API's. A token calling itself "USDT" from any other contract is skipped and
    counted.
  * Not covered: internal transactions (TRX moved by contract execution), and
    TRC-10 tokens. Same limitation as the EVM client, stated in the report.

PINNING. TronGrid filters by timestamp, not block, so an as-of height is
turned into its block timestamp (one call, cached) and every history request is
capped at it (`max_timestamp`), then filtered again here. Tron's TRC-20 rows
carry no block number; their timestamp is the block's, so the cap is exact.

ADDRESSES are canonical base58 (core/addresses.py). TronGrid returns native
rows in 41-hex form; they are converted on parse, so one wallet is one key.
"""

from __future__ import annotations

import asyncio
import time

import httpx

from app import config
from core import addresses
from services.etherscan import Transfer

TRON_CHAIN_ID = 728126428
BASE_URL = "https://api.trongrid.io"
PAGE = 200  # TronGrid's maximum page size


class TronError(Exception):
    """TronGrid could not answer."""


class TronClient:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()
        self._last = 0.0
        self.api_calls = 0
        self.cache_hits = 0
        self.skipped_tokens: dict[tuple[int, str], int] = {}
        self.filtered_contract_types: dict[str, int] = {}
        # (chain_id, address, as_of_block) -> reach, as EtherscanClient keeps it.
        self.history_reach: dict[tuple, dict] = {}
        self._cache: dict[tuple, list[Transfer]] = {}
        self._block_ts: dict[int, int] = {}  # block -> timestamp in ms
        self._misc: dict[tuple, object] = {}

    # --- plumbing ---------------------------------------------------------------

    def reset_stats(self) -> None:
        self.api_calls = 0
        self.cache_hits = 0
        self.skipped_tokens = {}
        self.filtered_contract_types = {}

    def clear_cache(self) -> None:
        self._cache.clear()
        self._misc.clear()

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def _call(self, method: str, path: str, **kwargs) -> dict:
        """One throttled TronGrid request, with backoff on the keyless throttle."""
        network_failures = 0
        for attempt in range(4 + config.NETWORK_RETRIES):
            async with self._lock:
                wait = config.TRONGRID_REQUEST_DELAY_SEC - (time.monotonic() - self._last)
                if wait > 0:
                    await asyncio.sleep(wait)
                if self._client is None or self._client.is_closed:
                    self._client = httpx.AsyncClient(timeout=30.0)
                try:
                    response = await self._client.request(method, BASE_URL + path, **kwargs)
                    network_error = None
                except httpx.HTTPError as exc:
                    network_error = exc
                finally:
                    self._last = time.monotonic()
                self.api_calls += 1
            if network_error is not None:
                # Transient network failures are retried with backoff, as on EVM.
                network_failures += 1
                if network_failures > config.NETWORK_RETRIES:
                    raise TronError(
                        f"Network error talking to TronGrid (after {network_failures} tries): {network_error}"
                    ) from network_error
                await asyncio.sleep(2 ** network_failures)
                continue
            if response.status_code in (403, 429):
                # Keyless requests over the limit are blocked for about 30 s.
                await asyncio.sleep(31 if attempt else 5)
                continue
            if response.status_code != 200:
                raise TronError(f"TronGrid returned HTTP {response.status_code}")
            try:
                return response.json()
            except ValueError as exc:
                raise TronError("TronGrid returned a non-JSON response") from exc
        raise TronError("TronGrid kept refusing requests (rate limited)")

    # --- blocks -----------------------------------------------------------------

    async def latest_block(self, chain_id: int = TRON_CHAIN_ID) -> int:
        """The head: the latest block TronGrid reports."""
        body = await self._call("POST", "/wallet/getnowblock", json={})
        raw = (body.get("block_header") or {}).get("raw_data") or {}
        number = int(raw.get("number"))
        self._block_ts[number] = int(raw.get("timestamp"))
        return number

    async def _block_ms(self, block: int) -> int:
        if block not in self._block_ts:
            body = await self._call("POST", "/wallet/getblockbynum", json={"num": int(block)})
            raw = (body.get("block_header") or {}).get("raw_data") or {}
            if "timestamp" not in raw:
                raise TronError(f"TronGrid has no block {block}")
            self._block_ts[int(block)] = int(raw["timestamp"])
        return self._block_ts[int(block)]

    async def block_timestamp(self, block: int, chain_id: int = TRON_CHAIN_ID) -> int:
        """A block's timestamp in seconds."""
        return (await self._block_ms(block)) // 1000

    async def block_at(self, timestamp: int, chain_id: int = TRON_CHAIN_ID, closest: str = "before") -> int:
        """The last block at or before `timestamp` (Tron produces a block every ~3 s)."""
        target = int(timestamp) * 1000
        head = await self.latest_block()
        head_ms = self._block_ts[head]
        guess = max(1, head - max(0, head_ms - target) // 3000)
        for _ in range(8):
            ms = await self._block_ms(guess)
            step = (target - ms) // 3000
            if step == 0:
                break
            guess = max(1, min(head, guess + step))
        while guess > 1 and await self._block_ms(guess) > target:
            guess -= 1
        return guess

    # --- history ----------------------------------------------------------------

    async def _pages(self, path: str, params: dict, max_pages: int) -> tuple[list, bool]:
        """Rows newest first, following TronGrid's fingerprint cursor."""
        rows, fingerprint, truncated = [], None, False
        for page in range(max_pages):
            query = dict(params)
            if fingerprint:
                query["fingerprint"] = fingerprint
            body = await self._call("GET", path, params=query)
            if body.get("success") is False:
                raise TronError(f"TronGrid error: {body.get('error') or body}")
            rows.extend(body.get("data") or [])
            fingerprint = (body.get("meta") or {}).get("fingerprint")
            if not fingerprint:
                break
            if page == max_pages - 1:
                truncated = True
        return rows, truncated

    async def get_wallet_transfers(
        self, address: str, chain_id: int | None = TRON_CHAIN_ID, as_of_block: int | None = None
    ) -> list[Transfer]:
        """Every followed TRX and TRC-20 transfer touching `address`, as of the height."""
        chain_id = TRON_CHAIN_ID if chain_id is None else int(chain_id)
        wallet = addresses.normalize(address, "tron")
        key = (chain_id, wallet, as_of_block)
        if key in self._cache:
            self.cache_hits += 1
            return self._cache[key]
        cap_ms = await self._block_ms(as_of_block) if as_of_block is not None else None
        common = {"limit": PAGE, "only_confirmed": "true", "order_by": "block_timestamp,desc"}
        if cap_ms is not None:
            common["max_timestamp"] = cap_ms
        max_pages = config.TRON_MAX_HISTORY_PAGES

        native, native_cut = await self._pages(f"/v1/accounts/{wallet}/transactions", common, max_pages)
        token, token_cut = await self._pages(f"/v1/accounts/{wallet}/transactions/trc20", common, max_pages)

        transfers: list[Transfer] = []
        for row in native:
            t = self._parse_native(row, cap_ms)
            if t is not None:
                transfers.append(t)
        for row in token:
            t = self._parse_trc20(row, wallet, chain_id, cap_ms)
            if t is not None:
                transfers.append(t)

        def reach(rows, cut, with_blocks):
            stamps = [int(r.get("block_timestamp") or 0) // 1000 for r in rows if r.get("block_timestamp")]
            blocks = [int(r.get("blockNumber") or 0) for r in rows if with_blocks and r.get("blockNumber")]
            return {"rows": len(rows), "pages": None, "truncated": cut,
                    "oldest": min(stamps) if stamps else None,
                    "oldest_block": min(blocks) if blocks else None, "end_block": as_of_block}

        self.history_reach[key] = {"native": reach(native, native_cut, True),
                                   "token": reach(token, token_cut, False)}
        self._cache[key] = transfers
        return transfers

    def _parse_native(self, row: dict, cap_ms: int | None) -> Transfer | None:
        raw = row.get("raw_data")
        if not raw:  # an internal-transaction record: not followed
            self.filtered_contract_types["internal"] = self.filtered_contract_types.get("internal", 0) + 1
            return None
        contract = (raw.get("contract") or [{}])[0]
        kind = contract.get("type", "")
        if kind != "TransferContract":
            self.filtered_contract_types[kind] = self.filtered_contract_types.get(kind, 0) + 1
            return None
        if (row.get("ret") or [{}])[0].get("contractRet", "SUCCESS") != "SUCCESS":
            self.filtered_contract_types["failed"] = self.filtered_contract_types.get("failed", 0) + 1
            return None
        ts_ms = int(row.get("block_timestamp") or 0)
        if cap_ms is not None and ts_ms > cap_ms:
            return None
        value = (contract.get("parameter") or {}).get("value") or {}
        frm = addresses.try_normalize(value.get("owner_address"), "tron")
        to = addresses.try_normalize(value.get("to_address"), "tron")
        if not frm or not to:
            return None
        return Transfer(
            hash=row.get("txID", ""), from_addr=frm, to_addr=to,
            value=int(value.get("amount") or 0) / 1_000_000, timestamp=ts_ms // 1000,
            block=int(row.get("blockNumber") or 0), asset="TRX", contract=None, decimals=6,
        )

    def _parse_trc20(self, row: dict, wallet: str, chain_id: int, cap_ms: int | None) -> Transfer | None:
        if row.get("type", "Transfer") != "Transfer":
            return None
        ts_ms = int(row.get("block_timestamp") or 0)
        if cap_ms is not None and ts_ms > cap_ms:
            return None
        contract = addresses.try_normalize((row.get("token_info") or {}).get("address"), "tron")
        entry = config.token_asset(chain_id, contract or "")
        frm = addresses.try_normalize(row.get("from"), "tron")
        to = addresses.try_normalize(row.get("to"), "tron")
        if entry is None:
            # Not on our verified list - including any token merely CALLING itself USDT.
            if frm == wallet:
                symbol = str((row.get("token_info") or {}).get("symbol") or "?")
                k = (chain_id, symbol)
                self.skipped_tokens[k] = self.skipped_tokens.get(k, 0) + 1
            return None
        if not frm or not to:
            return None
        symbol, decimals = entry
        return Transfer(
            hash=row.get("transaction_id", ""), from_addr=frm, to_addr=to,
            value=int(row.get("value") or 0) / (10 ** decimals), timestamp=ts_ms // 1000,
            # TRC-20 rows carry no block number; the timestamp is the block's, and
            # the as-of cap is applied on it above.
            block=0, asset=symbol, contract=contract, decimals=decimals,
        )

    async def get_inbound_senders(
        self, address: str, chain_id: int = TRON_CHAIN_ID, as_of_block: int | None = None
    ) -> dict:
        """The calibrated fan-in measure: one page of each endpoint, as of the height."""
        wallet = addresses.normalize(address, "tron")
        key = ("senders", wallet, as_of_block)
        if key in self._misc:
            self.cache_hits += 1
            return self._misc[key]
        cap_ms = await self._block_ms(as_of_block) if as_of_block is not None else None
        common = {"limit": PAGE, "only_confirmed": "true", "order_by": "block_timestamp,desc"}
        if cap_ms is not None:
            common["max_timestamp"] = cap_ms
        native, n_more = await self._pages(f"/v1/accounts/{wallet}/transactions", common, 1)
        token, t_more = await self._pages(f"/v1/accounts/{wallet}/transactions/trc20", common, 1)
        transfers = [t for t in (self._parse_native(r, cap_ms) for r in native) if t] + \
                    [t for t in (self._parse_trc20(r, wallet, TRON_CHAIN_ID, cap_ms) for r in token) if t]
        incoming = [t for t in transfers if t.to_addr == wallet and t.from_addr != wallet]
        outgoing = [t for t in transfers if t.from_addr == wallet]
        out = {
            "senders": len({t.from_addr for t in incoming}),
            "value_senders": len({t.from_addr for t in incoming
                                  if t.value >= config.dust_threshold_for(t.asset, None)}),
            "recipients": len({t.to_addr for t in outgoing}),
            "value_recipients": len({t.to_addr for t in outgoing
                                     if t.value >= config.dust_threshold_for(t.asset, None)}),
            "rows": len(incoming), "out_rows": len(outgoing), "calls": 2,
            "complete": not n_more and not t_more,
        }
        self._misc[key] = out
        return out


_client: TronClient | None = None


def get_client() -> TronClient:
    global _client
    if _client is None:
        _client = TronClient()
    return _client
