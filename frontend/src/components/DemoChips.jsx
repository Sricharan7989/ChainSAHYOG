import { useRef } from 'react';
import { PlayCircle, ShieldCheck, AlertOctagon } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { shortAddress } from '../utils/formatters';

gsap.registerPlugin(useGSAP);

export default function DemoChips({ demos, onSelectDemo, selectedAddress, loading }) {
  const containerRef = useRef(null);

  useGSAP(() => {
    if (demos && demos.length > 0) {
      gsap.from('.demo-chip', {
        scale: 0.9,
        opacity: 0,
        y: 10,
        stagger: 0.08,
        duration: 0.5,
        ease: 'back.out(1.5)',
      });
    }
  }, { dependencies: [demos], scope: containerRef });

  if (!demos || demos.length === 0) return null;

  return (
    <div ref={containerRef} className="flex flex-wrap items-center gap-2 pt-1 pb-2">
      <span className="text-xs font-medium text-slate-500 dark:text-zinc-400 flex items-center gap-1.5 mr-1">
        <PlayCircle className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
        <span>Pre-recorded Demos:</span>
      </span>

      {demos.map((demo) => {
        const isSelected = selectedAddress?.toLowerCase() === demo.address?.toLowerCase();
        const hasExchange = demo.summary?.found && demo.summary?.exchange;
        const isSanctioned = demo.summary?.risk_flags?.some(
          (f) => f.severity === 'critical' || f.risk_type === 'sanctioned'
        );

        return (
          <button
            key={demo.address}
            type="button"
            disabled={loading}
            onClick={() => onSelectDemo(demo)}
            className={`demo-chip text-xs px-3 py-1.5 rounded-full border transition-all flex items-center gap-2 shadow-xs cursor-pointer ${
              isSelected
                ? 'bg-cyan-50 dark:bg-cyan-500/20 text-cyan-700 dark:text-cyan-300 border-cyan-400 ring-1 ring-cyan-400/50 font-semibold'
                : 'bg-white dark:bg-zinc-900/80 hover:bg-slate-50 dark:hover:bg-zinc-800 text-slate-700 dark:text-zinc-300 border-slate-200 dark:border-zinc-700/80 hover:border-slate-300 dark:hover:border-zinc-600'
            }`}
          >
            {hasExchange ? (
              <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-semibold">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>{demo.summary.exchange}</span>
              </span>
            ) : isSanctioned ? (
              <span className="flex items-center gap-1 text-red-600 dark:text-red-400 font-semibold">
                <AlertOctagon className="w-3.5 h-3.5" />
                <span>Sanctioned Entity</span>
              </span>
            ) : (
              <span className="text-slate-700 dark:text-zinc-300 font-medium">Trace Demo</span>
            )}

            <span className="text-slate-400 dark:text-zinc-600">·</span>
            <span className="font-mono text-slate-500 dark:text-zinc-400 text-[11px]">
              {shortAddress(demo.address, 6, 4)}
            </span>

            {demo.summary?.hop_distance !== undefined && (
              <span className="px-1.5 py-0.2 rounded bg-slate-100 dark:bg-zinc-800 text-[10px] font-mono text-slate-600 dark:text-zinc-400">
                {demo.summary.hop_distance} hops
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
