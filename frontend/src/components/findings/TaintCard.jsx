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
      y: 15,
      opacity: 0,
      duration: 0.5,
      delay: 0.1,
      ease: 'power2.out',
    });
  }, { dependencies: [summary], scope: cardRef });

  if (!summary) return null;

  const taintedValue = summary.tainted_value_received;
  const grossValue = summary.value_received;
  const inflowFraction = summary.inflow_fraction;

  const hasTaint = taintedValue && Object.keys(taintedValue).length > 0;
  const percentStr =
    typeof inflowFraction === 'number' ? `${(inflowFraction * 100).toFixed(1)}%` : null;

  return (
    <div
      ref={cardRef}
      className="bg-white dark:bg-zinc-900/90 border border-slate-200 dark:border-zinc-800 rounded-2xl p-5 shadow-sm dark:shadow-xl transition-all"
    >
      {/* Title */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
          <h3 className="font-bold text-sm text-slate-900 dark:text-zinc-100">FIFO Taint Tracking</h3>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-100 dark:bg-cyan-500/10 text-cyan-700 dark:text-cyan-400 border border-cyan-300 dark:border-cyan-500/20 font-semibold">
          First-In, First-Out
        </span>
      </div>

      {/* Main Metric comparison */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
        {/* Tainted Value */}
        <div className="bg-slate-50 dark:bg-zinc-950 p-3.5 rounded-xl border border-slate-200 dark:border-zinc-800/80">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5 mb-1">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Suspect-Attributable Value
          </span>
          <p className="font-mono text-base sm:text-lg font-bold text-slate-900 dark:text-zinc-100">
            {hasTaint ? formatAssets(taintedValue) : '0.00'}
          </p>
          <span className="text-[10px] text-slate-500 dark:text-zinc-500 block mt-0.5">
            Stolen funds reaching this destination
          </span>
        </div>

        {/* Gross Value */}
        <div className="bg-slate-50 dark:bg-zinc-950 p-3.5 rounded-xl border border-slate-200 dark:border-zinc-800/80">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-600 dark:text-zinc-400 block mb-1">
            Gross Traced Inflow
          </span>
          <p className="font-mono text-base sm:text-lg font-semibold text-slate-700 dark:text-zinc-300">
            {grossValue ? formatAssets(grossValue) : '0.00'}
          </p>
          <span className="text-[10px] text-slate-500 dark:text-zinc-500 block mt-0.5">
            Total deposit volume at endpoint
          </span>
        </div>
      </div>

      {/* Inflow Fraction Progress Bar */}
      {percentStr && (
        <div className="mb-3 bg-slate-50 dark:bg-zinc-950/60 p-3 rounded-xl border border-slate-200 dark:border-zinc-800">
          <div className="flex justify-between items-center text-xs mb-1.5 font-medium">
            <span className="text-slate-600 dark:text-zinc-400">Tainted Share of Observed Inflow</span>
            <span className="font-mono text-cyan-600 dark:text-cyan-400 font-bold">{percentStr}</span>
          </div>
          <div className="w-full bg-slate-200 dark:bg-zinc-800 h-2 rounded-full overflow-hidden">
            <div
              className="bg-gradient-to-r from-cyan-500 to-emerald-400 h-full rounded-full transition-all duration-700 ease-out"
              style={{ width: `${Math.min(100, (inflowFraction || 0) * 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Clean Accounting Metadata Footer */}
      {accounting?.events_replayed > 0 && (
        <div className="pt-2 border-t border-slate-200 dark:border-zinc-800/80 flex items-center justify-between text-[11px] font-mono text-slate-500 dark:text-zinc-400">
          <span>Replayed {accounting.events_replayed} transfers</span>
          <span>{accounting.observed_wallets} wallets tracked</span>
        </div>
      )}
    </div>
  );
}
