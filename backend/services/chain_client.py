"""
One client for every chain: routes each call to the client for that chain.

The tracer holds a single client and names a chain on every call. This keeps
that true now that Tron is read through TronGrid rather than Etherscan: calls
for an EVM chain go to EtherscanClient, calls for Tron to TronClient, and the
per-trace counters the payload reports (API calls, cache hits, skipped tokens,
how far back each history reached) are the sum of both.
"""

from __future__ import annotations

from app import config
from services import etherscan, tron


class MultiChainClient:
    def __init__(self) -> None:
        self.evm = etherscan.get_client()
        self.tron = tron.get_client()

    def _for(self, chain_id):
        meta = config.CHAINS.get(int(chain_id or config.DEFAULT_CHAIN_ID)) or {}
        return self.tron if meta.get("family") == "tron" else self.evm

    # --- the interface the tracer uses ------------------------------------------

    async def get_wallet_transfers(self, address, chain_id=None, as_of_block=None):
        return await self._for(chain_id).get_wallet_transfers(address, chain_id=chain_id, as_of_block=as_of_block)

    async def get_wallet_transfers_window(self, address, chain_id, start_ts, end_ts, as_of_block=None):
        client = self._for(chain_id)
        if client is self.tron:
            raise NotImplementedError("no bridge route lands on Tron, so no window lookup exists")
        return await client.get_wallet_transfers_window(address, chain_id, start_ts, end_ts, as_of_block=as_of_block)

    async def latest_block(self, chain_id):
        return await self._for(chain_id).latest_block(chain_id)

    async def block_timestamp(self, block, chain_id):
        return await self._for(chain_id).block_timestamp(block, chain_id)

    async def block_at(self, timestamp, chain_id, closest="before"):
        return await self._for(chain_id).block_at(timestamp, chain_id, closest)

    async def get_inbound_senders(self, address, chain_id, as_of_block=None):
        return await self._for(chain_id).get_inbound_senders(address, chain_id, as_of_block=as_of_block)

    # --- aggregated per-trace state ------------------------------------------------

    @property
    def api_calls(self) -> int:
        return self.evm.api_calls + self.tron.api_calls

    @property
    def cache_hits(self) -> int:
        return self.evm.cache_hits + self.tron.cache_hits

    @property
    def skipped_tokens(self) -> dict:
        return {**self.evm.skipped_tokens, **self.tron.skipped_tokens}

    @property
    def history_reach(self) -> dict:
        return {**self.evm.history_reach, **self.tron.history_reach}

    def reset_stats(self) -> None:
        self.evm.reset_stats()
        self.tron.reset_stats()

    def clear_cache(self) -> None:
        self.evm.clear_cache()
        self.tron.clear_cache()

    async def aclose(self) -> None:
        await self.evm.aclose()
        await self.tron.aclose()


_client: MultiChainClient | None = None


def get_client() -> MultiChainClient:
    global _client
    if _client is None:
        _client = MultiChainClient()
    return _client
