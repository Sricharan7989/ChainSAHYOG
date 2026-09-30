"""
ERC-20 support tests.

Covers the three things the token work must get right:
  1. a 6-decimal token converts correctly (USDT/USDC are 6, not 18);
  2. mixed-asset aggregation keeps assets apart and never sums across them;
  3. a token-only trail is followed end to end - the case that used to vanish,
     because a transaction carrying a token transfer has native value 0 and was
     dropped as worthless;
  4. the allowlist is pinned to CONTRACT ADDRESSES, per chain - a token that
     merely calls itself USDT is refused, and the same asset's contract differs
     (and has different decimals) on each chain.
"""
import asyncio
import sys

# Run from backend/:  python -m tests.test_tokens
import app  # noqa: E402,F401
from app import config  # noqa: E402
from core import tracer  # noqa: E402
from services import graph_store  # noqa: E402
from services.etherscan import (  # noqa: E402
    Transfer,
    _parse_native_transfer,
    _parse_token_transfer,
)

BINANCE = "0x28c6c06298d514db089934071355e5743bf21d60"
USDT_CONTRACT = "0xdac17f958d2ee523a2206206994597c13d831ec7"
USDC_CONTRACT = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
DAI_CONTRACT = "0x6b175474e89094c44da98b954eedeac495271d0f"
POLYGON_USDT = "0xc2132d05d31c914a87c6611c10748aeb04b58e8f"
BNB_USDT = "0x55d398326f99059ff775485246999027b3197955"
# A contract that calls itself USDT and is not. This is the attack: send the
# suspect a worthless token named USDT so the trace follows it and a police
# report cites its amount as dollars.
FAKE_USDT = "0x1234567890abcdef1234567890abcdef12345678"

fail = 0


def check(name, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got!r}" + ("" if ok else f", want {want!r}"))


def A(n):
    return "0x" + f"{n:040x}"


def native(frm, to, val, h="0xeth"):
    return Transfer(hash=h, from_addr=frm, to_addr=to, value=val,
                    timestamp=1700000000, block=1, asset="ETH", contract=None, decimals=18)


def token(frm, to, val, symbol="USDT", h="0xusdt", decimals=6, contract=USDT_CONTRACT):
    return Transfer(hash=h, from_addr=frm, to_addr=to, value=val,
                    timestamp=1700000000, block=1, asset=symbol,
                    contract=contract, decimals=decimals)


class FakeClient:
    def __init__(self, book):
        self.book = book
        self.api_calls = 0
        self.cache_hits = 0
        self.skipped_tokens = {}

    def reset_stats(self):
        self.api_calls = 0
        self.skipped_tokens = {}

    async def get_wallet_transfers(self, address, chain_id=None):
        """Both directions, as Etherscan returns them: the book is the world."""
        self.api_calls += 1
        outgoing = self.book.get(address, [])
        incoming = [
            t
            for transfers in self.book.values()
            for t in transfers
            if t.to_addr == address
        ]
        return outgoing + incoming

    async def get_outgoing_transfers(self, address, chain_id=None):
        self.api_calls += 1
        return self.book.get(address, [])


async def run(book, start, depth=4):
    original = graph_store.get_store
    graph_store.get_store = lambda trace_id=None, prefer=None: original(trace_id, prefer="memory")
    try:
        return await tracer.trace(start, max_depth=depth, dust_threshold=0.001,
                                  client=FakeClient(book))
    finally:
        graph_store.get_store = original


async def main():
    # ------------------------------------------------------------- case 1
    print("--- 1. a 6-decimal token converts correctly ---")
    row = {
        "from": "0xaaa", "to": "0xbbb", "hash": "0x1", "timeStamp": "1700000000",
        "blockNumber": "1", "tokenSymbol": "USDT", "tokenDecimal": "6",
        "contractAddress": USDT_CONTRACT,
        "value": "100000000",  # 100.000000 USDT at 6 decimals
    }
    transfer, skipped = _parse_token_transfer(row, wallet="0xaaa", chain_id=1)
    check("100 USDT parsed as 100.0, not 1e-10", transfer.value, 100.0)
    check("symbol", transfer.asset, "USDT")
    check("decimals from the verified table, not assumed", transfer.decimals, 6)
    check("contract recorded", transfer.contract, USDT_CONTRACT)
    check("not native", transfer.is_native, False)
    check("nothing skipped", skipped, None)

    # the same raw amount under an 18-decimal assumption would be dust
    naive = int(row["value"]) / 1e18
    check("an 18-decimal assumption would fall under the dust floor",
          naive < config.dust_threshold_for("USDT"), True)

    # 18-decimal token still works
    dai_row = dict(row, tokenSymbol="DAI", tokenDecimal="18",
                   value="5000000000000000000", contractAddress=DAI_CONTRACT)
    dai, _ = _parse_token_transfer(dai_row, wallet="0xaaa", chain_id=1)
    check("18-decimal token converts too", dai.value, 5.0)

    # allowlist
    spam_row = dict(row, tokenSymbol="FREEAIRDROP", tokenDecimal="18",
                    contractAddress="0xfeed000000000000000000000000000000000001")
    spam, spam_symbol = _parse_token_transfer(spam_row, wallet="0xaaa", chain_id=1)
    check("non-allowlisted token not followed", spam, None)
    check("but it is counted, with its symbol", spam_symbol, "FREEAIRDROP")

    # native rows are unaffected
    nat = _parse_native_transfer(
        {"from": "0xaaa", "to": "0xbbb", "hash": "0x2", "timeStamp": "1",
         "blockNumber": "1", "value": "1000000000000000000", "isError": "0"},
        wallet="0xaaa", asset="ETH")
    check("native 1 ETH still parses", nat.value, 1.0)
    check("native has no contract", nat.contract, None)

    # ------------------------------------------------------------- case 2
    print("\n--- 2. mixed-asset aggregation does not sum across assets ---")
    transfers = [
        native(A(0), A(1), 5.0),
        native(A(0), A(1), 3.0),
        token(A(0), A(1), 4000.0),
        token(A(0), A(1), 1000.0),
        token(A(0), A(1), 250.0, symbol="USDC", contract=USDC_CONTRACT, h="0xusdc"),
    ]
    flows = tracer._aggregate_by_recipient(transfers, 0.001)
    assets = flows[A(1)]["assets"]
    check("three assets kept apart", sorted(assets), ["ETH", "USDC", "USDT"])
    check("ETH summed within its own asset", assets["ETH"]["value"], 8.0)
    check("USDT summed within its own asset", assets["USDT"]["value"], 5000.0)
    check("USDC kept separate", assets["USDC"]["value"], 250.0)
    check("no cross-asset total exists on the flow", "value_eth" in flows[A(1)], False)
    check("per-asset tx counts", assets["ETH"]["tx_count"], 2)
    check("total tx count across assets", flows[A(1)]["tx_count"], 5)
    check("largest USDT tx is the citable one", assets["USDT"]["tx_hash"], "0xusdt")
    # 8 ETH + 5000 USDT must never appear as 5008 of anything
    check("assets are not summed into one number",
          any(abs(a["value"] - 5008.0) < 0.001 for a in assets.values()), False)

    # per-asset dust: 0.5 USDT is dust, 0.5 ETH is not
    dusty = tracer._aggregate_by_recipient(
        [token(A(0), A(2), 0.5), native(A(0), A(2), 0.5)], 0.001)
    check("0.5 USDT dropped as dust (threshold 1.0)",
          "USDT" in dusty.get(A(2), {}).get("assets", {}), False)
    check("0.5 ETH kept (threshold 0.001)",
          dusty[A(2)]["assets"]["ETH"]["value"], 0.5)

    # ------------------------------------------------------------- case 3
    print("\n--- 3. a token-only trail is followed end to end ---")
    # Suspect sends USDT only; no native value anywhere on the path. Before this
    # work the whole trail was invisible.
    book = {
        A(0): [token(A(0), A(1), 50_000.0)],
        A(1): [token(A(1), A(2), 49_000.0)],
        A(2): [token(A(2), BINANCE, 48_000.0)],
    }
    result = await run(book, A(0))
    summary = tracer.summarize(result)

    check("the exchange is reached", summary["found"], True)
    check("named correctly", summary["exchange"], "Binance")
    check("hop distance", summary["hop_distance"], 3)
    check("USDT total reported", summary["value_received"], {"USDT": 48000.0})
    check("display names the asset", "48,000 USDT" in summary["value_received_display"], True)
    check("native total is 0 and says so", summary["value_received_eth"], 0.0)
    check("termination", summary["termination"]["reason"], "exchange_reached")

    payload = tracer.to_json(result)
    edge = payload["edges"][0]
    check("edge carries the asset breakdown", edge["assets"][0]["asset"], "USDT")
    check("edge decimals preserved", edge["assets"][0]["decimals"], 6)
    check("hops carry their asset", payload["hops"][0]["asset"], "USDT")

    # ------------------------------------------------------------- case 4
    print("\n--- 4. the allowlist is pinned to contract addresses, per chain ---")

    # THE ATTACK. Identical row to a real USDT transfer in every respect an
    # earlier version looked at - symbol USDT, 6 decimals, a large round amount -
    # except that the contract is not Tether's. It must not be followed, and it
    # must not be labelled USDT.
    fake_row = {
        "from": "0xaaa", "to": "0xbbb", "hash": "0x9", "timeStamp": "1700000000",
        "blockNumber": "1", "tokenSymbol": "USDT", "tokenDecimal": "6",
        "contractAddress": FAKE_USDT,
        "value": "40000000000",  # would read as 40,000 USDT
    }
    fake, fake_symbol = _parse_token_transfer(fake_row, wallet="0xaaa", chain_id=1)
    check("a token calling itself USDT from another contract is REJECTED", fake, None)
    check("it is counted under the symbol it claimed", fake_symbol, "USDT")
    check("and the real USDT contract is still accepted",
          _parse_token_transfer(
              dict(fake_row, contractAddress=USDT_CONTRACT), wallet="0xaaa", chain_id=1
          )[0].value,
          40000.0)

    # A lowercase/uppercase difference in the address must not matter; a one
    # character difference must.
    check("address matching is case-insensitive",
          config.token_asset(1, USDT_CONTRACT.upper()), ("USDT", 6))
    check("a near-miss address is not the asset",
          config.token_asset(1, USDT_CONTRACT[:-1] + "8"), None)

    # The row cannot dictate decimals either: a spoofed tokenDecimal on a real
    # contract would otherwise scale the amount by orders of magnitude.
    lying = dict(fake_row, contractAddress=USDT_CONTRACT, tokenDecimal="18")
    check("decimals come from our table, not the row",
          _parse_token_transfer(lying, wallet="0xaaa", chain_id=1)[0].value, 40000.0)

    # PER CHAIN. The same address is not the same asset everywhere.
    check("Ethereum's USDT address is not USDT on Polygon",
          config.token_asset(137, USDT_CONTRACT), None)
    check("Polygon has its own USDT contract",
          config.token_asset(137, POLYGON_USDT), ("USDT", 6))
    check("a Polygon-USDT row is refused on an Ethereum trace",
          _parse_token_transfer(
              dict(fake_row, contractAddress=POLYGON_USDT), wallet="0xaaa", chain_id=1
          )[0],
          None)
    check("BNB Chain USDT carries 18 decimals, not 6",
          config.token_asset(56, BNB_USDT), ("USDT", 18))
    bnb = _parse_token_transfer(
        dict(fake_row, contractAddress=BNB_USDT, value="40000" + "0" * 18),
        wallet="0xaaa", chain_id=56,
    )[0]
    check("so 40,000 BNB-Chain USDT parses at 18 decimals", bnb.value, 40000.0)
    check("an unsupported chain follows no tokens at all",
          config.token_asset(999, USDT_CONTRACT), None)

    # The display label is ours. Polygon's contract self-reports "USDT0" and
    # Arbitrum's reports a Tether glyph; neither should leak into a report.
    check("display symbol is our own label, not the contract's string",
          {config.token_asset(c, a)[0]
           for c, a in ((137, POLYGON_USDT),
                        (42161, "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9"))},
          {"USDT"})

    # And the skipped count must say WHY, or a refused fake reads as a miss.
    class Skipper:
        skipped_tokens = {(1, "USDT"): 3, (1, "FREEAIRDROP"): 12, (137, "USDC"): 9}

    note = tracer._unfollowed_token_note(Skipper(), chain_id=1)
    check("only this chain's skips are reported", note["skipped_transfers"], 15)
    check("the fake USDT is flagged as an impostor",
          note["impersonated_symbols"], ["USDT"])
    check("spam is not flagged as an impostor",
          [e["impersonating"] for e in note["top_skipped"] if e["asset"] == "FREEAIRDROP"],
          [False])
    check("the note explains the refusal",
          "not the real contract" in note["impersonation_note"], True)

    # ------------------------------------------------------------- case 5
    print("\n--- 5. the skipped-token disclosure survives the wallet cache ---")
    # REGRESSION. The tally was built while parsing rows, so a cache hit added
    # nothing to it: the second trace of a session reported no skipped tokens at
    # all, because every wallet was already cached. Both re-recorded demo traces
    # lost their "Tokens not followed" section this way. A disclosure that
    # disappears depending on what was fetched earlier is worse than none.
    import json as _json  # noqa: PLC0415
    from unittest.mock import patch as _patch  # noqa: PLC0415

    from services.etherscan import EtherscanClient  # noqa: PLC0415

    WALLET = "0x" + "7" * 40
    spam_rows = [
        {
            "from": WALLET, "to": "0x" + "8" * 40, "hash": f"0x{i:064x}",
            "timeStamp": "1700000000", "blockNumber": "1", "transactionIndex": "0",
            "tokenSymbol": "SPAM", "tokenDecimal": "18",
            "contractAddress": "0xfeed000000000000000000000000000000000009",
            "value": "5000000000000000000",
        }
        for i in range(3)
    ]

    client = EtherscanClient()

    async def fake_request(params, chain_id=None):
        return spam_rows if params.get("action") == "tokentx" else []

    with _patch.object(client, "_request", side_effect=fake_request):
        await client.get_wallet_transfers(WALLET, chain_id=1)
        first = dict(client.skipped_tokens)
        # A second trace: stats reset, wallet still cached, no parsing happens.
        client.reset_stats()
        await client.get_wallet_transfers(WALLET, chain_id=1)
        second = dict(client.skipped_tokens)
        # Visiting the same wallet twice within one trace must not double it.
        await client.get_wallet_transfers(WALLET, chain_id=1)
        third = dict(client.skipped_tokens)

    check("a fresh fetch counts the skipped tokens", first, {(1, "SPAM"): 3})
    check("a CACHED fetch reports the same tally, not nothing", second, {(1, "SPAM"): 3})
    check("and the cache was actually used", client.cache_hits > 0, True)
    check("revisiting a wallet in one trace does not double count", third, second)
    check("the note is therefore produced on a cached trace too",
          tracer._unfollowed_token_note(client, 1).get("skipped_transfers"), 3)
    _json  # referenced so the import reads as deliberate

    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail


sys.exit(asyncio.run(main()))
