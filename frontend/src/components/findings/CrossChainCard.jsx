import { ArrowRightLeft, ShieldAlert, CircleSlash } from 'lucide-react';

const STATUS = {
  matched: {
    label: 'FOLLOWED',
    cls: 'text-emerald-300 bg-emerald-950/40 border-emerald-500/50',
  },
  ambiguous: {
    label: 'AMBIGUOUS — NOT FOLLOWED',
    cls: 'text-amber-300 bg-amber-950/40 border-amber-500/50',
  },
  no_match: {
    label: 'NO MATCH — NOT FOLLOWED',
    cls: 'text-amber-300 bg-amber-950/40 border-amber-500/50',
  },
  hop_cap_reached: {
    label: 'STOPPED AT CROSSING LIMIT',
    cls: 'text-[#627EEA] bg-[#151726] border-[#627EEA]/50',
  },
  unsupported: {
    label: 'RECOGNISED BRIDGE — NOT FOLLOWED',
    cls: 'text-zinc-300 bg-zinc-900/60 border-zinc-700',
  },
  not_registered: {
    label: 'BRIDGE NOT IN OUR REGISTRY',
    cls: 'text-zinc-300 bg-zinc-900/60 border-zinc-700',
  },
  destination_unavailable: {
    label: 'DESTINATION CHAIN UNREADABLE',
    cls: 'text-zinc-300 bg-zinc-900/60 border-zinc-700',
  },
};

/**
 * What the trace did about bridges, and how sure it is.
 *
 * Two things have to be visible here, and both are easy to lose:
 *
 *  1. A chain crossing is an INFERENCE. The deposit is on record; the arrival of
 *     the same value on another chain is matched by amount, timing and recipient
 *     address. Presenting it as one more hop would quietly upgrade a judgement
 *     call into a transaction.
 *
 *  2. Crossings we DECLINED are evidence. A bridge that was ambiguous, unmatched,
 *     or simply not in our registry is where the trail goes cold, and an
 *     investigator needs to know that before deciding to widen the search.
 *
 * The coverage note matters just as much: without labels on the destination chain
 * we cannot name an exchange there, so "no exchange found" on that chain means
 * "we would not have recognised one", not "there wasn't one".
 */
export default function CrossChainCard({ cross }) {
  if (!cross) return null;
  const handoffs = cross.handoffs || [];
  const chains = cross.chains_traced || [];
  if (handoffs.length === 0 && chains.length < 2) return null;

  const coverage = cross.label_coverage || {};
  const unlabelled = Object.entries(coverage)
    .filter(([, info]) => info && !info.identification_possible)
    .map(([slug]) => slug);
  const isCrossChain = chains.length > 1;

  return (
    <div className="bg-[#0a0a0a] border border-[#262626] p-3 space-y-3 font-mono">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-bold text-cyan-300 flex items-center gap-1.5 uppercase tracking-wider">
          <ArrowRightLeft className="w-3 h-3" />
          Cross-Chain Movement
        </span>
        {isCrossChain && (
          <span className="text-[9px] text-[#888888] uppercase">
            {chains.length} chains traced
          </span>
        )}
      </div>

      {/* Chains examined */}
      {isCrossChain && (
        <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-[#a3a3a3]">
          {chains.map((slug, i) => (
            <span key={slug} className="flex items-center gap-1.5">
              {i > 0 && <span className="text-cyan-400">&rarr;</span>}
              <span className="px-1.5 py-0.5 border border-[#262626] bg-[#111111] uppercase">
                {slug}
              </span>
            </span>
          ))}
          {cross.hops_used != null && (
            <span className="text-[#666666] ml-1">
              ({cross.hops_used} crossing{cross.hops_used === 1 ? '' : 's'} of max{' '}
              {cross.max_hops})
            </span>
          )}
        </div>
      )}

      {/* The inference caveat. Always shown when a crossing was attempted. */}
      {handoffs.length > 0 && (
        <div className="border border-cyan-500/40 bg-cyan-950/20 p-2 text-[10px] leading-relaxed text-cyan-200/90">
          <span className="font-bold text-cyan-300 uppercase block mb-1">
            Crossings are inferred, not observed
          </span>
          A deposit is on record on one chain. The arrival of the same value on
          another is matched by amount, timing, recipient address and payout
          contract. Each crossing carries its own score, reported separately and
          never merged into the on-chain confidence score.
        </div>
      )}

      {/* Coverage limit */}
      {unlabelled.length > 0 && (
        <div className="border border-amber-500/40 bg-amber-950/20 p-2 text-[10px] leading-relaxed text-amber-200/90 flex items-start gap-1.5">
          <ShieldAlert className="w-3 h-3 mt-0.5 shrink-0 text-amber-400" />
          <span>
            <span className="font-bold uppercase block">
              Coverage limit
            </span>
            We hold no entity labels for {unlabelled.join(', ')}. An exchange there
            could not be recognised by name, so this route may understate where the
            money actually went.
          </span>
        </div>
      )}

      {/* Each handoff */}
      {handoffs.map((h, idx) => {
        const meta = STATUS[h.status] || {
          label: h.status,
          cls: 'text-zinc-300 bg-zinc-900/60 border-zinc-700',
        };
        const deposit = h.deposit || {};
        const entity = deposit.entity || h.bridge?.entity || 'Bridge';
        const chosen = h.chosen;

        return (
          <div
            key={`${entity}-${idx}`}
            className="border border-[#262626] bg-[#111111] p-2 space-y-1.5 text-[10px]"
          >
            <div className="flex justify-between items-start gap-2">
              <span className="text-[#f5f5f5] font-bold truncate">{entity}</span>
              <span
                className={`px-1.5 py-0.5 border text-[9px] font-bold uppercase shrink-0 ${meta.cls}`}
              >
                {meta.label}
              </span>
            </div>

            <div className="text-[#888888] uppercase">
              {deposit.chain || '?'} <span className="text-cyan-400">&rarr;</span>{' '}
              {deposit.to_chain || '?'}
            </div>

            {h.reason && (
              <p className="text-[#a3a3a3] leading-relaxed">{h.reason}</p>
            )}

            {chosen && (
              <div className="border-t border-[#262626] pt-1.5 space-y-1 text-[#a3a3a3]">
                <div className="flex justify-between">
                  <span>Arrived</span>
                  <span className="text-[#f5f5f5]">
                    {chosen.value} {chosen.asset}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Match score</span>
                  <span className="text-emerald-300 font-bold">
                    {h.confidence_score}/100
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Attributable to suspect</span>
                  <span className="text-[#f5f5f5]">
                    {(h.tainted_value ?? 0).toFixed(6)} {chosen.asset}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Delay after deposit</span>
                  <span>{chosen.lag_sec}s</span>
                </div>
                {chosen.tx_hash && (
                  <div className="flex justify-between">
                    <span>Payout tx</span>
                    <span className="truncate">{shortTx(chosen.tx_hash)}</span>
                  </div>
                )}
              </div>
            )}

            {/* EVERY candidate, on every outcome. Shown so the decision can be
                challenged on the evidence rather than taken on trust - including a
                followed crossing, where hiding the list would make "the only
                candidate" and "the best of several" look identical. The one we
                followed, if any, is marked. */}
            {(h.candidates || []).length > 0 && (
              <div className="border-t border-[#262626] pt-1.5 space-y-1">
                <span className="text-[#888888] uppercase flex items-center gap-1">
                  <CircleSlash className="w-3 h-3" />
                  Candidates considered ({h.candidates.length})
                </span>
                {h.candidates.map((c, ci) => {
                  const followed = chosen && c.tx_hash === chosen.tx_hash;
                  return (
                    <div
                      key={c.tx_hash || ci}
                      className={`flex justify-between ${followed ? 'text-emerald-300' : 'text-[#666666]'}`}
                    >
                      <span className="truncate">
                        {followed ? '✓ ' : ''}
                        {c.value} {c.asset} · {c.lag_sec}s · {shortTx(c.tx_hash)}
                      </span>
                      <span>{c.score}/100</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function shortTx(hash) {
  const h = String(hash || '');
  return h.length > 18 ? `${h.slice(0, 10)}…${h.slice(-6)}` : h;
}