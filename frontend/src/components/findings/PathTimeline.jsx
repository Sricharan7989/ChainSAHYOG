import { ExternalLink, Copy, Check } from 'lucide-react';
import { useState } from 'react';
import {
  getTxUrl,
  formatNumber,
  splitNodeId,
  bareAddress,
  explorerUrlForNode,
  explorerForChain,
} from '../../utils/formatters';

/**
 * What the final step of the route actually is, in the same terms the headline's
 * Target tile uses. The last node used to be labelled "EXCHANGE (DESTINATION)"
 * whatever it was - an unconfirmed collection point and a mixer included.
 */
function endpointLabel(summary) {
  const reason = summary?.termination?.reason;
  if (summary?.found) return `${summary.exchange || 'Named exchange'} (named exchange)`;
  if (summary?.lead) return 'Unnamed collection point (unconfirmed)';
  if (reason === 'terminated_at_mixer') return 'Mixer (trail broken here)';
  if (reason === 'terminated_at_bridge') return 'Bridge (funds left this chain)';
  return 'Endpoint';
}

/**
 * The money on one edge: the suspect-attributable share under FIFO where the
 * replay computed one, otherwise the gross amount, labelled as such. A route
 * reads as "this much of the suspect's money moved here", not as every
 * transfer that happened to share the edge.
 */
function edgeMoney(edge) {
  const assets = Array.isArray(edge.assets) && edge.assets.length > 0
    ? edge.assets
    : [{ asset: edge.asset || '', value: edge.value }];
  const computed = assets.some((a) => typeof a.tainted_value === 'number');
  return {
    computed,
    rows: assets.map((a) => ({
      asset: a.asset,
      gross: Number(a.value) || 0,
      tainted: typeof a.tainted_value === 'number' ? a.tainted_value : null,
    })),
  };
}

export default function PathTimeline({ pathEdges, startAddress, summary, explorerBase, onSelectAddress }) {
  const [copiedAddr, setCopiedAddr] = useState(null);

  // No route to draw. Said, not left as a blank tab: either nothing was
  // recognised, or the endpoint is the suspect wallet itself.
  if (!pathEdges || pathEdges.length === 0) {
    const hasEndpoint = typeof summary?.hop_distance === 'number';
    return (
      <div className="bg-white dark:bg-[#111111] border border-[#d4d4d8] dark:border-[#262626] p-4 sm:p-5 shadow-[3px_3px_0px_#18181b] dark:shadow-[3px_3px_0px_#000000] space-y-1.5">
        <h3 className="font-bold text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5]">
          Money Trail
        </h3>
        <p className="text-xs text-[#52525b] dark:text-[#a3a3a3] leading-relaxed">
          {hasEndpoint
            ? 'The endpoint could not be connected to the suspect wallet by a route in the graph, so no hop-by-hop trail is shown.'
            : 'There is no route to show: the trace did not reach an exchange, collection point, mixer or bridge. The Case Summary tab says why the trace stopped.'}
        </p>
      </div>
    );
  }

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
                  href={explorerUrlForNode(explorerBase, startAddress)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[#71717a] hover:text-[#627EEA] flex items-center gap-1"
                  title="View on Explorer"
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

          // A chain crossing is shown as its own step, styled apart from a
          // transfer, and says out loud that it is an inference. Reading this
          // trail as a list of transactions would be the easiest way for a
          // reader to over-trust the route.
          const isCrossing = edge.edge_type === 'cross_chain';
          const handoff = edge.handoff || null;
          const { chain: toChain } = splitNodeId(recipient);
          const bareRecipient = bareAddress(recipient);
          const crossedTo = edge.to_chain || toChain;
          const entity =
            handoff?.deposit?.entity || handoff?.bridge?.entity || 'a bridge';

          return (
            <div key={idx} className="relative flex items-start gap-3">
              <div
                className={`absolute -left-6 top-1 w-3.5 h-3.5 ring-4 ring-white dark:ring-[#111111] ${
                  isFinal
                    ? 'bg-emerald-500'
                    : isCrossing
                      ? 'bg-cyan-400'
                      : 'bg-[#627EEA]'
                }`}
              />
              <div
                className={`p-3 flex-1 text-xs border space-y-1 ${
                  isFinal
                    ? 'bg-emerald-500/5 dark:bg-emerald-950/20 border-emerald-500/50'
                    : isCrossing
                      ? 'bg-cyan-500/5 dark:bg-cyan-950/20 border-cyan-500/60 border-dashed'
                      : 'bg-[#f4f4f5] dark:bg-[#0a0a0a] border-[#d4d4d8] dark:border-[#262626]'
                }`}
              >
                <div className="flex justify-between items-center mb-0.5">
                  <span
                    className={`font-bold font-mono text-[11px] uppercase tracking-wider ${
                      isFinal
                        ? 'text-emerald-700 dark:text-emerald-400'
                        : isCrossing
                          ? 'text-cyan-700 dark:text-cyan-300'
                          : 'text-[#627EEA]'
                    }`}
                  >
                    Hop {hopNumber} ·{' '}
                    {isFinal
                      ? endpointLabel(summary).toUpperCase()
                      : isCrossing
                        ? `CROSSED TO ${(crossedTo || '').toUpperCase()}`
                        : 'INTERMEDIARY CONDUIT'}
                  </span>

                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => handleCopy(bareRecipient)}
                      className="text-[#71717a] hover:text-[#627EEA] transition-colors p-0.5"
                      title="Copy address"
                    >
                      {copiedAddr === bareRecipient ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                    </button>
                    {edge.tx_hash && (
                      <a
                        href={getTxUrl(
                          explorerForChain(crossedTo, explorerBase),
                          edge.tx_hash
                        )}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#71717a] hover:text-[#627EEA] flex items-center gap-1 text-[11px] font-mono"
                        title="View Transaction Hash on Explorer"
                      >
                        <span>Tx</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                    <a
                      href={explorerUrlForNode(explorerBase, recipient)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[#71717a] hover:text-[#627EEA] flex items-center gap-1"
                      title="View on Explorer"
                    >
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => onSelectAddress?.(recipient)}
                  className="font-mono text-[#09090b] dark:text-[#f5f5f5] hover:text-[#627EEA] transition-colors break-all text-left block cursor-pointer font-medium"
                >
                  {bareRecipient}
                </button>

                {/* Chain Crossing Explanation */}
                {isCrossing && (
                  <div className="text-[11px] text-cyan-800 dark:text-cyan-200 pt-1 space-y-1">
                    <p>
                      Crossed to {crossedTo} via {entity}
                      {handoff?.confidence_score != null && (
                        <>
                          {' '}
                          — matched{' '}
                          <strong>{handoff.confidence_score}/100</strong> on amount
                          and timing
                        </>
                      )}
                      .
                    </p>
                    <p className="text-cyan-700/80 dark:text-cyan-300/70 italic">
                      Inferred, not observed. The deposit is on record; the arrival
                      of the same value on {crossedTo} is matched by amount, time
                      and recipient address.
                    </p>
                    {handoff?.reason && (
                      <p className="text-cyan-700/80 dark:text-cyan-300/70">
                        {handoff.reason}
                      </p>
                    )}
                  </div>
                )}

                {/* Value on this leg: the suspect's share under FIFO, with the gross
                    amount beside it for context. Gross only, and labelled so,
                    where no FIFO figure exists for this edge. */}
                {(() => {
                  const money = edgeMoney(edge);
                  return (
                    <div className="flex flex-col gap-0.5 text-[11px] text-[#52525b] dark:text-[#a3a3a3] pt-1 border-t border-[#d4d4d8] dark:border-[#262626]">
                      {money.rows.map((row) => (
                        <span key={row.asset}>
                          {money.computed ? (
                            <>
                              Suspect funds (FIFO):{' '}
                              <strong className="text-[#09090b] dark:text-[#f5f5f5]">
                                {formatNumber(row.tainted ?? 0, 4)} {row.asset}
                              </strong>{' '}
                              <span className="text-[#71717a] dark:text-[#666666]">
                                of {formatNumber(row.gross, 4)} {row.asset} moved on this leg
                              </span>
                            </>
                          ) : (
                            <>
                              Moved on this leg (gross, not attributed):{' '}
                              <strong className="text-[#09090b] dark:text-[#f5f5f5]">
                                {formatNumber(row.gross, 4)} {row.asset}
                              </strong>
                            </>
                          )}
                        </span>
                      ))}
                      {edge.tx_count && edge.tx_count > 1 && (
                        <span className="text-[#71717a] dark:text-[#666666]">
                          ({edge.tx_count} transfers aggregated)
                        </span>
                      )}
                    </div>
                  );
                })()}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
