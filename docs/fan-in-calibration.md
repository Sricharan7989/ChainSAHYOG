# Fan-in threshold calibration

How ChainSAHYOG decides that an unlabelled address is a *suspected exchange collection point*, and where the two thresholds come from. They were measured against verified exchange addresses, not chosen by hand. Reproduce with `python -m scripts.calibrate_fanin` (backend/); the raw measurements are in `data/calibration/fanin_sample.json`.

## The question

The consolidation heuristic flags a wallet that many traced wallets pay into. Within one trace, "several of the suspect's own paths reconverge" and "an exchange collects deposits from hundreds of customers" look the same. Since Step 4 every candidate is also checked against how many distinct addresses have paid it chain-wide. That check needs a threshold, and the earlier figure (20 raw senders) let the Ronin attacker's own re-pooling wallet through.

## Sample

- **Pinned at Ethereum block 26125179.** Every figure below is as of that block.
- **Positives:** 70 labelled Ethereum exchange wallets. The sample is deterministic and stratified, with at most 2 wallets per company so that no single company dominates (seed 26182). Labels inferred from another chain were excluded.
- **Negatives:** 9 wallets known to be attackers re-pooling their own funds: the Ronin trace's candidate `0xee009faf...` and the OFAC-listed Lazarus Group wallets from the Ronin trace.
- **Measurement:** for each wallet, the two calls the tracer itself makes (`EtherscanClient.get_inbound_senders`): the newest page of normal transactions and the newest page of token transfers, up to 1,000 rows each.
- **Cost:** 159 API calls for the whole calibration, 2 per wallet.

## Finding 1: raw sender counts do not separate

- Positives: min 6, 10th pct 56, 25th pct 164, median 380.5, max 1483.
- Negatives: min 3, 10th pct 3, 25th pct 12, median 12, max 204.

An OFAC-listed Lazarus wallet (`0x098b...`) shows 204 raw senders. Sanctioned and high-profile addresses attract zero-value "address poisoning" transfers and fake-token spam from strangers, which inflate a raw count. So senders are counted **only over non-dust transfers of assets the tool follows** (native coin above its dust floor, or an allowlisted token contract above its dust floor). That is the measure used from here on.

## Finding 2: value senders separate the attacker pools, but the populations touch

- Negatives: min 1, 10th pct 1, 25th pct 1, median 1, max 9. The highest are `0xee009faf...` and `0x098b...`, with 9 each.
- All positives: min 0, 10th pct 2, 25th pct 8, median 58.5, max 830.
- 20 of the 70 positives also have 9 or fewer value senders. These are genuine exchange addresses that do **not** collect deposits in their recent history: dormant or defunct wallets (Cryptopia, Yunbi, Bittrex, BiteBTC) and withdrawal-only wallets (Crypto.com `0x46340b...` has 826 recipients and 0 value senders). A fan-in test cannot find these, and should not try; labels do that.
- The remaining 50 positives are the deposit-collecting population: min 10, 10th pct 17, 25th pct 44, median 124.5, max 830. The lowest is Uex `0x2f1233ec3a4930fd95874291db7da9e90dfb2f03`, with 10 value senders.

**The gap is one sender wide** (negatives max 9, lowest collecting positive 10). There is no clean split with a margin, and this document does not pretend otherwise.

## Threshold 1: at least 20 value senders

Set at 20, a little over twice the highest negative. On this sample it rejects all 9 negatives and keeps 44 of the 50 collecting positives. The 6 it drops are small exchanges with 10 to 17 value senders. A floor of 10 would keep them all, but it would sit one sender above the attacker wallets. For a tool whose output can trigger a legal request, a missed small exchange (still visible as a path, and still findable by label) is the cheaper error than calling an attacker's pool an exchange.

## Threshold 2: at least 0.01 value senders per outgoing transaction

A collection point receives from many wallets and pays out in sweeps. An attacker's pool receives from a few and fans out. Two versions of this ratio were tested on the same sample:

- **Senders per distinct recipient does not separate.** Negatives range 0.11 to 0.67, and collecting positives have a median of 0.96 but a 10th percentile of 0.14. Labelled exchange wallets are mostly hot wallets, which also pay withdrawals out to many customers.
- **Senders per outgoing transaction separates the dangerous cases.** Negatives: [0.007, 0.009, 0.111, 0.125, 0.143, 0.25, 0.25, 0.333, 0.5]. The two negatives closest to the floor, `0xee009faf...` and `0x098b...`, are at 0.007 and 0.009: a few senders against well over a thousand outgoing transactions, the attacker shape. Collecting positives: min 0.005, 10th pct 0.018, 25th pct 0.044, median 0.115, max 3.347.

Set at 0.01, this second condition catches exactly those two. It costs 3 of the 50 collecting positives on its own. On this sample it is redundant with the floor, which already rejects every negative. It is kept as a second, independent line, aimed at a pool that collects non-dust value from many senders but fans out like an attacker.

## Combined

Both conditions keep 44 of 50 collecting positives and 0 of 9 negatives.

## What this calibration does and does not show

The result is weaker than the clean "0 of 9 negatives kept" figure suggests, and the tool says so itself.

1. **The populations nearly overlap.** The attacker maximum is 9 value senders and the lowest genuine collecting exchange has 10. A one-sender gap is not a reliable separation. Fan-in is a weak signal, not a detector. That is why a fan-in-only identification is **capped at 67%** (`scoring.FAN_IN_MAX_SCORE`, enforced whatever the bonuses) and **never names a company**: it is reported as an unconfirmed collection point to verify before any request. Every fan-in lead carries this sentence in the finding panel and the PDF.
2. **Fan-in can only find wallets that are currently collecting.** 20 of the 70 labelled exchange wallets in the sample are dormant or withdrawal-only. No structural method will ever find them; only a label names such a wallet. This is stated in every chain's label-coverage note.
3. **The sample is entirely Ethereum.** Applying these thresholds to Tron, or later Bitcoin, is an assumption, not a measurement. A fan-in lead on another chain says so. Re-calibrate per chain (same script, that chain's labelled wallets) once each has enough labelled exchange wallets to sample. Tron has 27 today, too few for a separate calibration.

4. **Contracts are excluded before any threshold applies.** Running the calibrated rules on the 0x6242 demo flagged 56 "collection points", many of them well-known DeFi contracts: WETH, Uniswap's routers, pools and v4 PoolManager, 1inch, CoW, LI.FI. A contract has enormous fan-in from unrelated senders and passes any sender threshold, but it is not an exchange's deposit-collection wallet, which is an ordinary account. The sample above measured sender counts only, so it never tested this. Every candidate is now checked for contract code first (one call: `eth_getCode` on EVM, `getcontract` on Tron), and a contract is rejected with that reason. On Ronin this also removes the remaining lead, `0xcad001c3...`, which is a contract.

## Limits

- **The counts are lower bounds** from each wallet's newest page of rows, not lifetime totals. Etherscan has no "count distinct senders" endpoint, and paging a hot wallet's full history is not affordable per candidate.
- **The negative set is small** (one heist's wallets). Rerun this script as more known re-pooling wallets are found, and revisit the thresholds if a negative crosses them.
- **Ethereum only.** On Tron the same rules apply, with Tron's own dust floors. A Tron calibration should follow once Tron has enough labelled exchange wallets to sample.

## Per-address figures

| Group | Entity | Role | Address | Value senders | Raw senders | Value recipients | Outgoing rows | Senders/out tx | Passes both |
|---|---|---|---|---:|---:|---:|---:|---:|:---:|
| negative | Ronin trace candidate: attacker re-pooling (6 traced senders) | - | `0xee009faf00cf54c1b4387829af7a8dc5f0c8c8c5` | 9 | 44 | 32 | 1312 | 0.007 | no |
| negative | Lazarus Group (OFAC SDN) | - | `0x098b716b8aaf21512996dc57eb0615e2383e2f96` | 9 | 204 | 26 | 1017 | 0.009 | no |
| negative | Lazarus Group (OFAC SDN) | - | `0xa0e1c89ef1a489c9c7de96311ed5ce5d32c20e4b` | 2 | 3 | 3 | 4 | 0.500 | no |
| negative | Lazarus Group (OFAC SDN) | - | `0x08723392ed15743cc38513c4925f5e6be5c17243` | 1 | 11 | 4 | 4 | 0.250 | no |
| negative | Lazarus Group (OFAC SDN) | - | `0x35fb6f6db4fb05e6a4ce86f2c93691425626d4b1` | 1 | 12 | 9 | 9 | 0.111 | no |
| negative | Lazarus Group (OFAC SDN) | - | `0x3cffd56b47b7b41c56258d9c7731abadc360e073` | 1 | 19 | 3 | 4 | 0.250 | no |
| negative | Lazarus Group (OFAC SDN) | - | `0x3e37627deaa754090fbfbb8bd226c1ce66d255e9` | 1 | 12 | 7 | 7 | 0.143 | no |
| negative | Lazarus Group (OFAC SDN) | - | `0x53b6936513e738f44fb50d2b9476730c0ab3bfc1` | 1 | 19 | 3 | 3 | 0.333 | no |
| negative | Lazarus Group (OFAC SDN) | - | `0xf7b31119c2682c88d88d455dbb9d5932c65cf1be` | 1 | 12 | 8 | 8 | 0.125 | no |
| positive | FixedFloat | - | `0x4e5b2e1dc63f6b91cb6cd759936495434c7e972f` | 830 | 865 | 530 | 969 | 0.857 | yes |
| positive | Gate.io | - | `0x7793cd85c11a924478d358d49b05b37e91b5810f` | 778 | 1483 | 14 | 337 | 2.309 | yes |
| positive | Eigen Fx | - | `0xeb9ebf2c624ebee42e0853da6443ddc6c8020de7` | 559 | 864 | 23 | 167 | 3.347 | yes |
| positive | MEXC | - | `0x0211f3cedbef3143223d3acf0e589747933e8527` | 507 | 932 | 2 | 917 | 0.553 | yes |
| positive | BitMart | - | `0xe79eef9b9388a4ff70ed7ec5bccd5b928ebb8bd1` | 458 | 1308 | 3 | 562 | 0.815 | yes |
| positive | Coinbene | cold wallet | `0x33683b94334eebc9bd3ea85ddbda4a86fb461405` | 455 | 1284 | 6 | 509 | 0.894 | yes |
| positive | WhiteBIT | - | `0x39f6a6c85d39d5abad8a398310c52e7c374f2ba3` | 439 | 461 | 485 | 1499 | 0.293 | yes |
| positive | Bitstamp | - | `0x1522900b6dafac587d499a862861c0869be6e428` | 433 | 438 | 1 | 197 | 2.198 | yes |
| positive | Azbit | - | `0x92dbd8e0a46edd62aa42d1f7902d0e496bddc15a` | 425 | 652 | 278 | 963 | 0.441 | yes |
| positive | Switchain | - | `0xa96b536eef496e21f5432fd258b6f78cf3673f74` | 413 | 598 | 92 | 1325 | 0.312 | yes |
| positive | FTX | - | `0xc098b2a3aa256d2140208c3de6543aaef5cd3a94` | 409 | 1170 | 65 | 314 | 1.303 | yes |
| positive | Bitzlato | - | `0x00cdc153aa8894d08207719fe921fff964f28ba3` | 387 | 399 | 833 | 1281 | 0.302 | yes |
| positive | Coinbase | - | `0x3cd751e6b0078be393132286c442345e5dc49699` | 375 | 617 | 621 | 1305 | 0.287 | yes |
| positive | Livecoin.net | - | `0x243bec9256c9a3469da22103891465b47583d9f1` | 333 | 441 | 216 | 413 | 0.806 | yes |
| positive | AscendEX | - | `0x4b1a99467a284cc690e3237bc69105956816f762` | 332 | 680 | 4 | 414 | 0.802 | yes |
| positive | MinedTrade.com | - | `0xac338d9faac562df26d702880c796e1024e2698a` | 332 | 362 | 283 | 1237 | 0.268 | yes |
| positive | BIKI.com | - | `0x6eff3372fa352b239bb24ff91b423a572347000d` | 331 | 1017 | 3 | 801 | 0.413 | yes |
| positive | C2CX | hot wallet | `0xd7c866d0d536937bf9123e02f7c052446588189f` | 229 | 408 | 285 | 1405 | 0.163 | yes |
| positive | Tidex | - | `0x0a73573cf2903d2d8305b1ecb9e9730186a312ae` | 186 | 192 | 382 | 1643 | 0.113 | yes |
| positive | COSS.io | - | `0x0d6b5a54f940bf3d52e438cab785981aaefdf40c` | 184 | 636 | 97 | 1244 | 0.148 | yes |
| positive | Bilaxy | - | `0xf7793d27a1b76cdf14db7c83e82c772cf7c92910` | 176 | 505 | 247 | 1230 | 0.143 | yes |
| positive | Gate.io | - | `0x0d0707963952f2fba59dd06f2b425ace40b492fe` | 173 | 346 | 203 | 1482 | 0.117 | yes |
| positive | SouthXchange | - | `0x324cc2c9fb379ea7a0d1c0862c3b48ca28d174a4` | 165 | 302 | 511 | 1532 | 0.108 | yes |
| positive | Sparrow Exchange | - | `0x91f6d99b232153cb655ad3e0d05e13ef505f6cd5` | 142 | 164 | 38 | 296 | 0.480 | yes |
| positive | MaiCoin | - | `0x477b8d5ef7c2c42db84deb555419cd817c336b6f` | 135 | 147 | 553 | 1757 | 0.077 | yes |
| positive | BitBlinx | - | `0x5d375281582791a38e0348915fa9cbc6139e9c2a` | 114 | 355 | 334 | 1386 | 0.082 | yes |
| positive | Tokocrypto | - | `0x0068eb681ec52dbd9944517d785727310b494575` | 81 | 152 | 88 | 787 | 0.103 | yes |
| positive | Cobinhood | - | `0x8958618332df62af93053cb9c535e26462c959b0` | 79 | 99 | 171 | 1827 | 0.043 | yes |
| positive | Bibox | - | `0xf73c3c65bde10bf26c2e1763104e609a41702efe` | 77 | 1456 | 63 | 517 | 0.149 | yes |
| positive | Artis Turba Exchange | - | `0xf0c80fb9fb22bef8269cb6feb9a51130288a671f` | 68 | 730 | 148 | 732 | 0.093 | yes |
| positive | Bitbee | - | `0x2b49ce21ad2004cfb3d0b51b2e8ec0406d632513` | 67 | 208 | 68 | 1384 | 0.048 | yes |
| positive | BITStorage | - | `0x1b8a38ea02ceda9440e00c1aeba26ee2dc570423` | 66 | 188 | 88 | 721 | 0.092 | yes |
| positive | Catex Exchange | - | `0x7a56f645dcb513d0326cbaa048e9106ff6d4cd5f` | 61 | 324 | 155 | 1387 | 0.044 | yes |
| positive | Bitexlive | - | `0x7217d64f77041ce320c356d1a2185bcb89798a0a` | 60 | 520 | 98 | 1001 | 0.060 | yes |
| positive | NEXBIT Pro | - | `0xae7006588d03bd15d6954e3084a7e644596bc251` | 59 | 209 | 100 | 1196 | 0.049 | yes |
| positive | Bidesk | - | `0x0bb5de248dbbd31ee6c402c3c4a70293024acf74` | 58 | 604 | 420 | 1328 | 0.044 | yes |
| positive | Flybit | - | `0x91e18ee76483fa2ec5cfe2959df46673c2565be0` | 49 | 249 | 14 | 1661 | 0.030 | yes |
| positive | Bitexlive | - | `0x57a47cfe647306a406118b6cf36459a1756823d0` | 44 | 103 | 43 | 266 | 0.165 | yes |
| positive | Exchange A | - | `0xd3808c5d48903be1490989f3fce2a2b3890e8eb6` | 40 | 161 | 113 | 1620 | 0.025 | yes |
| positive | ChainX | - | `0xfd648cc72f1b4e71cbdda7a0a91fe34d32abd656` | 37 | 306 | 287 | 1466 | 0.025 | yes |
| positive | Blockfolio | - | `0x25eaff5b179f209cf186b1cdcbfa463a69df4c45` | 33 | 569 | 789 | 1211 | 0.027 | yes |
| positive | Poloniex | - | `0xb794f5ea0ba39494ce839613fffba74279579268` | 33 | 727 | 24 | 225 | 0.147 | yes |
| positive | Hotbit | - | `0x274f3c32c90517975e29dfc209a23f315c1e5fc7` | 29 | 303 | 14 | 1655 | 0.018 | yes |
| positive | BitBase | - | `0x0d8824ca76e627e9cc8227faa3b3993986ce9e48` | 20 | 27 | 714 | 1808 | 0.011 | yes |
| positive | Binance | - | `0x44592b81c05b4c35efb8424eb9d62538b949ebbf` | 17 | 524 | 2 | 248 | 0.069 | no |
| positive | Trade.io | - | `0x1119aaefb02bf12b84d28a5d8ea48ec3c90ef1db` | 12 | 823 | 9 | 413 | 0.029 | no |
| positive | Binance | - | `0xd551234ae421e3bcba99a0da6d736074f22192ff` | 11 | 98 | 1 | 1878 | 0.006 | no |
| positive | Bybit | reserve wallet | `0xee5b5b923ffce93a870b3104b7ca09c3db80047a` | 11 | 474 | 21 | 868 | 0.013 | no |
| positive | Coinswitch | - | `0xd0808da05cc71a9f308d330bc9c5c81bbc26fc59` | 11 | 13 | 934 | 1751 | 0.006 | no |
| positive | Uex | - | `0x2f1233ec3a4930fd95874291db7da9e90dfb2f03` | 10 | 59 | 278 | 1848 | 0.005 | no |
| positive | Artis Turba Exchange | - | `0x94597850916a49b3b152ee374e97260b99249f5b` | 9 | 11 | 54 | 335 | 0.027 | no |
| positive | Indodax | - | `0x9cbadd5ce7e14742f70414a6dcbd4e7bb8712719` | 9 | 511 | 7 | 1256 | 0.007 | no |
| positive | TAGZ | - | `0xed8204345a0cf4639d2db61a4877128fe5cf7599` | 8 | 40 | 29 | 1841 | 0.004 | no |
| positive | Yobit.net | - | `0xf5bec430576ff1b82e44ddb5a1c93f6f9d0884f3` | 5 | 519 | 235 | 1292 | 0.004 | no |
| positive | OKX | - | `0x6cc5f688a315f3dc28a7781717a9a798a59fda7b` | 4 | 218 | 1 | 1303 | 0.003 | no |
| positive | BitMEX | - | `0xeea81c4416d71cef071224611359f6f99a4c4294` | 3 | 268 | 1 | 618 | 0.005 | no |
| positive | Liquid | - | `0xdf4b6fb700c428476bd3c02e6fa83e110741145b` | 3 | 495 | 215 | 1438 | 0.002 | no |
| positive | BiteBTC | - | `0x28ebe764b8f9a853509840645216d3c2c0fd774b` | 2 | 867 | 32 | 1030 | 0.002 | no |
| positive | Bittrex | - | `0x66f820a414680b5bcda5eeca5dea238543f42054` | 2 | 721 | 1 | 245 | 0.008 | no |
| positive | CoinExchange.io | - | `0x4b01721f0244e7c5b5f63c20942850e447f5a5ee` | 2 | 467 | 367 | 1530 | 0.001 | no |
| positive | HitBTC | - | `0x59a5208b32e627891c389ebafc644145224006e8` | 2 | 318 | 396 | 1537 | 0.001 | no |
| positive | Mercatox | - | `0xe03c23519e18d64f144d2800e30e81b0065c48b5` | 2 | 66 | 135 | 1891 | 0.001 | no |
| positive | Poloniex | CVC wallet | `0x31a2feb9b5d3b5f4e76c71d6c92fc46ebb3cb1c1` | 2 | 94 | 1 | 1489 | 0.001 | no |
| positive | BitUN.io | - | `0xf8d04a720520d0bcbc722b1d21ca194aa22699f2` | 1 | 13 | 116 | 1893 | 0.001 | no |
| positive | Yunbi | - | `0xd94c9ff168dc6aebf9b6cc86deff54f3fb0afc33` | 1 | 206 | 390 | 1773 | 0.001 | no |
| positive | Crypto.com | - | `0x46340b20830761efd32832a74d7169b29feb9758` | 0 | 6 | 826 | 1970 | 0.000 | no |
| positive | Cryptopia | - | `0x2984581ece53a4390d1f568673cf693139c97049` | 0 | 955 | 1 | 1031 | 0.000 | no |
| positive | Eidoo | - | `0xf1c525a488a848b58b95d79da48c21ce434290f7` | 0 | 56 | 0 | 0 | 0.000 | no |
| positive | KuCoin | - | `0xf16e9b0d03470827a95cdfd0cb8a8a3b46969b91` | 0 | 186 | 0 | 1455 | 0.000 | no |
| positive | Panda.Exchange | hot wallet 2 | `0xb709d82f0706476457ae6bad7c3534fbf424382c` | 0 | 33 | 0 | 29 | 0.000 | no |
