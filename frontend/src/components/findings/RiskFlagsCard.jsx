import { ShieldAlert, ShieldCheck, AlertOctagon, GitFork, Shuffle, ExternalLink } from 'lucide-react';
import { shortAddress, getRiskBadgeConfig, getExplorerUrl } from '../../utils/formatters';

export default function RiskFlagsCard({ riskFlags, explorerBase }) {
  const hasFlags = riskFlags && riskFlags.length > 0;

  if (!hasFlags) {
    return (
      <div className="bg-white dark:bg-[#111111] border border-[#d4d4d8] dark:border-[#262626] p-4 transition-all flex items-center gap-3 shadow-[2px_2px_0px_#18181b] dark:shadow-[2px_2px_0px_#000000]">
        <div className="w-8 h-8 bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0">
          <ShieldCheck className="w-4 h-4" />
        </div>
        <div className="space-y-0.5">
          <h4 className="font-bold text-xs text-[#09090b] dark:text-[#f5f5f5]">
            Clean Forward Money Trail
          </h4>
          <p className="text-[11px] text-[#52525b] dark:text-[#a3a3a3] leading-snug">
            No privacy mixers, tumblers, or blacklisted addresses were encountered between the suspect and the exchange.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-[#111111] border border-[#d4d4d8] dark:border-[#262626] p-4 sm:p-5 transition-all space-y-3 shadow-[3px_3px_0px_#18181b] dark:shadow-[3px_3px_0px_#000000]">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-red-500" />
          <h3 className="font-bold text-sm text-[#09090b] dark:text-[#f5f5f5]">
            Trail Warnings ({riskFlags.length})
          </h3>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20 font-semibold uppercase">
          Enforcement Flags
        </span>
      </div>

      <div className="space-y-2">
        {riskFlags.map((flag, idx) => {
          const badge = getRiskBadgeConfig(flag.severity);
          const isSanctioned = flag.risk_type === 'sanctioned';
          const isMixer = flag.risk_type === 'mixer';

          return (
            <div
              key={idx}
              className={`p-3 border space-y-1.5 transition-colors ${
                flag.on_primary_path
                  ? 'bg-red-500/10 dark:bg-red-950/20 border-red-500/40'
                  : 'bg-[#f4f4f5] dark:bg-[#0a0a0a] border-[#d4d4d8] dark:border-[#262626]'
              }`}
            >
              {/* Top row: Type + Severity + Primary Path Badge */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  {isSanctioned ? (
                    <AlertOctagon className="w-4 h-4 text-red-500 shrink-0" />
                  ) : isMixer ? (
                    <Shuffle className="w-4 h-4 text-amber-500 shrink-0" />
                  ) : (
                    <GitFork className="w-4 h-4 text-violet-500 shrink-0" />
                  )}
                  <span className="font-bold text-xs text-[#09090b] dark:text-[#f5f5f5]">
                    {flag.entity || 'Flagged Entity'}
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  {flag.on_primary_path && (
                    <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 bg-red-500/20 text-red-700 dark:text-red-400 border border-red-500/30">
                      ON TRAIL
                    </span>
                  )}
                  <span
                    className={`text-[10px] font-mono font-bold px-1.5 py-0.5 border ${badge.bg}`}
                  >
                    {badge.label}
                  </span>
                </div>
              </div>

              {/* Address + Hop */}
              <div className="flex items-center justify-between text-xs font-mono text-[#52525b] dark:text-[#a3a3a3]">
                <a
                  href={getExplorerUrl(explorerBase, flag.address)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-[#627EEA] flex items-center gap-1 font-semibold"
                >
                  <span>{shortAddress(flag.address, 8, 6)}</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
                <span className="text-[11px] text-[#71717a] dark:text-[#666666]">
                  {flag.hop_distance} {flag.hop_distance === 1 ? 'hop' : 'hops'} out
                </span>
              </div>

              {/* Note */}
              {flag.note && (
                <p className="text-[11px] text-[#52525b] dark:text-[#a3a3a3] leading-snug pt-0.5 font-sans">
                  {flag.note}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
