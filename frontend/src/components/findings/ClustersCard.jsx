import { useState } from 'react';
import { Building2, ChevronDown, ChevronUp } from 'lucide-react';
import { shortAddress } from '../../utils/formatters';

export default function ClustersCard({ clusters }) {
  const [expanded, setExpanded] = useState(false);

  if (!clusters || clusters.length === 0) return null;

  return (
    <div className="bg-white dark:bg-[#111111] border border-[#d4d4d8] dark:border-[#262626] p-4 sm:p-5 transition-all space-y-3 shadow-[3px_3px_0px_#18181b] dark:shadow-[3px_3px_0px_#000000]">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-[#627EEA]" />
          <h3 className="font-bold text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5]">
            Resolved Entity Clusters ({clusters.length})
          </h3>
        </div>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="text-xs font-mono text-[#627EEA] hover:text-[#5068cf] flex items-center gap-1 font-semibold cursor-pointer"
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
            className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] p-3 space-y-2"
          >
            <div className="flex items-center justify-between">
              <div>
                <span className="font-bold text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5] block">
                  {cluster.entity}
                </span>
                <span className="text-[11px] font-mono text-[#52525b] dark:text-[#a3a3a3]">
                  {cluster.named ? 'Verified Entity Label' : 'Consolidation Hub Cluster'}
                </span>
              </div>

              <div className="text-right">
                <span className="text-xs font-mono font-semibold text-emerald-700 dark:text-emerald-400 block">
                  {cluster.hop_distance} Hops (Min)
                </span>
                <span className="text-[10px] text-[#71717a] dark:text-[#888888]">
                  {cluster.member_count} {cluster.member_count === 1 ? 'wallet' : 'wallets'} touched
                </span>
              </div>
            </div>

            {/* Expanded Member Wallets */}
            {expanded && cluster.members && (
              <div className="pt-2 border-t border-[#d4d4d8] dark:border-[#262626] space-y-1.5 animate-in fade-in duration-150">
                <span className="text-[10px] font-semibold text-[#71717a] dark:text-[#666666] uppercase tracking-wider block">
                  Constituent Member Wallets:
                </span>
                <div className="space-y-1 font-mono text-xs">
                  {cluster.members.map((addr) => (
                    <div
                      key={addr}
                      className="flex items-center justify-between px-2 py-1.5 bg-white dark:bg-[#111111] border border-[#d4d4d8] dark:border-[#262626] text-[#09090b] dark:text-[#f5f5f5]"
                    >
                      <span>{shortAddress(addr, 10, 8)}</span>
                      {cluster.member_hops && cluster.member_hops[addr] !== undefined && (
                        <span className="text-[10px] text-[#52525b] dark:text-[#a3a3a3] bg-[#f4f4f5] dark:bg-[#1a1a1a] px-1.5 py-0.5 font-semibold">
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
