import { ShieldAlert, AlertOctagon, GitFork, Shuffle, ExternalLink } from 'lucide-react';
import { shortAddress, getRiskBadgeConfig, getExplorerUrl } from '../../utils/formatters';

export default function RiskFlagsCard({ riskFlags, explorerBase }) {
  if (!riskFlags || riskFlags.length === 0) return null;

  return (
    <div className="bg-white dark:bg-zinc-900/90 border border-slate-200 dark:border-zinc-800 rounded-2xl p-5 shadow-sm dark:shadow-xl transition-all space-y-3">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-red-500" />
          <h3 className="font-bold text-sm text-slate-900 dark:text-zinc-100">
            Critical Risk & Sanction Flags ({riskFlags.length})
          </h3>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-red-100 dark:bg-red-500/10 text-red-700 dark:text-red-400 border border-red-300 dark:border-red-500/20 font-semibold">
          OFAC / Obfuscators
        </span>
      </div>

      <div className="space-y-2.5">
        {riskFlags.map((flag, idx) => {
          const badge = getRiskBadgeConfig(flag.severity);
          const isSanctioned = flag.risk_type === 'sanctioned';
          const isMixer = flag.risk_type === 'mixer';

          return (
            <div
              key={idx}
              className={`p-3 rounded-xl border space-y-1.5 transition-colors ${
                flag.on_primary_path
                  ? 'bg-red-50 dark:bg-red-950/20 border-red-300 dark:border-red-500/40 ring-1 ring-red-400/20'
                  : 'bg-slate-50 dark:bg-zinc-950/80 border-slate-200 dark:border-zinc-800'
              }`}
            >
              {/* Top row: Type + Severity + Primary Path Badge */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  {isSanctioned ? (
                    <AlertOctagon className="w-4 h-4 text-red-500" />
                  ) : isMixer ? (
                    <Shuffle className="w-4 h-4 text-amber-500" />
                  ) : (
                    <GitFork className="w-4 h-4 text-purple-500" />
                  )}
                  <span className="font-bold text-xs text-slate-900 dark:text-zinc-100">
                    {flag.entity || 'Unknown Risky Entity'}
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  {flag.on_primary_path && (
                    <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400 border border-red-300 dark:border-red-500/30">
                      ON MONEY TRAIL
                    </span>
                  )}
                  <span
                    className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded border ${badge.bg}`}
                  >
                    {badge.label}
                  </span>
                </div>
              </div>

              {/* Address + Hop */}
              <div className="flex items-center justify-between text-xs font-mono text-slate-600 dark:text-zinc-400">
                <a
                  href={getExplorerUrl(explorerBase, flag.address)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-cyan-600 dark:hover:text-cyan-400 flex items-center gap-1 font-semibold"
                >
                  <span>{shortAddress(flag.address, 8, 6)}</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
                <span className="text-[11px] text-slate-500 dark:text-zinc-500">
                  {flag.hop_distance} {flag.hop_distance === 1 ? 'hop' : 'hops'} out
                </span>
              </div>

              {/* Note */}
              {flag.note && (
                <p className="text-[11px] text-slate-600 dark:text-zinc-400 leading-snug pt-0.5 font-sans">
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
