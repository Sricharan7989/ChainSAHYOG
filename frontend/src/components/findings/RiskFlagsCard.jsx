import { ShieldAlert, ShieldCheck, AlertOctagon, GitFork, Shuffle, ExternalLink } from 'lucide-react';
import { shortAddress, getRiskBadgeConfig, getExplorerUrl } from '../../utils/formatters';

export default function RiskFlagsCard({ riskFlags, explorerBase, labelCoverage }) {
  const hasFlags = Array.isArray(riskFlags) && riskFlags.length > 0;

  // THREE STATES, NOT TWO. A payload without `risk_flags` was never screened
  // (the recording predates the risk-label pass); an empty list means the
  // screen ran and matched no LABELLED risk entity. Neither is a "clean trail":
  // the screen can only recognise addresses in our label set, so on a chain
  // where we hold few or no labels an empty list says very little.
  if (!Array.isArray(riskFlags)) {
    return (
      <div className="bg-white dark:bg-[#111111] border border-[#d4d4d8] dark:border-[#262626] p-4 flex items-center gap-3 shadow-[2px_2px_0px_#18181b] dark:shadow-[2px_2px_0px_#000000]">
        <div className="w-8 h-8 bg-[#f4f4f5] dark:bg-[#1a1a1a] border border-[#d4d4d8] dark:border-[#262626] flex items-center justify-center text-[#71717a] shrink-0">
          <ShieldAlert className="w-4 h-4" />
        </div>
        <div className="space-y-0.5">
          <h4 className="font-bold text-xs text-[#09090b] dark:text-[#f5f5f5]">
            Risk Screening Not Performed
          </h4>
          <p className="text-[11px] text-[#52525b] dark:text-[#a3a3a3] leading-snug">
            This result carries no risk-label screen (the recording predates it), so
            nothing here says the trail avoided mixers or sanctioned addresses. Re-run
            the trace live to screen it.
          </p>
        </div>
      </div>
    );
  }

  if (!hasFlags) {
    const unlabelled = Object.entries(labelCoverage || {})
      .filter(([, info]) => info && !info.identification_possible)
      .map(([slug]) => slug);
    return (
      <div className="bg-white dark:bg-[#111111] border border-[#d4d4d8] dark:border-[#262626] p-4 transition-all flex items-center gap-3 shadow-[2px_2px_0px_#18181b] dark:shadow-[2px_2px_0px_#000000]">
        <div className="w-8 h-8 bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0">
          <ShieldCheck className="w-4 h-4" />
        </div>
        <div className="space-y-0.5">
          <h4 className="font-bold text-xs text-[#09090b] dark:text-[#f5f5f5]">
            No Labelled Risk Entities Met
          </h4>
          <p className="text-[11px] text-[#52525b] dark:text-[#a3a3a3] leading-snug">
            No address in our label set for mixers, bridges, scams or sanctions
            appeared anywhere in the traced graph. Only labelled addresses can be
            flagged, so an unlabelled mixer would not show here.
            {unlabelled.length > 0 &&
              ` We hold no labels for ${unlabelled.join(', ')}, so that part of the trace was effectively not screened.`}
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

              {/* Sanctions status, in one plain sentence: a current SDN listing, or
                  a past designation since removed ("... Not a current sanction."). */}
              {flag.sanctions_status && (
                <p
                  className={`text-[11px] leading-snug font-sans font-semibold px-1.5 py-1 border ${
                    flag.sanctions_status.includes('Not a current sanction')
                      ? 'border-amber-500/40 text-amber-700 dark:text-amber-400'
                      : 'border-red-500/40 text-red-700 dark:text-red-400'
                  }`}
                >
                  {flag.sanctions_status}
                </p>
              )}

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
