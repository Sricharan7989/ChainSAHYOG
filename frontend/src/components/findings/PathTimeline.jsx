import { ExternalLink, Copy, Check } from 'lucide-react';
import { useState } from 'react';
import { getExplorerUrl, getTxUrl } from '../../utils/formatters';

export default function PathTimeline({ pathEdges, startAddress, summary, explorerBase, onSelectAddress }) {
  const [copiedAddr, setCopiedAddr] = useState(null);

  if (!pathEdges || pathEdges.length === 0) return null;

  const handleCopy = (addr) => {
    navigator.clipboard.writeText(addr);
    setCopiedAddr(addr);
    setTimeout(() => setCopiedAddr(null), 2000);
  };

  return (
    <div className="bg-white dark:bg-[#111111] border border-[#d4d4d8] dark:border-[#262626] p-4 sm:p-5 transition-all space-y-4 shadow-[3px_3px_0px_#18181b] dark:shadow-[3px_3px_0px_#000000]">
      {/* Title */}
      <div className="flex items-center justify-between">
        <h3 className="font-bold text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5] flex items-center gap-2">
          <span>Chronological Money Trail</span>
          <span className="font-mono text-xs text-[#627EEA] font-semibold">
            ({pathEdges.length} {pathEdges.length === 1 ? 'hop' : 'hops'})
          </span>
        </h3>
        <span className="text-[10px] font-mono text-[#71717a] dark:text-[#888888] uppercase">
          Shortest BFS Route
        </span>
      </div>

      <div className="relative pl-6 space-y-4 pt-1">
        {/* Continuous vertical timeline connector line */}
        <div className="absolute left-[11px] top-3 bottom-3 w-0.5 bg-[#d4d4d8] dark:bg-[#404040]" />

        {/* Step 0: Suspect Wallet */}
        <div className="relative flex items-start gap-3">
          <div className="absolute -left-6 top-1 w-3.5 h-3.5 bg-red-500 ring-4 ring-white dark:ring-[#111111] flex items-center justify-center" />
          <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] p-3 flex-1 text-xs space-y-1">
            <div className="flex justify-between items-center mb-0.5">
              <span className="font-bold text-red-600 dark:text-red-400 font-mono text-[11px] uppercase tracking-wider">
                Hop 0 · SUSPECT ORIGIN
              </span>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => handleCopy(startAddress)}
                  className="text-[#71717a] hover:text-[#627EEA] transition-colors p-0.5"
                  title="Copy address"
                >
                  {copiedAddr === startAddress ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                </button>
                <a
                  href={getExplorerUrl(explorerBase, startAddress)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[#71717a] hover:text-[#627EEA] flex items-center gap-1"
                  title="View on Etherscan"
                >
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
            <button
              type="button"
              onClick={() => onSelectAddress?.(startAddress)}
              className="font-mono text-[#09090b] dark:text-[#f5f5f5] hover:text-[#627EEA] transition-colors break-all text-left cursor-pointer font-medium block"
            >
              {startAddress}
            </button>
            <span className="text-[10px] text-[#71717a] dark:text-[#888888] font-mono block">
              Initial complaint wallet address
            </span>
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
                className={`absolute -left-6 top-1 w-3.5 h-3.5 ring-4 ring-white dark:ring-[#111111] ${
                  isFinal ? 'bg-emerald-500' : 'bg-[#627EEA]'
                }`}
              />
              <div
                className={`p-3 flex-1 text-xs border space-y-1 ${
                  isFinal
                    ? 'bg-emerald-500/5 dark:bg-emerald-950/20 border-emerald-500/50'
                    : 'bg-[#f4f4f5] dark:bg-[#0a0a0a] border-[#d4d4d8] dark:border-[#262626]'
                }`}
              >
                <div className="flex justify-between items-center mb-0.5">
                  <span
                    className={`font-bold font-mono text-[11px] uppercase tracking-wider ${
                      isFinal ? 'text-emerald-700 dark:text-emerald-400' : 'text-[#627EEA]'
                    }`}
                  >
                    Hop {hopNumber} ·{' '}
                    {isFinal
                      ? `${summary?.exchange || 'EXCHANGE'} (DESTINATION)`
                      : 'INTERMEDIARY CONDUIT'}
                  </span>

                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => handleCopy(recipient)}
                      className="text-[#71717a] hover:text-[#627EEA] transition-colors p-0.5"
                      title="Copy address"
                    >
                      {copiedAddr === recipient ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                    </button>
                    {edge.tx_hash && (
                      <a
                        href={getTxUrl(explorerBase, edge.tx_hash)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#71717a] hover:text-[#627EEA] flex items-center gap-1 text-[11px] font-mono"
                        title="View Transaction Hash on Explorer"
                      >
                        <span>Tx</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => onSelectAddress?.(recipient)}
                  className="font-mono text-[#09090b] dark:text-[#f5f5f5] hover:text-[#627EEA] transition-colors break-all text-left block cursor-pointer font-medium"
                >
                  {recipient}
                </button>

                {/* Transfer Value Info */}
                <div className="flex flex-wrap items-center gap-2 text-[11px] text-[#52525b] dark:text-[#a3a3a3] pt-1 border-t border-[#d4d4d8] dark:border-[#262626]">
                  <span>
                    Forwarded: <strong className="text-[#09090b] dark:text-[#f5f5f5]">{edge.value} {edge.asset || 'ETH'}</strong>
                  </span>
                  {edge.tx_count && edge.tx_count > 1 && (
                    <span className="text-[#71717a] dark:text-[#666666]">
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
