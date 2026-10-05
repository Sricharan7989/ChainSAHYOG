"""
Tron: the TronGrid client, and the whole pipeline walking a Tron trace.

WHY THIS SUITE EXISTS. Tron is the first non-EVM chain. Everything that was
quietly EVM-shaped - lowercased addresses, symbol-matched tokens, 18-decimal
natives, block-numbered rows - can break here without an error. These checks
pin that it does not:

  * TronGrid rows parse: TRX in sun, TRC-20 USDT at 6 decimals, hex -> base58
  * non-transfer contract types and failed transactions are filtered
  * USDT is matched on its CONTRACT, so a fake "USDT" is skipped
  * every history request is capped at the as-of block's timestamp
  * a TRC-20 USDT trace reaches a labelled exchange, with FIFO taint
  * an Ethereum label never matches a Tron address, even one with the same bytes
  * a pinned Tron trace reproduces

Run from backend/:  python -m tests.test_tron
"""
import asyncio
import json
import sys

import app  # noqa: E402,F401
from core import addresses, identify, tracer  # noqa: E402
from services.etherscan import Transfer  # noqa: E402
from services.tron import TRON_CHAIN_ID, TronClient  # noqa: E402

USDT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
BINANCE_TRON = "TV6MuMXfmLbBqPZvBHdwFsDnQeVfnmiuSi"   # Binance's own published Tron wallet
SUSPECT = "TLa2f6VPqDgRE67v1736s7bJ8Ray5wYjU7"
MID = addresses.normalize("41" + "11" * 20, "tron")  # a valid, unlabelled Tron address
FAKE_USDT = "TMhJviFWiaxvqKLdng9dmsi1H5H5yTGEeu"      # any other contract
HEAD = 70_000_000

fail = 0


def check(name, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got!r}" + ("" if ok else f", want {want!r}"))


def client_tests():
    print("--- 1. TronGrid rows parse into transfers ---")
    c = TronClient()
    calls = []
    suspect_hex = addresses.tron_hex(SUSPECT)
    mid_hex = addresses.tron_hex(MID)

    async def fake_call(method, path, **kw):
        calls.append((method, path, kw.get("params") or kw.get("json")))
        if path == "/wallet/getblockbynum":
            return {"block_header": {"raw_data": {"number": kw["json"]["num"], "timestamp": 1_700_000_000_000}}}
        if path.endswith("/transactions"):
            return {"data": [
                {"txID": "t1", "blockNumber": 10, "block_timestamp": 1_699_999_000_000,
                 "ret": [{"contractRet": "SUCCESS"}],
                 "raw_data": {"contract": [{"type": "TransferContract", "parameter": {"value": {
                     "amount": 12_500_000, "owner_address": suspect_hex, "to_address": mid_hex}}}]}},
                {"txID": "t2", "blockNumber": 11, "block_timestamp": 1_699_999_100_000,
                 "ret": [{"contractRet": "SUCCESS"}],
                 "raw_data": {"contract": [{"type": "DelegateResourceContract", "parameter": {"value": {}}}]}},
                {"txID": "t3", "blockNumber": 12, "block_timestamp": 1_699_999_200_000,
                 "ret": [{"contractRet": "REVERT"}],
                 "raw_data": {"contract": [{"type": "TransferContract", "parameter": {"value": {
                     "amount": 1, "owner_address": suspect_hex, "to_address": mid_hex}}}]}},
                {"internal_tx_id": "i1", "data": {}},
            ], "meta": {}}
        if path.endswith("/transactions/trc20"):
            return {"data": [
                {"transaction_id": "u1", "block_timestamp": 1_699_999_300_000, "type": "Transfer",
                 "from": SUSPECT, "to": MID, "value": "1234567",
                 "token_info": {"address": USDT, "symbol": "USDT", "decimals": 6}},
                {"transaction_id": "u2", "block_timestamp": 1_699_999_400_000, "type": "Transfer",
                 "from": SUSPECT, "to": MID, "value": "99000000",
                 "token_info": {"address": FAKE_USDT, "symbol": "USDT", "decimals": 6}},
                {"transaction_id": "u3", "block_timestamp": 1_699_999_500_000, "type": "Approval",
                 "from": SUSPECT, "to": MID, "value": "1",
                 "token_info": {"address": USDT, "symbol": "USDT", "decimals": 6}},
            ], "meta": {}}
        raise AssertionError(path)

    c._call = fake_call
    rows = asyncio.run(c.get_wallet_transfers(SUSPECT, TRON_CHAIN_ID, as_of_block=HEAD))
    trx = [t for t in rows if t.asset == "TRX"]
    usdt = [t for t in rows if t.asset == "USDT"]
    check("one TRX transfer survives (delegation, failed and internal rows filtered)", len(trx), 1)
    check("TRX converts from sun", trx[0].value, 12.5)
    check("native hex addresses come back as base58", (trx[0].from_addr, trx[0].to_addr), (SUSPECT, MID))
    check("filtered types are counted", sorted(c.filtered_contract_types),
          ["DelegateResourceContract", "failed", "internal"])
    check("exactly one USDT transfer: the real contract, a Transfer", [t.hash for t in usdt], ["u1"])
    check("USDT converts at 6 decimals", usdt[0].value, 1.234567)
    check("the fake 'USDT' from another contract is skipped and counted",
          c.skipped_tokens.get((TRON_CHAIN_ID, "USDT")), 1)
    caps = {p.get("max_timestamp") for _, path, p in calls if path.startswith("/v1/") and p}
    check("every history request is capped at the as-of block's timestamp", caps, {1_700_000_000_000})


class FakeTron:
    """A Tron chain with a head and history honouring as_of_block (by timestamp)."""

    def __init__(self, book):
        self.book = book
        self.history_reach = {}
        self.api_calls = self.cache_hits = 0
        self.skipped_tokens = {}

    def reset_stats(self):
        pass

    async def latest_block(self, chain_id):
        return HEAD

    async def block_timestamp(self, block, chain_id):
        return 1_600_000_000 + (block - 60_000_000) * 3

    async def block_at(self, ts, chain_id, closest="before"):
        return 60_000_000 + (ts - 1_600_000_000) // 3

    async def get_wallet_transfers(self, address, chain_id=None, as_of_block=None):
        cap = await self.block_timestamp(as_of_block, chain_id) if as_of_block else None
        return [t for t in self.book.get(address, []) if cap is None or t.timestamp <= cap]

    async def get_inbound_senders(self, address, chain_id, as_of_block=None):
        return {"senders": 1, "value_senders": 1, "out_rows": 1, "complete": True, "calls": 2}


def usdt(frm, to, v, h, ts):
    return Transfer(hash=h, from_addr=frm, to_addr=to, value=v, timestamp=ts, block=0,
                    asset="USDT", contract=USDT, decimals=6)


T0 = 1_600_000_000 + 9_000_000 * 3   # comfortably before HEAD
BOOK = {
    SUSPECT: [usdt(SUSPECT, MID, 5_000.0, "u1", T0)],
    MID: [usdt(SUSPECT, MID, 5_000.0, "u1", T0), usdt(MID, BINANCE_TRON, 4_900.0, "u2", T0 + 60)],
}


def run(book, **kw):
    return tracer.to_json(asyncio.run(tracer.trace(SUSPECT, max_depth=3, client=FakeTron(book),
                                                   chain_id=TRON_CHAIN_ID, **kw)))


def trace_tests():
    print("\n--- 2. a TRC-20 USDT trace reaches a labelled exchange, with taint ---")
    identify.load_labels(force_reload=True)
    p = run(BOOK)
    s = p["summary"]
    check("found the exchange", (s.get("found"), s.get("exchange")), (True, "Binance"))
    check("two hops", s.get("hop_distance"), 2)
    check("FIFO taint in USDT", s.get("tainted_value_received"), {"USDT": 4900.0})
    check("pinned at the Tron head", (p["as_of"]["chain"], p["as_of"]["block"]), ("tron", HEAD))
    check("the deposit names the chain and TRC-20 contract",
          ((s["deposits"] or [{}])[0].get("chain_name"), (s["deposits"] or [{}])[0].get("token_standard"),
           (s["deposits"] or [{}])[0].get("contract")), ("Tron", "TRC-20", USDT))
    check("the coverage note names the OKX gap",
          "OKX" in (p["cross_chain"]["label_coverage"].get("tron", {}).get("note") or ""), True)

    print("\n--- 3. an Ethereum label never matches a Tron address ---")
    binance_eth = "0x28c6c06298d514db089934071355e5743bf21d60"
    same_bytes = addresses.normalize("41" + binance_eth[2:], "tron")   # the identical 20 bytes on Tron
    check("the Ethereum label exists", getattr(identify.known_label_lookup(binance_eth, "ethereum"), "entity", None),
          "Binance")
    check("the same bytes as a Tron address match nothing", identify.known_label_lookup(same_bytes, "tron"), None)
    book = {SUSPECT: [usdt(SUSPECT, same_bytes, 100.0, "x1", T0)]}
    check("so a Tron trace into it finds no exchange", run(book)["summary"].get("found"), False)

    print("\n--- 4. a pinned Tron trace reproduces; an earlier height excludes later transfers ---")
    a = run(BOOK, as_of_block=HEAD)
    b = run(BOOK, as_of_block=HEAD)
    strip = lambda x: {k: v for k, v in json.loads(json.dumps(x, default=str)).items() if k != "stats"}  # noqa: E731
    check("two traces at the same Tron height are identical", strip(a) == strip(b), True)
    early = 60_000_000 + (T0 + 30 - 1_600_000_000) // 3   # after u1, before u2
    e = run(BOOK, as_of_block=early)
    check("before the exchange deposit, no exchange is reached", e["summary"].get("found"), False)

    print("\n--- 4b. a hop cites the transfer that carried the suspect's money ---")
    # Found verifying a real trace on Tronscan: the edge's LARGEST transfer was
    # dated before the suspect's funds arrived, so it cannot have carried them.
    book = dict(BOOK)
    book[MID] = [usdt(MID, BINANCE_TRON, 10_000.0, "u0-early", T0 - 100)] + BOOK[MID]
    edge = next(e for e in run(book)["edges"] if e["target"] == BINANCE_TRON)
    check("the edge's largest transfer is the early one", edge["tx_hash"], "u0-early")
    check("but the transfer cited as carrying the suspect's value is the later one",
          edge["tainted_tx_hash"], "u2")

    print("\n--- 5. a sanctioned Tron address raises a risk flag ---")
    sdn = next(addr for (chain, addr), m in identify.load_labels().items()
               if chain == "tron" and m.get("type") == "sanctioned")
    book = {SUSPECT: [usdt(SUSPECT, sdn, 50.0, "s1", T0)]}
    flags = run(book)["risk_flags"]
    check("the SDN-listed Tron wallet is flagged", [f["address"] for f in flags], [sdn])
    check("with its sanctions status", (flags[0].get("sanctions_status") or "").endswith("A current sanction."), True)


def run_all():
    client_tests()
    trace_tests()
    print("\n" + ("ALL CHECKS PASSED" if fail == 0 else f"{fail} CHECK(S) FAILED"))
    return fail


def test_suite():
    """pytest entry point; run directly for the per-check listing."""
    assert run_all() == 0


if __name__ == "__main__":
    sys.exit(run_all())
