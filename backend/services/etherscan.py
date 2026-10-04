"""
Etherscan data layer — fetches a wallet's transaction history, with caching.

WHY this is a separate module:
The tracer's job is graph logic. Everything ugly about talking to a third-party
API — rate limits, pagination, the fact that Etherscan reports errors with
HTTP 200 and a status field, wei-to-ETH conversion — is quarantined here. The
tracer asks one question, "what left this wallet?", and gets back clean data.

WHY the cache matters:
A forward trace revisits the same wallet constantly. Criminal flows loop and
re-converge — wallet A pays B and C, and both pay D — so a naive tracer would
refetch D once per inbound path. Every refetch is a network round trip against
a 5-calls/sec free tier, so the cache is the difference between a trace that
takes seconds and one that takes minutes. It is keyed by lowercased address and
lives for the process, so the demo address stays warm between traces.
"""

import asyncio
import time
from dataclasses import dataclass

import httpx

from app import config

# Ethereum addresses are 20 bytes / 40 hex chars, plus the "0x" prefix.
# Etherscan returns them EIP-55 checksummed (mixed case) but treats them
# case-insensitively; we lowercase everywhere so the graph never holds the
# same wallet twice under two spellings.
ADDRESS_LENGTH = 42


class EtherscanError(RuntimeError):
    """Upstream refused or failed. Surfaced to the caller as a 502, never swallowed."""


@dataclass(frozen=True)
class Transfer:
    """
    One value-bearing transfer - native or ERC-20 - normalised from Etherscan.

    `value` is in WHOLE UNITS of `asset`, already scaled by that token's own
    decimals. Assuming 18 everywhere would report a 100 USDT payment as
    0.0000000000001 USDT, because USDT and USDC use 6.

    `contract` is None for the chain's native token and the token address
    otherwise, which is what makes two tokens sharing a symbol distinguishable.

    `tx_index` is the transaction's position within its block. It is carried for
    FIFO taint accounting: a block gives every transaction in it the SAME
    timestamp, so timestamps alone cannot order two transfers out of one wallet,
    and the order decides which funds were spent first.
    """

    hash: str
    from_addr: str
    to_addr: str
    value: float
    timestamp: int  # unix epoch seconds
    block: int
    asset: str = "ETH"
    contract: str | None = None
    decimals: int = 18
    tx_index: int = 0

    @property
    def is_native(self) -> bool:
        return self.contract is None


def normalize_address(address: str) -> str:
    """Lowercase + strip. The single source of truth for how an address is keyed."""
    return address.strip().lower()


def is_valid_address(address: str) -> bool:
    """Shape check only — does not verify the address exists on chain."""
    a = address.strip()
    if len(a) != ADDRESS_LENGTH or not a.startswith("0x"):
        return False
    try:
        int(a[2:], 16)
    except ValueError:
        return False
    return True


class EtherscanClient:
    """
    Async Etherscan client with an in-memory cache and a request throttle.

    The throttle serialises requests rather than running a token bucket on
    purpose: exceeding the free tier's 5 calls/sec gets the key temporarily
    blocked, and a blocked key mid-demo is far worse than a trace that takes
    an extra second.
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        # (chain_id, address) -> transfers sent BY that address. The chain is
        # part of the key because the same address on another network is another
        # wallet entirely; a flat cache would answer with the wrong chain's data.
        self._cache: dict[tuple[int, str], list[Transfer]] = {}
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0
        self.api_calls = 0
        self.cache_hits = 0
        # (chain_id, claimed symbol) -> how many transfers we declined to
        # follow, for THIS trace. Keyed by chain because a symbol that is a real
        # asset on one chain can be an impostor on another.
        self.skipped_tokens: dict[tuple[int, str], int] = {}
        # The same tally per wallet, cached alongside that wallet's transfers.
        #
        # WHY THIS EXISTS. The per-trace tally above is built while PARSING rows,
        # so a cache hit used to contribute nothing to it: the second trace of a
        # session silently lost its "tokens not followed" disclosure entirely,
        # because every wallet was already cached. A disclosure that disappears
        # depending on whether something was fetched before is worse than none,
        # so the tally is remembered per wallet and replayed on every hit.
        self._skipped_by_wallet: dict[tuple[int, str], dict[str, int]] = {}
        # Wallets already counted into this trace, so revisiting one cannot
        # double its contribution.
        self._tallied: set[tuple[int, str]] = set()
        # (chain_id, address) -> how far back each fetch actually reached:
        # {"native": {"rows": n, "truncated": bool, "oldest": ts}, "token": {...}}.
        #
        # WHY. Each fetch returns only the most recent MAX_TXNS_PER_ADDRESS rows.
        # For a busy wallet that window can end long AFTER an event we need to
        # look for - a bridge credit months old, say - and "we found nothing" over
        # a window that never covered the event is a false negative. Recording
        # the reach lets a caller say "we could not look that far back" instead.
        self.history_reach: dict[tuple[int, str], dict[str, dict]] = {}
        # (chain_id, address, start_block, end_block) -> (transfers, reach), for
        # the windowed lookups used to match bridge credits.
        self._window_cache: dict[tuple, tuple[list, dict]] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    def reset_stats(self) -> None:
        """Zero the per-trace counters. The cache itself deliberately survives."""
        self.api_calls = 0
        self.cache_hits = 0
        self.skipped_tokens = {}
        self._tallied = set()

    def clear_cache(self) -> None:
        self._cache.clear()
        self._window_cache.clear()
        self._skipped_by_wallet.clear()
        self._tallied.clear()

    async def _request(self, params: dict, chain_id: int | None = None) -> object:
        """
        One throttled explorer call.

        Etherscan signals failure with HTTP 200 and status="0", so the response
        body has to be inspected rather than trusting the status code. The one
        benign "failure" is "No transactions found" — a wallet with no outgoing
        history is a normal dead end in a trace, not an error.

        WHICH API answers is decided by config.chain_api: Etherscan V2 for every
        chain the plan covers, and a chain's own explorer for one it does not
        (BNB Chain, via BscScan). The caller names a chain and never learns which
        door the request went through, so a chain-specific endpoint is not
        something every call site has to know about.
        """
        if not config.has_etherscan_key():
            raise EtherscanError(
                "ETHERSCAN_API_KEY is not set in backend/.env - cannot run a live trace."
            )

        resolved_chain_id = config.chain(chain_id)["chain_id"]
        base_url, api_key, send_chainid = config.chain_api(resolved_chain_id)
        if not api_key:
            raise EtherscanError(
                f"No explorer API key is configured for {config.chain(chain_id)['name']}."
            )

        query = {**params, "apikey": api_key}
        if send_chainid:
            query["chainid"] = resolved_chain_id

        async with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < config.ETHERSCAN_REQUEST_DELAY_SEC:
                await asyncio.sleep(config.ETHERSCAN_REQUEST_DELAY_SEC - elapsed)

            client = await self._get_client()
            try:
                response = await client.get(base_url, params=query)
            except httpx.HTTPError as exc:
                raise EtherscanError(f"Network error talking to the explorer API: {exc}") from exc
            finally:
                self._last_request_at = time.monotonic()
            self.api_calls += 1

        if response.status_code != 200:
            raise EtherscanError(f"Etherscan returned HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise EtherscanError("Etherscan returned a non-JSON response") from exc

        status = str(payload.get("status", ""))
        result = payload.get("result")

        if status == "1":
            return result

        message = str(payload.get("message", ""))
        if "no transactions found" in message.lower():
            return []

        # Rate-limit trips and dead/deprecated endpoints both land here. The
        # result field usually carries the human-readable reason.
        raise EtherscanError(f"Etherscan error: {message or 'unknown'} / {result}")

    async def get_wallet_transfers(
        self, address: str, chain_id: int | None = None
    ) -> list[Transfer]:
        """
        Every ETH transfer SENT BY `address`, most recent first.

        BOTH DIRECTIONS, and this is deliberate. The trace itself only ever
        follows outgoing edges - see the direction argument in tracer.py, which
        has not changed. But FIFO taint accounting cannot work from outgoing
        transfers alone: to know which funds a wallet passed on, you have to know
        the order in which funds arrived, including arrivals from wallets the
        trace never visited. Those clean inflows are exactly what dilutes taint.

        THIS COSTS NOTHING EXTRA. Etherscan's `txlist` returns every transaction
        where the address is sender OR recipient, in the same single call we were
        already making - on one real demo wallet, 1000 rows of which 647 were
        incoming and were being thrown away. Same for `tokentx`. Callers wanting
        the old behaviour use `get_outgoing_transfers`, which filters this list.

        Covers BOTH native transfers (`txlist`) and ERC-20 transfers (`tokentx`),
        merged into one stream. They have to be merged rather than chosen between:
        a wallet that receives ETH and forwards USDT is a single step in the
        trail, and a native-only view shows it as a dead end.

        SCOPE: internal transactions (value moved by contract execution) are still
        not covered. Token transfers outside the allowlist are counted and
        reported, not followed - see `skipped_tokens`.
        """
        chain = config.chain(chain_id)
        resolved = chain["chain_id"]
        native_symbol = chain["native"]
        key = (resolved, normalize_address(address))
        if key in self._cache:
            self.cache_hits += 1
            self._count_skipped(key)
            return self._cache[key]

        raw = await self._request(
            {
                "module": "account",
                "action": "txlist",
                "address": key[1],
                "startblock": 0,
                "endblock": 99999999,
                "page": 1,
                "offset": config.MAX_TXNS_PER_ADDRESS,
                "sort": "desc",
            },
            chain_id=resolved,
        )

        transfers: list[Transfer] = []
        if isinstance(raw, list):
            for tx in raw:
                transfer = _parse_native_transfer(tx, wallet=key[1], asset=native_symbol)
                if transfer is not None:
                    transfers.append(transfer)

        # Second call: ERC-20 movements out of the same wallet. This doubles the
        # calls per wallet, which the throttle already covers - it serialises on
        # elapsed time, not on call count, so the 5/sec ceiling still holds.
        token_raw = await self._request(
            {
                "module": "account",
                "action": "tokentx",
                "address": key[1],
                "startblock": 0,
                "endblock": 99999999,
                "page": 1,
                "offset": config.MAX_TXNS_PER_ADDRESS,
                "sort": "desc",
            },
            chain_id=resolved,
        )

        if isinstance(token_raw, list):
            for tx in token_raw:
                transfer, skipped_symbol = _parse_token_transfer(
                    tx, wallet=key[1], chain_id=resolved
                )
                if transfer is not None:
                    transfers.append(transfer)
                elif skipped_symbol and (tx.get("from") or "").strip().lower() == key[1]:
                    # Counted, never followed: the payload reports how much token
                    # movement we chose not to trace and why. Only rows this
                    # wallet SENT count - incoming spam is not a trail we
                    # declined to follow, and counting it would inflate the
                    # figure now that both directions are fetched.
                    wallet_tally = self._skipped_by_wallet.setdefault(key, {})
                    wallet_tally[skipped_symbol] = wallet_tally.get(skipped_symbol, 0) + 1

        def _reach(rows) -> dict:
            rows = rows if isinstance(rows, list) else []
            stamps = [int(r.get("timeStamp", 0) or 0) for r in rows if isinstance(r, dict)]
            return {
                "rows": len(rows),
                "truncated": len(rows) >= config.MAX_TXNS_PER_ADDRESS,
                "oldest": min(stamps) if stamps else None,
            }

        self.history_reach[key] = {"native": _reach(raw), "token": _reach(token_raw)}
        self._cache[key] = transfers
        self._count_skipped(key)
        return transfers

    async def block_at(self, timestamp: int, chain_id: int, closest: str = "before") -> int:
        """The block number at a unix time on one chain (Etherscan getblocknobytime)."""
        result = await self._request(
            {
                "module": "block",
                "action": "getblocknobytime",
                "timestamp": int(max(0, timestamp)),
                "closest": closest,
            },
            chain_id=chain_id,
        )
        return int(result)

    async def get_wallet_transfers_window(
        self, address: str, chain_id: int, start_ts: int, end_ts: int
    ) -> tuple[list[Transfer], dict]:
        """
        One wallet's transfers within a TIME WINDOW, both directions, oldest first.

        WHY THIS EXISTS. get_wallet_transfers returns a wallet's most recent rows,
        which is right for walking forward but wrong for answering "did this
        specific thing happen at that time?". A busy wallet's newest 1,000 rows
        can all post-date a bridge deposit made weeks ago, so its credit is never
        in the data. Here the request is bounded by the block range covering the
        window instead, so the answer is about the window that matters.

        Returns (transfers, reach). `reach` says whether the window itself hit the
        row cap, in which case it is still incomplete and the caller must say so.
        Cached per (chain, address, block range); never mixed into the forward-walk
        cache, which describes a different slice of history.
        """
        chain = config.chain(chain_id)
        resolved = chain["chain_id"]
        wallet = normalize_address(address)
        start_block = await self.block_at(start_ts, resolved, "before")
        end_block = await self.block_at(end_ts, resolved, "after")
        key = (resolved, wallet, start_block, end_block)
        cached = self._window_cache.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached

        common = {
            "module": "account",
            "address": wallet,
            "startblock": start_block,
            "endblock": end_block,
            "page": 1,
            "offset": config.MAX_TXNS_PER_ADDRESS,
            "sort": "asc",
        }
        raw = await self._request({**common, "action": "txlist"}, chain_id=resolved)
        token_raw = await self._request({**common, "action": "tokentx"}, chain_id=resolved)

        transfers: list[Transfer] = []
        for tx in raw if isinstance(raw, list) else []:
            transfer = _parse_native_transfer(tx, wallet=wallet, asset=chain["native"])
            if transfer is not None:
                transfers.append(transfer)
        for tx in token_raw if isinstance(token_raw, list) else []:
            transfer, _ = _parse_token_transfer(tx, wallet=wallet, chain_id=resolved)
            if transfer is not None:
                transfers.append(transfer)

        cap = config.MAX_TXNS_PER_ADDRESS
        reach = {
            "start_block": start_block,
            "end_block": end_block,
            "complete": (len(raw or []) < cap) and (len(token_raw or []) < cap),
        }
        self._window_cache[key] = (transfers, reach)
        return transfers, reach

    def _count_skipped(self, key: tuple[int, str]) -> None:
        """
        Fold one wallet's skipped-token tally into this trace's total.

        Called on both a fresh fetch and a cache hit, so the disclosure describes
        the wallets the TRACE visited rather than the wallets this process
        happened to parse. Guarded against counting a wallet twice.
        """
        if key in self._tallied:
            return
        self._tallied.add(key)
        chain_id = key[0]
        for symbol, count in self._skipped_by_wallet.get(key, {}).items():
            tally_key = (chain_id, symbol)
            self.skipped_tokens[tally_key] = self.skipped_tokens.get(tally_key, 0) + count

    async def get_outgoing_transfers(
        self, address: str, chain_id: int | None = None
    ) -> list[Transfer]:
        """
        Only the transfers this wallet SENT - what the forward walk expands on.

        A filtered view of `get_wallet_transfers`, so it costs no extra API call
        and cannot disagree with the data the taint pass replays.
        """
        transfers = await self.get_wallet_transfers(address, chain_id=chain_id)
        wallet = normalize_address(address)
        return [t for t in transfers if t.from_addr == wallet]


def _common_fields(tx: dict, wallet: str) -> tuple[str, str] | None:
    """
    Shared row checks; returns (from, to) or None when the row is unusable.

    Keeps rows in EITHER direction - the wallet may be sender or recipient - and
    drops rows it is not party to, contract creations with no recipient, and
    self-sends (which move no money between wallets and would add a self-loop to
    the FIFO ledger, spending a wallet's own funds to refill its own queue).
    """
    to_addr = (tx.get("to") or "").strip().lower()
    from_addr = (tx.get("from") or "").strip().lower()
    if not to_addr or not from_addr:
        return None
    if from_addr == to_addr:
        return None
    if wallet not in (from_addr, to_addr):
        return None
    return from_addr, to_addr


def _parse_native_transfer(tx: dict, wallet: str, asset: str = "ETH") -> Transfer | None:
    """
    One `txlist` row as a native-token Transfer, or None if unusable.

    Dropped rows: reverted transactions, contract creations, self-sends, and
    zero-value calls. A zero-value row here is a contract interaction carrying no
    native value - very often an ERC-20 transfer, whose real value lives in the
    token contract. Those are NOT lost any more: the same movement arrives
    through `tokentx` with its true amount.
    """
    try:
        pair = _common_fields(tx, wallet)
        if pair is None:
            return None
        from_addr, to_addr = pair

        # isError is "1" on a reverted transaction; no value actually moved.
        if str(tx.get("isError", "0")) == "1":
            return None

        value = int(tx.get("value", "0")) / 1e18
        if value <= 0:
            return None

        return Transfer(
            hash=tx.get("hash", ""),
            from_addr=from_addr,
            to_addr=to_addr,
            value=value,
            timestamp=int(tx.get("timeStamp", "0")),
            block=int(tx.get("blockNumber", "0")),
            asset=asset,
            contract=None,
            decimals=18,
            tx_index=int(tx.get("transactionIndex") or 0),
        )
    except (TypeError, ValueError):
        # A malformed row should skip, not kill an entire investigation.
        return None


def _parse_token_transfer(
    tx: dict, wallet: str, chain_id: int
) -> tuple[Transfer | None, str | None]:
    """
    One `tokentx` row as an ERC-20 Transfer.

    Returns (transfer, skipped_symbol). A token that is not on this chain's
    allowlist yields (None, CLAIMED_SYMBOL) so the caller can count what was
    deliberately not followed - silence there would recreate the exact blind spot
    this work removes.

    THE ALLOWLIST IS MATCHED ON `contractAddress`, NOT ON `tokenSymbol`. The
    symbol in this row is whatever the token's author wrote: anyone can deploy a
    contract calling itself USDT and send it to the suspect. Matching on it would
    make the tracer follow that token and report its amount as dollars in a police
    report. The contract address is the identity; the symbol we attach afterwards
    is a display label, taken from our own verified table rather than from the row.

    DECIMALS LIKEWISE COME FROM OUR TABLE, not from `tokenDecimal`, for the same
    reason - and they are not uniform: USDT and USDC use 6 decimals on Ethereum
    and 18 on BNB Chain. Dividing a 100 USDT payment by 1e18 would understate it
    by twelve orders of magnitude, and it would then be discarded as dust.
    """
    try:
        pair = _common_fields(tx, wallet)
        if pair is None:
            return None, None
        from_addr, to_addr = pair

        contract = (tx.get("contractAddress") or "").strip().lower()
        allowed = config.token_asset(chain_id, contract)
        if allowed is None:
            # Not followed. Report it under the symbol it CLAIMS, so an
            # investigator sees what was refused; truncated because that string
            # comes from the token's author and ends up in our JSON payload.
            claimed = (tx.get("tokenSymbol") or "").strip()[:20]
            return None, claimed or "(unnamed token)"
        symbol, decimals = allowed

        raw = int(tx.get("value", "0"))
        value = raw / (10 ** decimals)
        if value <= 0:
            return None, None

        return (
            Transfer(
                hash=tx.get("hash", ""),
                from_addr=from_addr,
                to_addr=to_addr,
                value=value,
                timestamp=int(tx.get("timeStamp", "0")),
                block=int(tx.get("blockNumber", "0")),
                asset=symbol,
                contract=contract or None,
                decimals=decimals,
                tx_index=int(tx.get("transactionIndex") or 0),
            ),
            None,
        )
    except (TypeError, ValueError):
        return None, None


# Process-wide singleton so the cache is shared across requests and traces.
_client = EtherscanClient()


def get_client() -> EtherscanClient:
    """The shared client. Always go through this so the cache is actually shared."""
    return _client
