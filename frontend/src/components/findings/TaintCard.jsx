import { useRef } from 'react';
import { Layers, CheckCircle2 } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { formatAssets } from '../../utils/formatters';

gsap.registerPlugin(useGSAP);

export default function TaintCard({ summary, accounting }) {
  const cardRef = useRef(null);

  useGSAP(() => {
    gsap.from(cardRef.current, {
      y: 12,
      opacity: 0,
      duration: 0.4,
      ease: 'power2.out',
    });
  }, { dependencies: [summary], scope: cardRef });

  if (!summary) return null;

  // "We computed nothing" and "we computed zero" are different statements, and
  // only the second one is a finding. `taint_computed` is the backend's own
  // statement of whether the FIFO replay ran at all. When it did not - or when
  // the field is simply absent, as in recordings that predate the FIFO pass -
  // the figures below are not answers and the card says so instead of printing
  // "0.00 stolen", which reads as "none of this was stolen money".
  //
  // An absent field used to count as "computed" (`!== false`), which is exactly
  // backwards: silence from the backend is not evidence that the analysis ran.
  const taintComputed = summary.taint_computed === true;
  const recordingPredatesTaint = summary.taint_computed === undefined;

  // No endpoint was reached, so there is no wallet to measure arrival at. That
  // is neither "zero arrived" nor "not calculated"; it is "nothing to measure".
  const hasEndpoint = typeof summary.hop_distance === 'number';
  if (!hasEndpoint) {
    return (
      <div
        ref={cardRef}
        className="bg-white dark:bg-[#111111] border border-[#d4d4d8] dark:border-[#262626] p-4 sm:p-5 shadow-[3px_3px_0px_#18181b] dark:shadow-[3px_3px_0px_#000000] space-y-2"
      >
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-[#627EEA]" />
          <h3 className="font-bold text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5]">
            Stolen Funds Accounting
          </h3>
        </div>
        <p className="text-xs text-[#52525b] dark:text-[#a3a3a3] leading-relaxed">
          No exchange or collection point was reached, so there is no endpoint to
          measure arrival at.{' '}
          {taintComputed
            ? 'The FIFO replay did run over the transfers fetched; it simply has no destination to report a figure for.'
            : 'The FIFO replay was not performed for this result.'}
        </p>
      </div>
    );
  }

  const taintedValue = summary.tainted_value_received;
  const grossValue = summary.value_received;
  // The backend emits `tainted_inflow_fraction` as a PER-ASSET map
  // ({ETH: 1.0, USDT: 0.4}), not a single number. An untyped `undefined`
  // here used to fall through to a hard-coded "100%", so a wallet where
  // only 40% of the inflow was the suspect's money still reported 100% -
  // the single most over-claiming line on the panel. A fraction only
  // appears once at least one asset carries one.
  const inflowByAsset = summary.tainted_inflow_fraction;
  const inflowFractions = inflowByAsset && typeof inflowByAsset === 'object'
    ? Object.values(inflowByAsset).filter((v) => typeof v === 'number')
    : [];

  const hasTaint = taintedValue && Object.keys(taintedValue).length > 0;
  // Fully observed = every asset's inflow is 100% accounted for. Below
  // 1.0 means either part of the inflow is pre-existing balance, or the
  // wallet's own history was never fetched, and the backend says which
  // via `inflow_fully_observed`. Guessing would be worse than saying so.
  const fullyObserved = summary.inflow_fully_observed === true;
  const percentStr =
    inflowFractions.length === 0
      ? null
      : `${((Math.min(...inflowFractions)) * 100).toFixed(1)}%`;
  const barWidth =
    inflowFractions.length === 0 ? 100 : Math.min(100, Math.min(...inflowFractions) * 100);

  return (
    <div
      ref={cardRef}
      className="bg-white dark:bg-[#111111] border border-[#d4d4d8] dark:border-[#262626] p-4 sm:p-5 transition-all shadow-[3px_3px_0px_#18181b] dark:shadow-[3px_3px_0px_#000000] space-y-3"
    >
      {/* Title */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-[#627EEA]" />
          <h3 className="font-bold text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5]">
            Stolen Funds Accounting
          </h3>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 bg-[#627EEA]/10 text-[#627EEA] border border-[#627EEA]/30 font-semibold uppercase">
          {taintComputed ? 'FIFO Ledger Replay' : 'Accounting Not Performed'}
        </span>
      </div>

      {/* The replay did not run, so no figure below means anything. */}
      {!taintComputed && (
        <p className="text-xs text-[#52525b] dark:text-[#a3a3a3] leading-relaxed">
          {recordingPredatesTaint
            ? 'This result carries no taint analysis (the recording predates the FIFO pass), so '
            : 'The FIFO replay did not run for this trace, so '}
          the split between the suspect's money and pre-existing balance was{' '}
          <strong>not calculated</strong>. The gross inflow below is observed value only,
          not an amount attributable to the suspect.
        </p>
      )}

      {/* Main Metric comparison */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {/* Tainted Value */}
        <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] p-3 border border-[#d4d4d8] dark:border-[#262626]">
          <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-red-600 dark:text-red-400 flex items-center gap-1 mb-0.5">
            <CheckCircle2 className="w-3 h-3" />
            Stolen Portion at Destination
          </span>
          <p className="font-mono text-base font-extrabold text-[#09090b] dark:text-[#f5f5f5]">
            {!taintComputed
              ? 'Not calculated'
              : summary.tainted_value_display ||
                (hasTaint ? formatAssets(taintedValue) : '0.00')}
          </p>
          <span className="text-[10px] text-[#71717a] dark:text-[#888888] block mt-0.5 font-mono">
            Stolen crypto reaching this wallet
          </span>
        </div>

        {/* Gross Value */}
        <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] p-3 border border-[#d4d4d8] dark:border-[#262626]">
          <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#71717a] dark:text-[#888888] block mb-0.5">
            Inflow Along Traced Edges
          </span>
          <p className="font-mono text-base font-bold text-[#09090b] dark:text-[#f5f5f5]">
            {summary.value_received_display || (grossValue ? formatAssets(grossValue) : '0.00')}
          </p>
          <span className="text-[10px] text-[#71717a] dark:text-[#888888] block mt-0.5 font-mono">
            Gross value on the traced edges into this wallet
          </span>
        </div>
      </div>

      {/* Inflow Fraction Progress Bar. Hidden entirely when the backend sent
          no fraction, rather than showing a default that asserts a clean trail. */}
      {percentStr !== null && (
        <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] p-2.5 border border-[#d4d4d8] dark:border-[#262626] space-y-1.5">
          <div className="flex justify-between items-center text-xs font-mono">
            <span className="text-[#52525b] dark:text-[#a3a3a3]">Suspect Share of Observed Inflow</span>
            <span className="text-[#627EEA] font-bold">{percentStr}</span>
          </div>
          <div className="w-full bg-[#d4d4d8] dark:bg-[#262626] h-2 overflow-hidden">
            <div
              className="bg-[#627EEA] h-full transition-all duration-700 ease-out"
              style={{ width: `${barWidth}%` }}
            />
          </div>
          {/* WHY THIS MEASUREMENT IS PARTIAL. The trace stops at this wallet, so
              its own history is not fetched; the share is measured only against
              the transfers the trace observed, not against everything the wallet
              received. The backend says so explicitly, and repeating it here keeps
              a 100% figure from reading as "we checked every incoming dollar". */}
          {!fullyObserved && summary.inflow_note && (
            <p className="text-[10px] text-[#71717a] dark:text-[#888888] leading-snug font-sans">
              {summary.inflow_note}
            </p>
          )}
        </div>
      )}

      {/* Explanatory footer */}
      {taintComputed && (
        <p className="text-[11px] text-[#71717a] dark:text-[#888888] leading-tight">
          Calculated under First-In, First-Out (FIFO) accounting: funds leave each
          wallet in the order they arrived. FIFO is a stated convention, not the only
          one; a different rule would attribute a different amount from the same
          transactions.
        </p>
      )}

      {/* Accounting Replay Stats if present */}
      {accounting?.events_replayed > 0 && (
        <div className="pt-2 border-t border-[#d4d4d8] dark:border-[#262626] flex items-center justify-between text-[11px] font-mono text-[#71717a] dark:text-[#888888]">
          <span>Replayed {accounting.events_replayed} transactions</span>
          {/* `wallets_observed` is the field the backend emits. The old read of
              `observed_wallets` matched nothing and rendered " wallets tracked". */}
          <span>
            {accounting.wallets_observed ?? accounting.observed_wallets ?? 0} wallets
            tracked
          </span>
        </div>
      )}
    </div>
  );
}
