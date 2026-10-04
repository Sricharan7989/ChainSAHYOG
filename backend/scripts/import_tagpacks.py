"""
Import address labels from the GraphSense TagPacks into data/labels.json.

    python -m scripts.import_tagpacks            # fetch, filter, verify on-chain, merge
    python -m scripts.import_tagpacks --dry-run  # show what would change, write nothing
    python -m scripts.import_tagpacks --no-verify  # skip the on-chain check (faster, riskier)

WHY THIS IS NOT A STRAIGHT COPY
-------------------------------
A label file is the ground truth for method (a), so a wrong entry here does
not produce a small error - it produces a CONFIDENT, FALSE attribution at 88%
confidence, with a recommendation to serve a legal request on whoever it names.
That is the worst thing this tool can do. Bulk-importing a third-party list
without inspecting it would trade a small, trustworthy label set for a large,
untrustworthy one.

And the TagPacks genuinely need inspecting. `etherscan-wordcloud-exchange.yaml`
carries 646 addresses tagged "exchange", but they are scraped from Etherscan's
label cloud, where the tag is applied loosely: 267 of them (41%) are ERC-20
TOKEN CONTRACTS of exchange-affiliated tokens - "AAX Token (AAB)",
"2GT_token (2GT)" - not exchange wallets at all. A token contract holds no
customer deposits, has no KYC records, and cannot answer a SAHYOG request.

So every candidate passes two filters:

  1. LABEL SHAPE - reject anything that reads like a token: a trailing ticker
     in parentheses, or the word "token". Cheap, and catches the bulk of it.

  2. ON-CHAIN REALITY - for exchange entries, reject addresses that are
     contracts with no outgoing transaction history. An exchange hot wallet is
     a live spending wallet with a large nonce; a token contract sends nothing
     itself. This catches the token contracts whose labels look innocent.

Mixers are deliberately NOT held to filter 2: a mixer pool is SUPPOSED to be a
contract, so requiring an EOA there would reject every genuine entry.

MULTI-CHAIN
-----------
The exchange packs are NOT Ethereum-only: `exchange-wallets-binance.yaml`
also lists the same reserve wallets as BEP20 (BNB Chain) addresses, and
`exchange-wallets-bitfinexcom.yaml` lists Polygon (MATIC) ones. The TagPack
`currency` field says which chain each address lives on, and the same 0x
address can be a Binance wallet on BOTH Ethereum and BNB Chain - so labels
are imported per (chain, address), never per address alone. Only currencies
that map to a chain this tool can actually trace are kept; BTC, TRX and the
rest are counted and refused, because a label for a chain we cannot walk
would let the report claim a finding it can never corroborate.

Every imported row is verified on ITS OWN chain (eth_getCode and
eth_getTransactionCount with that chain's chainid), so a wallet that is live
on Ethereum but idle on Polygon cannot slide through as a Polygon label.

Existing entries in labels.json always win. They were verified by hand, and an
import must never silently overwrite a checked fact with a scraped one.
"""

import argparse
import asyncio
import base64
import json
import re
import sys
import urllib.request

import httpx
import yaml

from app import config
from core import addresses, label_names
from scripts import apply_provenance

GITHUB_API = (
    "https://api.github.com/repos/graphsense/graphsense-tagpacks/contents/packs/"
)

# Packs to import, and the type each contributes. Chosen deliberately, not
# wholesale - see the notes beside each exclusion at the bottom of this file.
PACKS = {
    "etherscan-wordcloud-exchange.yaml": "exchange",
    "etherscan-wordcloud-mixing_service.yaml": "mixer",
    "tornado_cash.yaml": "mixer",
    "exchange-wallets-binance.yaml": "exchange",
    "exchange-wallets-bitfinexcom.yaml": "exchange",
    "exchange-wallets-bybit.yaml": "exchange",
    "exchange-wallets-cryptocom.yaml": "exchange",
    "exchange-wallets-deribit.yaml": "exchange",
    "exchange-wallets-huobi.yaml": "exchange",
    "exchange-wallets-kucoin.yaml": "exchange",
    "exchange-wallets-okx.yaml": "exchange",
    "exchange-wallets-swissborg.yaml": "exchange",
}

# GraphSense category -> our label type.
CATEGORY_MAP = {
    "exchange": "exchange",
    "mixing_service": "mixer",
    "bridge": "bridge",
}

# TagPack currency -> the chain slug this tool traces. A TagPack address
# is only importable when we can actually WALK the chain it lives on:
# a label for a chain we cannot read would let the report name an
# exchange on a trail it never verified. BTC, TRX, BEP2 (Binance Chain
# native) and every other currency here are deliberately refused and
# counted, so the refusal is visible rather than silent.
#
# Every value must be a key of config.CHAIN_BY_SLUG, or the import
# refuses it - the mapping is checked at startup, not trusted by luck.
CURRENCY_MAP = {
    "ETH": "ethereum",
    "BEP20": "bnb",
    "MATIC": "polygon",
    "POLYGON": "polygon",
    "ARB": "arbitrum",
    "ARBITRUM": "arbitrum",
}

# The TagPack `actor` field names the entity the pack is about
# ("binance", "bitfinex"), which is a cleaner entity name than the
# per-tag label ("binance reserve wallets BNB"). An investigator serves
# a request on the COMPANY, not on "reserve wallet #3".
ACTOR_NAMES = {
    "binance": "Binance",
    "bitfinex": "Bitfinex",
    "bybit": "Bybit",
    "cryptocom": "Crypto.com",
    "deribit": "Deribit",
    "huobi": "Huobi",
    "kucoin": "KuCoin",
    "okx": "OKX",
    "swissborg": "SwissBorg",
}

ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

# A trailing "(TICKER)", or the word "token" anywhere: both say ERC-20 contract.
TOKEN_RE = re.compile(r"\(\s*\w{2,10}\s*\)\s*$")

# Trailing wallet index, e.g. "Binance 14" -> "Binance". The company is what an
# investigator serves a request on; which of its hot wallets it was is already
# recorded separately as the address.
INDEX_RE = re.compile(r"[\s_-]+\d+$")

# An exchange hot wallet sends constantly. Below this many outgoing
# transactions an address is not carrying exchange flow, whatever it is called.
MIN_NONCE_FOR_EXCHANGE = 25


def looks_like_token(label: str) -> bool:
    low = label.lower()
    return bool(TOKEN_RE.search(label)) or "token" in low or "voucher" in low


def clean_entity(label: str, actor: str = "") -> str:
    """Tidy a TagPack label into an entity name fit for an investigator's report."""
    # The pack's actor is the entity itself: "binance reserve wallets BNB"
    # and "bitfinex Polygon hot wallet" both name Binance and Bitfinex.
    name = ACTOR_NAMES.get(actor.strip().lower())
    if name:
        return name
    name = label.strip().strip("'\"")
    name = re.sub(r"\s*:\s*", ": ", name)
    name = INDEX_RE.sub("", name)
    return name.strip() or label.strip()


def fetch_pack(filename: str) -> str:
    """
    Download one pack, through the GitHub contents API with a
    raw.githubusercontent fallback.

    The contents API rather than the raw host on purpose: the raw host
    returns empty bodies from some networks (including the one this was
    first written on), which would look like an empty pack rather than a
    failed download. But the contents API allows only 60 unauthenticated
    calls an hour, and a pack set is a dozen of them - so a 403 rate
    limit falls back to the raw host, which has none. Either way the
    bytes come from the same repository, so the source is identical.
    """
    headers = {"User-Agent": "vasp-attribution-engine", "Accept": "application/vnd.github+json"}
    try:
        request = urllib.request.Request(
            GITHUB_API + filename, headers=headers
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            body = json.load(response)
        if body.get("encoding") == "base64" and body.get("content"):
            return base64.b64decode(body["content"]).decode("utf-8", "replace")
        raise RuntimeError(f"{filename}: no inline content (file may exceed the API's 1 MB limit)")
    except urllib.error.HTTPError as exc:
        if exc.code != 403:
            raise
    # Rate-limited (or otherwise refused) by the contents API: the raw
    # host serves the identical file without a call budget.
    raw_url = (
        "https://raw.githubusercontent.com/graphsense/graphsense-tagpacks/"
        "master/packs/" + filename
    )
    request = urllib.request.Request(raw_url, headers={"User-Agent": "vasp-attribution-engine"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read().decode("utf-8", "replace")


def parse_pack(text: str, filename: str, default_type: str) -> tuple[list[dict], dict]:
    """
    Turn one pack's YAML into candidate label rows, with a rejection tally.

    TagPack fields cascade: a tag inherits `currency`, `label` and `category`
    from the pack header unless it overrides them.

    The `currency` field decides which chain the address belongs to. Only
    currencies in CURRENCY_MAP survive - everything else is counted under
    `unsupported_chain` so the refusal is visible. An Ethereum pack and a
    BNB Chain pack can list the SAME 0x address; both rows are kept, because
    they are two different wallets on two different ledgers and the label
    store is keyed by (chain, address).
    """
    document = yaml.safe_load(text) or {}
    header_currency = str(document.get("currency", "") or "").upper()
    header_label = str(document.get("label") or document.get("title") or "").strip()
    header_category = str(document.get("category", "") or "")
    actor = str(document.get("actor") or "").strip()

    rejected = {"not_supported_chain": 0, "bad_address": 0, "token_like": 0, "no_label": 0}
    rows: list[dict] = []

    for tag in document.get("tags") or []:
        if not isinstance(tag, dict):
            continue

        address = str(tag.get("address", "")).strip().strip("'\"")
        currency = str(tag.get("currency", header_currency) or "").upper()

        # Only chains this tool can trace. Anything else (BTC, TRX, BEP2,
        # SOL, ...) is a dataset we knowingly do not use yet.
        chain_slug = CURRENCY_MAP.get(currency)
        if chain_slug is None or chain_slug not in config.CHAIN_BY_SLUG:
            rejected["not_supported_chain"] += 1
            continue
        canonical = addresses.try_normalize(address, chain_slug)
        if canonical is None:
            # Not a valid address for the chain the pack files it under - an
            # Ethereum-shaped string on a Tron row, a bad checksum, and so on.
            rejected["bad_address"] += 1
            continue

        label = str(tag.get("label") or header_label or "").strip()
        if not label:
            rejected["no_label"] += 1
            continue
        if looks_like_token(label):
            rejected["token_like"] += 1
            continue

        category = str(tag.get("category", header_category) or "")
        entity_type = CATEGORY_MAP.get(category, default_type)

        row = {
            # The chain's own canonical form - never lowercased where case matters.
            "address": canonical,
            "entity": clean_entity(label, actor),
            "type": entity_type,
            "chain": chain_slug,
            "source": filename,
            # The tag's own upstream link, for the provenance chain.
            "source_url": str(tag.get("source") or document.get("source") or ""),
        }
        # Same company/role split as scripts/normalize_label_names, so a fresh
        # import cannot reintroduce names like "binance reserve wallets ETH".
        label_names.apply(row)
        rows.append(row)

    return rows, rejected


async def verify_on_chain(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Keep only exchange candidates that behave like live exchange wallets
    ON THE CHAIN THE LABEL CLAIMS.

    One eth_getCode plus one eth_getTransactionCount per address, against
    that row's own chain, throttled to the free tier. A contract that
    has never sent a transaction is a token or protocol contract, not a
    wallet holding customer deposits - and those are exactly the entries
    that would otherwise produce a false attribution.

    The per-chain check is what makes a multi-chain import safe: an
    address can be a live Binance wallet on Ethereum and an idle
    lookalike on Polygon, and only the per-chain nonce tells them
    apart. A wallet that has never transacted on the labelled chain is
    dropped, however famous it is elsewhere.

    THREE outcomes, not two. `kept` and `dropped` are verdicts: this is a
    real exchange wallet, or it is not. `unverified` is neither - we have
    no explorer API for that chain at all, so the address is neither
    confirmed nor refuted. Those rows are counted and reported but never
    imported: an unverified label would put a 95%-confidence name on the
    map with nothing behind it, which is the one failure this tool must
    never produce.

    Mixer and bridge rows skip this: they are legitimately contracts.
    """
    need_check = [r for r in rows if r["type"] == "exchange"]
    passthrough = [r for r in rows if r["type"] != "exchange"]

    if not config.has_etherscan_key():
        print("  ! ETHERSCAN_API_KEY missing - skipping on-chain verification")
        return rows, [], []

    kept, dropped, unverified = list(passthrough), [], []
    total = len(need_check)
    print(f"  verifying {total} exchange candidates on-chain "
          f"(~{total * 2 * config.ETHERSCAN_REQUEST_DELAY_SEC / 60:.1f} min)…")

    async with httpx.AsyncClient(timeout=45) as client:
        async def rpc(action: str, address: str, chain_id: int):
            # Same door the tracer uses: config.chain_api picks Etherscan V2 or a
            # chain's own explorer. Verifying a label through a different API than
            # the trace would use would verify it against a different ledger.
            base_url, api_key, send_chainid = config.chain_api(chain_id)
            params = {
                "module": "proxy", "action": action, "address": address,
                "tag": "latest", "apikey": api_key,
            }
            if send_chainid:
                params["chainid"] = chain_id
            response = await client.get(base_url, params=params)
            await asyncio.sleep(config.ETHERSCAN_REQUEST_DELAY_SEC)
            body = response.json()
            if str(body.get("status", "")) == "0":
                raise RuntimeError(str(body.get("result")))
            return body.get("result")

        for index, row in enumerate(need_check, 1):
            if index % 50 == 0:
                print(f"    {index}/{total} checked…")
            # Verify against the row's OWN chain. The chainid comes from
            # the project's chain table, not from the pack, so a pack
            # cannot make us query a chain we do not know.
            chain = config.chain_by_slug(row["chain"])
            if chain is None:  # defensive: parse_pack already enforced this
                row["reason"] = f"unknown chain {row['chain']}"
                dropped.append(row)
                continue
            chain_id = chain["chain_id"]
            if not config.chain_readable(chain_id):
                # Said plainly rather than as a lookup failure: the data is
                # probably fine, our API plan simply cannot reach this chain.
                # That is a different problem from a wrong address, and it has a
                # different fix (a key for that chain's own explorer).
                row["reason"] = (
                    f"no explorer API configured for {row['chain']} "
                    f"(chainid {chain_id}) - unverified"
                )
                unverified.append(row)
                continue
            try:
                code = await rpc("eth_getCode", row["address"], chain_id)
                nonce_hex = await rpc("eth_getTransactionCount", row["address"], chain_id)
                nonce = int(nonce_hex, 16)
            except Exception as exc:  # noqa: BLE001 - a lookup failure is not a verdict
                row["reason"] = f"lookup failed ({exc})"
                dropped.append(row)
                continue

            is_contract = bool(code) and code != "0x"
            if is_contract and nonce == 0:
                row["reason"] = "contract that has never sent a transaction (token/protocol)"
                dropped.append(row)
            elif nonce < MIN_NONCE_FOR_EXCHANGE:
                row["reason"] = f"only {nonce} outgoing txs on {row['chain']} - not exchange-scale"
                dropped.append(row)
            else:
                row["nonce"] = nonce
                kept.append(row)

    return kept, dropped, unverified


def merge(rows: list[dict], dry_run: bool) -> dict:
    """
    Fold accepted rows into labels.json, leaving hand-verified entries untouched.

    Deduplication is on the lowercased address WITHIN one chain. An address
    already present on that chain is left exactly as it is - the existing file
    was checked on-chain by hand, and a scraped label must never quietly
    replace a verified one. The same address on ANOTHER chain is a separate
    entry, because it is a separate wallet.

    Every new entry carries the chain it was verified on, which is what
    makes the label store chain-aware: the same 0x address can be Binance
    on Ethereum and Binance on BNB Chain, and neither claim bleeds into
    the other.
    """
    raw = json.loads(config.LABELS_PATH.read_text(encoding="utf-8"))
    existing_keys = {k for k in raw if not k.startswith("_")}

    # (chain, address) of what the file already holds, so an import can
    # add the same wallet on a new chain without duplicating or clashing.
    from core import identify as _identify
    indexed = _identify.load_labels(force_reload=True)

    stats = {"before": len(existing_keys), "added": 0, "already_present": 0, "dupes_in_feed": 0}
    seen: set[tuple[str, str]] = set()
    # Count each already-known (chain, address) once, however many packs mention it.
    hit_existing: set[tuple[str, str]] = set()
    additions: dict[str, dict] = {}

    for row in rows:
        address = row["address"]
        chain = row["chain"]
        if (chain, address) in indexed:
            hit_existing.add((chain, address))
            continue
        if (chain, address) in seen:
            stats["dupes_in_feed"] += 1
            continue
        seen.add((chain, address))
        # File keying convention (see core/identify.load_labels): a bare
        # address means Ethereum; anything on another chain is keyed
        # "<chain>:<address>" so the same wallet on two chains is two
        # entries, not one overwriting the other.
        key = address if chain == "ethereum" else f"{chain}:{address}"
        # Provenance chain stated on the row itself: the pack (MIT) AND the
        # pack's own upstream source - never collapsed to a tidier origin.
        entries = apply_provenance.pack_entries(
            [{"pack": row["source"].rsplit(".", 1)[0], "source_url": row.get("source_url", "")}]
        )
        additions[key] = {
            "entity": row["entity"],
            "type": row["type"],
            "chain": chain,
            "source": "graphsense-tagpacks",
            **{k: row[k] for k in ("role", "source_name", "name_note") if row.get(k)},
            "evidence_tier": "third_party_pack",
            "redistributable": True,
            "citation": apply_provenance.pack_citation(entries),
            "provenance": entries,
        }
        stats["added"] += 1

    stats["already_present"] = len(hit_existing)
    stats["after"] = stats["before"] + stats["added"]

    if not dry_run and additions:
        raw.update(additions)
        config.LABELS_PATH.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    return stats


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    parser.add_argument("--no-verify", action="store_true", help="skip the on-chain check")
    parser.add_argument(
        "--packs", nargs="+", metavar="FILE",
        help="import only these pack filenames (for retrying ones that failed)",
    )
    args = parser.parse_args()

    # The GitHub contents API allows 60 unauthenticated calls an hour, so a
    # pack can fail with a 403 through no fault of the data. Re-running is safe
    # (existing entries always win); this just avoids re-verifying everything.
    packs = PACKS
    if args.packs:
        unknown = [p for p in args.packs if p not in PACKS]
        if unknown:
            print(f"error: not in PACKS: {', '.join(unknown)}", file=sys.stderr)
            return 2
        packs = {p: PACKS[p] for p in args.packs}

    print(f"Fetching {len(PACKS)} packs from graphsense-tagpacks…\n")
    print(f"{'pack':<42} {'kept':>6} {'unsupported':>12} {'token-like':>11}")
    print("-" * 75)

    candidates: list[dict] = []
    for filename, default_type in packs.items():
        try:
            text = fetch_pack(filename)
        except Exception as exc:  # noqa: BLE001
            print(f"{filename:<42}  FAILED: {exc}")
            continue
        rows, rejected = parse_pack(text, filename, default_type)
        candidates.extend(rows)
        print(f"{filename:<42} {len(rows):>6} {rejected['not_supported_chain']:>12} "
              f"{rejected['token_like']:>11}")

    print("-" * 75)
    print(f"{'candidates after label filter':<42} {len(candidates):>6}\n")

    if not candidates:
        print("Nothing to import.")
        return 1

    dropped: list[dict] = []
    unverified: list[dict] = []
    if not args.no_verify:
        candidates, dropped, unverified = await verify_on_chain(candidates)
        print(f"\n  on-chain check: kept {len(candidates)}, dropped {len(dropped)}, "
              f"unverifiable {len(unverified)}")
        for row in dropped[:8]:
            print(f"    - {row['entity'][:34]:<34} {row.get('reason', '')}")
        if len(dropped) > 8:
            print(f"    … and {len(dropped) - 8} more")
        for row in unverified[:8]:
            print(f"    ? {row['entity'][:34]:<34} {row.get('reason', '')}")
        if len(unverified) > 8:
            print(f"    … and {len(unverified) - 8} more")
        if unverified:
            # Stated as a gap rather than a rejection: these rows are refused
            # because we cannot look, not because they are wrong.
            chains = sorted({r["chain"] for r in unverified})
            print(f"\n  NOT imported: {len(unverified)} exchange addresses on "
                  f"{', '.join(chains)} could not be verified because no explorer API\n"
                  f"  covers those chains on the current plan. This is a coverage gap on "
                  f"our side, not evidence the addresses are wrong.\n"
                  f"  Add a key for that chain's own explorer (e.g. BSCSCAN_API_KEY for "
                  f"BNB Chain) and re-run to verify them.")

    stats = merge(candidates, args.dry_run)

    print()
    print("=" * 71)
    print(f"  labels before      : {stats['before']}")
    print(f"  new addresses added: {stats['added']}")
    print(f"  already present    : {stats['already_present']} (kept the existing entry)")
    print(f"  duplicate in feed  : {stats['dupes_in_feed']}")
    print(f"  LABELS NOW         : {stats['after']}")
    # The per-chain count is the honest one: a Polygon trace is not helped
    # by Ethereum labels, so this is what says whether the import actually
    # closed the multi-chain gap.
    from core import identify as _identify
    _identify.load_labels(force_reload=not args.dry_run)
    for slug in ("ethereum", "bnb", "polygon", "arbitrum"):
        print(f"    labels on {slug:<10}: {_identify.label_count(slug)}")
    print("=" * 71)
    if args.dry_run:
        print("\n(dry run - data/labels.json was not modified)")
    return 0


# PACKS DELIBERATELY EXCLUDED
# ---------------------------
# ofac.yaml (572 tags) - would be the authoritative source for a "sanctioned"
#   type, but its lastmod is 2024-02-26. OFAC delisted Tornado Cash in March
#   2025, so importing this today would make the tool assert a sanctions status
#   that no longer holds against a real entity. Sanctions data must be pulled
#   live from the SDN list, not from a snapshot.
# ronin_bridge.yaml - despite the name, its tags are the Ronin ATTACKER's
#   wallets ("Ronin bridge exploiter"), not bridge infrastructure. Importing
#   them as type "bridge" would be simply wrong, and it would also label our
#   own demo start address.
# blender_io.yaml, sinbad_io.yaml, samourai.yaml, wasabi_collector.yaml -
#   Bitcoin mixers. Bitcoin is a future pipeline (Phase 10), not a chain this
#   build traces, so its labels would be inert - and unverified.
# exchange-wallets-bitmex_*.yaml - 2.3 MB each and overwhelmingly BTC; they
#   also exceed the GitHub contents API's inline size limit.
# Every pack's BTC/TRX/BEP2 tags - counted under "unsupported" above. The
#   tool cannot walk those chains yet, so a label there could never be
#   corroborated by a trace.

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
