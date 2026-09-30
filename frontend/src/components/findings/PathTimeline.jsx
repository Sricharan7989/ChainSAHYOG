import { ExternalLink } from 'lucide-react';
import { shortAddress, getExplorerUrl, getTxUrl } from '../../utils/formatters';

export default function PathTimeline({ pathEdges, startAddress, summary, explorerBase, onSelectAddress }) {
  if (!pathEdges || pathEdges.length === 0) return null;

  return (
    <div className="bg-white dark:bg-zinc-900/90 border border-slate-200 dark:border-zinc-800 rounded-2xl p-5 shadow-sm dark:shadow-xl transition-all space-y-3">
      {/* Title */}
      <div className="flex items-center justify-between">
        <h3 className="font-bold text-sm text-slate-900 dark:text-zinc-100 flex items-center gap-2">
          <span>Traced Money Trail</span>
          <span className="font-mono text-xs text-cyan-600 dark:text-cyan-400 font-normal">
            ({pathEdges.length} {pathEdges.length === 1 ? 'hop' : 'hops'})
          </span>
        </h3>
        <span className="text-[10px] font-mono text-slate-400 dark:text-zinc-500 uppercase">
          Shortest BFS Route
        </span>
      </div>

      <div className="relative pl-6 space-y-4 pt-1">
        {/* Continuous vertical timeline connector line */}
        <div className="absolute left-[11px] top-3 bottom-3 w-0.5 bg-gradient-to-b from-red-500 via-cyan-500 to-emerald-500 rounded-full" />

        {/* Step 0: Suspect Wallet */}
        <div className="relative flex items-start gap-3">
          <div className="absolute -left-6 top-1 w-3.5 h-3.5 rounded-full bg-red-500 ring-4 ring-white dark:ring-zinc-950 flex items-center justify-center" />
          <div className="bg-slate-50 dark:bg-zinc-950/80 border border-slate-200 dark:border-zinc-800 rounded-xl p-3 flex-1 text-xs">
            <div className="flex justify-between items-center mb-1">
              <span className="font-bold text-red-600 dark:text-red-400 font-mono">Hop 0 · SUSPECT ORIGIN</span>
              <a
                href={getExplorerUrl(explorerBase, startAddress)}
                target="_blank"
                rel="noopener noreferrer"
                className="text-slate-400 dark:text-zinc-500 hover:text-cyan-600 dark:hover:text-cyan-400 flex items-center gap-1"
              >
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <button
              type="button"
              onClick={() => onSelectAddress?.(startAddress)}
              className="font-mono text-slate-800 dark:text-zinc-200 hover:text-cyan-600 dark:hover:text-cyan-300 transition-colors break-all text-left cursor-pointer"
            >
              {startAddress}
            </button>
          </div>
        </div>

        {/* Intermediate Hops & Destination */}
        {pathEdges.map((edge, idx) => {
          const isFinal = idx === pathEdges.length - 1;
          const hopNumber = idx + 1;
          const recipient = edge.target;

          return (
            <div key={idx} className="relative flex items-start gap-3">
              <div
                className={`absolute -left-6 top-1 w-3.5 h-3.5 rounded-full ring-4 ring-white dark:ring-zinc-950 ${
                  isFinal ? 'bg-emerald-500 ring-emerald-100 dark:ring-emerald-950' : 'bg-cyan-500 ring-white dark:ring-zinc-950'
                }`}
              />
              <div
                className={`rounded-xl p-3 flex-1 text-xs border ${
                  isFinal
                    ? 'bg-emerald-50/70 dark:bg-emerald-950/20 border-emerald-300 dark:border-emerald-500/40'
                    : 'bg-slate-50 dark:bg-zinc-950/80 border-slate-200 dark:border-zinc-800'
                }`}
              >
                <div className="flex justify-between items-center mb-1">
                  <span
                    className={`font-bold font-mono ${
                      isFinal ? 'text-emerald-700 dark:text-emerald-400' : 'text-cyan-700 dark:text-cyan-400'
                    }`}
                  >
                    Hop {hopNumber} ·{' '}
                    {isFinal
                      ? summary?.exchange || 'VASP ENDPOINT'
                      : 'INTERMEDIARY CONDUIT'}
                  </span>

                  {edge.tx_hash && (
                    <a
                      href={getTxUrl(explorerBase, edge.tx_hash)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-slate-500 dark:text-zinc-400 hover:text-cyan-600 dark:hover:text-cyan-400 flex items-center gap-1 text-[11px] font-mono"
                      title="View Transaction Hash on Explorer"
                    >
                      <span>Tx: {shortAddress(edge.tx_hash, 4, 4)}</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => onSelectAddress?.(recipient)}
                  className="font-mono text-slate-800 dark:text-zinc-200 hover:text-cyan-600 dark:hover:text-cyan-300 transition-colors break-all text-left block mb-1.5 cursor-pointer"
                >
                  {recipient}
                </button>

                {/* Transfer Value Info */}
                <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-600 dark:text-zinc-400 pt-1 border-t border-slate-200 dark:border-zinc-800/80">
                  <span>
                    Forwarded: <strong className="text-slate-900 dark:text-zinc-200">{edge.value} {edge.asset || 'ETH'}</strong>
                  </span>
                  {edge.tx_count && edge.tx_count > 1 && (
                    <span className="text-slate-400 dark:text-zinc-500">
                      ({edge.tx_count} transfers aggregated)
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
