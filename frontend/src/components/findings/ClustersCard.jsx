import { useState } from 'react';
import { Building2, ChevronDown, ChevronUp, Scale, Shuffle, ArrowRightLeft, Ban } from 'lucide-react';
import { shortAddress } from '../../utils/formatters';

// Entity type -> how an investigator has to treat it.
//
// WHY THIS IS ON EACH ROW. An exchange wallet is a SUBPOENA TARGET: it holds
// KYC records and can be served a lawful request. A mixer is usually not
// actionable in that way, and a bridge is a handoff point whose operator may
// hold nothing about the person on either side. Listing all three under one
// heading invited exactly the wrong action being taken against a mixer.
const TYPE_META = {
  exchange: {
    label: 'Exchange',
    Icon: Building2,
    cls: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/40',
    action: 'Can be served a lawful request',
  },
  suspected_exchange: {
    label: 'Suspected Exchange',
    Icon: Building2,
    cls: 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/40',
    action: 'Unnamed; consolidation pattern only',
  },
  mixer: {
    label: 'Mixer',
    Icon: Shuffle,
    cls: 'bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/40',
    action: 'Obfuscation point; usually not a request target',
  },
  bridge: {
    label: 'Bridge',
    Icon: ArrowRightLeft,
    cls: 'bg-cyan-500/10 text-cyan-700 dark:text-cyan-300 border-cyan-500/40',
    action: 'Chain handoff; funds left this ledger',
  },
  sanctioned: {
    label: 'Sanctioned Entity',
    Icon: Ban,
    cls: 'bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/40',
    action: 'Sanctions status applies to this entity',
  },
};

export default function ClustersCard({ clusters }) {
  const [expanded, setExpanded] = useState(false);

  if (!clusters || clusters.length === 0) return null;

  // Group by entity type so the actionable entities are never buried among
  // handoff points. Order is operational, not alphabetical.
  const order = ['exchange', 'suspected_exchange', 'sanctioned', 'mixer', 'bridge'];
  const grouped = order
    .map((type) => ({ type, items: clusters.filter((c) => c.entity_type === type) }))
    .filter((group) => group.items.length > 0);
  const untyped = clusters.filter(
    (c) => !TYPE_META[c.entity_type] && !order.includes(c.entity_type)
  );
  if (untyped.length) grouped.push({ type: 'other', items: untyped });

  return (
    <div className="bg-white dark:bg-[#111111] border border-[#d4d4d8] dark:border-[#262626] p-4 sm:p-5 transition-all space-y-3 shadow-[3px_3px_0px_#18181b] dark:shadow-[3px_3px_0px_#000000]">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Scale className="w-4 h-4 text-[#627EEA]" />
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

      {/* Cluster Cards, grouped by operational type */}
      <div className="space-y-3">
        {grouped.map((group) => {
          const meta = TYPE_META[group.type];
          const Icon = meta?.Icon;
          return (
            <div key={group.type} className="space-y-1.5">
              {meta && (
                <div className="flex items-center gap-2">
                  <span
                    className={`px-1.5 py-0.5 border text-[9px] font-mono font-bold uppercase flex items-center gap-1 ${meta.cls}`}
                  >
                    {Icon && <Icon className="w-2.5 h-2.5" />}
                    {meta.label}
                  </span>
                  <span className="text-[10px] text-[#71717a] dark:text-[#888888]">
                    {meta.action}
                  </span>
                </div>
              )}
              {group.items.map((cluster) => (
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
          );
        })}
      </div>
    </div>
  );
}
