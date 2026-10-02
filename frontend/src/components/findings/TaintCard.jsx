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

  const taintedValue = summary.tainted_value_received;
  const grossValue = summary.value_received;
  const inflowFraction = summary.inflow_fraction;

  const hasTaint = taintedValue && Object.keys(taintedValue).length > 0;
  const percentStr =
    typeof inflowFraction === 'number' ? `${(inflowFraction * 100).toFixed(1)}%` : '100%';

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
          FIFO Ledger Replay
        </span>
      </div>

      {/* Main Metric comparison */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {/* Tainted Value */}
        <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] p-3 border border-[#d4d4d8] dark:border-[#262626]">
          <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-red-600 dark:text-red-400 flex items-center gap-1 mb-0.5">
            <CheckCircle2 className="w-3 h-3" />
            Stolen Portion at Destination
          </span>
          <p className="font-mono text-base font-extrabold text-[#09090b] dark:text-[#f5f5f5]">
            {summary.tainted_value_display || (hasTaint ? formatAssets(taintedValue) : '0.00')}
          </p>
          <span className="text-[10px] text-[#71717a] dark:text-[#888888] block mt-0.5 font-mono">
            Stolen crypto reaching this wallet
          </span>
        </div>

        {/* Gross Value */}
        <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] p-3 border border-[#d4d4d8] dark:border-[#262626]">
          <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#71717a] dark:text-[#888888] block mb-0.5">
            Total Inflow Observed
          </span>
          <p className="font-mono text-base font-bold text-[#09090b] dark:text-[#f5f5f5]">
            {summary.value_received_display || (grossValue ? formatAssets(grossValue) : '0.00')}
          </p>
          <span className="text-[10px] text-[#71717a] dark:text-[#888888] block mt-0.5 font-mono">
            Total volume traced into endpoint
          </span>
        </div>
      </div>

      {/* Inflow Fraction Progress Bar */}
      {percentStr && (
        <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] p-2.5 border border-[#d4d4d8] dark:border-[#262626] space-y-1.5">
          <div className="flex justify-between items-center text-xs font-mono">
            <span className="text-[#52525b] dark:text-[#a3a3a3]">Suspect Share of Observed Inflow</span>
            <span className="text-[#627EEA] font-bold">{percentStr}</span>
          </div>
          <div className="w-full bg-[#d4d4d8] dark:bg-[#262626] h-2 overflow-hidden">
            <div
              className="bg-[#627EEA] h-full transition-all duration-700 ease-out"
              style={{ width: `${Math.min(100, (inflowFraction || 1) * 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Explanatory footer */}
      <p className="text-[11px] text-[#71717a] dark:text-[#888888] leading-tight">
        Calculated using First-In, First-Out (FIFO) ledger math: funds leave intermediary wallets in the exact order received, providing deterministic evidence for court filings.
      </p>

      {/* Accounting Replay Stats if present */}
      {accounting?.events_replayed > 0 && (
        <div className="pt-2 border-t border-[#d4d4d8] dark:border-[#262626] flex items-center justify-between text-[11px] font-mono text-[#71717a] dark:text-[#888888]">
          <span>Replayed {accounting.events_replayed} transactions</span>
          <span>{accounting.observed_wallets} wallets tracked</span>
        </div>
      )}
    </div>
  );
}
