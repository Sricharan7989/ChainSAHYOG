import { PlayCircle, ShieldCheck, AlertOctagon } from 'lucide-react';
import { shortAddress } from '../utils/formatters';

export default function DemoChips({ demos, onSelectDemo, selectedAddress, loading }) {
  if (!demos || demos.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2.5 pt-0.5 pb-1">
      <span className="text-[11px] font-mono text-[#71717a] dark:text-[#a3a3a3] flex items-center gap-1.5 uppercase tracking-wider font-bold shrink-0">
        <PlayCircle className="w-3.5 h-3.5 text-[#627EEA]" />
        <span>Demo Presets:</span>
      </span>

      <div className="flex flex-wrap items-center gap-2">
        {demos.map((demo) => {
          const isSelected = selectedAddress?.toLowerCase() === demo.address?.toLowerCase();
          const exchangeName = demo.exchange || demo.summary?.exchange;
          const hopCount = demo.hop_distance ?? demo.summary?.hop_distance;
          const isSanctioned =
            demo.headline?.toLowerCase().includes('sanction') ||
            demo.summary?.risk_flags?.some(
              (f) => f.severity === 'critical' || f.risk_type === 'sanctioned'
            );

          return (
            <button
              key={demo.address}
              type="button"
              disabled={loading}
              onClick={() => onSelectDemo(demo)}
              className={`text-xs px-3 py-1.5 border transition-all flex items-center gap-2 cursor-pointer brutal-press shrink-0 ${
                isSelected
                  ? 'bg-[#627EEA]/20 text-[#627EEA] border-[#627EEA] shadow-[2px_2px_0px_#627EEA] font-bold'
                  : 'bg-white dark:bg-[#1c1c22] hover:bg-[#f4f4f5] dark:hover:bg-[#272730] text-[#09090b] dark:text-[#f5f5f5] border-[#18181b] dark:border-[#383842] shadow-[2px_2px_0px_#18181b] dark:shadow-[2px_2px_0px_#000000] hover:border-[#627EEA]'
              }`}
            >
              {exchangeName ? (
                <span className="flex items-center gap-1 text-emerald-700 dark:text-emerald-400 font-bold bg-emerald-500/15 px-1.5 py-0.5 border border-emerald-500/40 text-[11px]">
                  <ShieldCheck className="w-3 h-3" />
                  <span>{exchangeName}</span>
                </span>
              ) : isSanctioned ? (
                <span className="flex items-center gap-1 text-red-600 dark:text-red-400 font-bold bg-red-500/15 px-1.5 py-0.5 border border-red-500/40 text-[11px]">
                  <AlertOctagon className="w-3 h-3" />
                  <span>Sanctioned Entity</span>
                </span>
              ) : (
                <span className="text-[#09090b] dark:text-[#f5f5f5] font-semibold text-[11px]">
                  Replay Trace
                </span>
              )}

              <span className="font-mono text-[#3f3f46] dark:text-[#d4d4d8] text-[11px] font-medium">
                {shortAddress(demo.address, 6, 4)}
              </span>

              {hopCount !== undefined && (
                <span className="px-1.5 py-0.5 bg-[#f4f4f5] dark:bg-[#272730] text-[10px] font-mono text-[#52525b] dark:text-[#e4e4e7] border border-[#d4d4d8] dark:border-[#3f3f46] font-semibold">
                  {hopCount} hops
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
