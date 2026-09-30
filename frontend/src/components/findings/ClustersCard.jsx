import { useState } from 'react';
import { Building2, ChevronDown, ChevronUp } from 'lucide-react';
import { shortAddress } from '../../utils/formatters';

export default function ClustersCard({ clusters }) {
  const [expanded, setExpanded] = useState(false);

  if (!clusters || clusters.length === 0) return null;

  return (
    <div className="bg-white dark:bg-zinc-900/90 border border-slate-200 dark:border-zinc-800 rounded-2xl p-5 shadow-sm dark:shadow-xl transition-all space-y-3">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
          <h3 className="font-bold text-sm text-slate-900 dark:text-zinc-100">
            Resolved Entity Clusters ({clusters.length})
          </h3>
        </div>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-cyan-700 dark:text-cyan-400 hover:text-cyan-800 dark:hover:text-cyan-300 flex items-center gap-1 font-medium cursor-pointer"
        >
          <span>{expanded ? 'Hide Wallets' : 'View Wallets'}</span>
          {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Cluster Cards */}
      <div className="space-y-2">
        {clusters.map((cluster) => (
          <div
            key={cluster.cluster_id}
            className="bg-slate-50 dark:bg-zinc-950/80 border border-slate-200 dark:border-zinc-800 rounded-xl p-3.5 space-y-2"
          >
            <div className="flex items-center justify-between">
              <div>
                <span className="font-bold text-sm text-slate-900 dark:text-zinc-100 block">
                  {cluster.entity}
                </span>
                <span className="text-[11px] font-mono text-slate-500 dark:text-zinc-400">
                  {cluster.named ? 'Verified Entity Label' : 'Consolidation Hub Cluster'}
                </span>
              </div>

              <div className="text-right">
                <span className="text-xs font-mono font-semibold text-emerald-600 dark:text-emerald-400 block">
                  {cluster.hop_distance} Hops (Min)
                </span>
                <span className="text-[11px] text-slate-500 dark:text-zinc-400">
                  {cluster.member_count} {cluster.member_count === 1 ? 'wallet' : 'wallets'} touched
                </span>
              </div>
            </div>

            {/* Expanded Member Wallets */}
            {expanded && cluster.members && (
              <div className="pt-2 border-t border-slate-200 dark:border-zinc-800 space-y-1.5 animate-in fade-in duration-200">
                <span className="text-[10px] font-semibold text-slate-400 dark:text-zinc-500 uppercase tracking-wider block">
                  Constituent Member Wallets:
                </span>
                <div className="space-y-1 font-mono text-xs">
                  {cluster.members.map((addr) => (
                    <div
                      key={addr}
                      className="flex items-center justify-between px-2.5 py-1.5 rounded bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800/80 text-slate-700 dark:text-zinc-300"
                    >
                      <span>{shortAddress(addr, 10, 8)}</span>
                      {cluster.member_hops && cluster.member_hops[addr] !== undefined && (
                        <span className="text-[10px] text-slate-600 dark:text-zinc-400 bg-slate-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded font-semibold">
                          Hop {cluster.member_hops[addr]}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
