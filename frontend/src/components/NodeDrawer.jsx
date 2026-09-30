import { useRef, useState } from 'react';
import { X, ExternalLink, Copy, Check, Shield, Coins } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { shortAddress, formatAssets, getExplorerUrl, getTxUrl } from '../utils/formatters';

gsap.registerPlugin(useGSAP);

export default function NodeDrawer({ selectedNode, selectedEdge, onClose, explorerBase }) {
  const drawerRef = useRef(null);
  const [copied, setCopied] = useState(false);

  useGSAP(() => {
    if (selectedNode || selectedEdge) {
      gsap.fromTo(
        drawerRef.current,
        { x: 300, opacity: 0 },
        { x: 0, opacity: 1, duration: 0.35, ease: 'power3.out' }
      );
    }
  }, { dependencies: [selectedNode, selectedEdge], scope: drawerRef });

  if (!selectedNode && !selectedEdge) return null;

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      ref={drawerRef}
      className="absolute top-4 right-4 z-30 w-80 sm:w-96 bg-white/95 dark:bg-zinc-900/95 border border-slate-200 dark:border-zinc-700/80 rounded-2xl shadow-xl dark:shadow-2xl backdrop-blur-xl p-5 overflow-y-auto max-h-[85vh] text-slate-800 dark:text-zinc-100"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-zinc-800 pb-3 mb-4">
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
          <h3 className="font-semibold text-sm text-slate-900 dark:text-zinc-200">
            {selectedNode ? 'Wallet Forensics' : 'Transaction Hop'}
          </h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1 text-slate-400 dark:text-zinc-400 hover:text-slate-700 dark:hover:text-zinc-200 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-md transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* NODE DETAILS */}
      {selectedNode && (
        <div className="space-y-4">
          {/* Identity Tag */}
          <div>
            <span className="text-[11px] text-slate-500 dark:text-zinc-500 uppercase tracking-wider font-semibold block mb-1">
              Entity Role
            </span>
            <div className="flex items-center gap-2">
              <span
                className={`px-2.5 py-1 rounded-md text-xs font-semibold ${
                  selectedNode.is_start
                    ? 'bg-red-500/20 text-red-600 dark:text-red-400 border border-red-500/30'
                    : selectedNode.is_vasp
                    ? 'bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30'
                    : selectedNode.entity_type === 'suspected_exchange'
                    ? 'bg-emerald-100 dark:bg-emerald-800/40 text-emerald-800 dark:text-emerald-300 border border-emerald-500/40 border-dashed'
                    : selectedNode.is_mixer
                    ? 'bg-amber-500/20 text-amber-600 dark:text-amber-400 border border-amber-500/30'
                    : selectedNode.is_bridge
                    ? 'bg-purple-500/20 text-purple-600 dark:text-purple-400 border border-purple-500/30'
                    : 'bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 border border-slate-200 dark:border-zinc-700'
                }`}
              >
                {selectedNode.is_start
                  ? 'SUSPECT ORIGIN'
                  : selectedNode.label ||
                    (selectedNode.entity_type === 'suspected_exchange'
                      ? 'SUSPECTED COLLECTION HUB'
                      : 'UNHOSTED WALLET')}
              </span>
              {selectedNode.depth !== undefined && (
                <span className="text-xs font-mono text-slate-600 dark:text-zinc-400 bg-slate-100 dark:bg-zinc-800 px-2 py-0.5 rounded border border-slate-200 dark:border-zinc-700">
                  Hop {selectedNode.depth}
                </span>
              )}
            </div>
          </div>

          {/* Full Address */}
          <div>
            <span className="text-[11px] text-slate-500 dark:text-zinc-500 uppercase tracking-wider font-semibold block mb-1">
              Address
            </span>
            <div className="flex items-center justify-between bg-slate-50 dark:bg-zinc-950 p-2.5 rounded-lg border border-slate-200 dark:border-zinc-800 font-mono text-xs">
              <span className="text-cyan-700 dark:text-cyan-300 break-all">{selectedNode.id}</span>
              <button
                type="button"
                onClick={() => handleCopy(selectedNode.id)}
                className="p-1 ml-2 text-slate-400 dark:text-zinc-400 hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors cursor-pointer"
                title="Copy Address"
              >
                {copied ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Tainted Value Received */}
          {selectedNode.tainted_in && Object.keys(selectedNode.tainted_in).length > 0 && (
            <div className="bg-cyan-50/70 dark:bg-cyan-950/20 border border-cyan-200 dark:border-cyan-500/30 rounded-xl p-3">
              <span className="text-[11px] text-cyan-700 dark:text-cyan-400 uppercase tracking-wider font-semibold flex items-center gap-1.5 mb-1">
                <Coins className="w-3.5 h-3.5" />
                Tainted Value Reached Here
              </span>
              <p className="font-mono text-sm font-semibold text-slate-900 dark:text-zinc-100">
                {formatAssets(selectedNode.tainted_in)}
              </p>
              <p className="text-[10px] text-slate-500 dark:text-zinc-400 mt-1">
                Calculated strictly via chronological FIFO accounting
              </p>
            </div>
          )}

          {/* Explorer Button */}
          <a
            href={getExplorerUrl(explorerBase, selectedNode.id)}
            target="_blank"
            rel="noopener noreferrer"
            className="w-full mt-2 py-2 px-3 rounded-lg bg-slate-100 dark:bg-zinc-800 hover:bg-slate-200 dark:hover:bg-zinc-700 text-xs font-medium text-slate-700 dark:text-zinc-200 flex items-center justify-center gap-2 border border-slate-200 dark:border-zinc-700 transition-colors cursor-pointer"
          >
            <span>View on Blockchain Explorer</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      )}

      {/* EDGE DETAILS */}
      {selectedEdge && (
        <div className="space-y-4">
          <div>
            <span className="text-[11px] text-slate-500 dark:text-zinc-500 uppercase tracking-wider font-semibold block mb-1">
              Transfer Movement
            </span>
            <div className="bg-slate-50 dark:bg-zinc-950 p-2.5 rounded-lg border border-slate-200 dark:border-zinc-800 space-y-2 text-xs font-mono">
              <div>
                <span className="text-slate-500 dark:text-zinc-500 block text-[10px]">FROM:</span>
                <span className="text-slate-700 dark:text-zinc-300">{shortAddress(selectedEdge.source, 8, 6)}</span>
              </div>
              <div>
                <span className="text-slate-500 dark:text-zinc-500 block text-[10px]">TO:</span>
                <span className="text-cyan-700 dark:text-cyan-300">{shortAddress(selectedEdge.target, 8, 6)}</span>
              </div>
            </div>
          </div>

          {/* Asset Breakdown on Edge */}
          {selectedEdge.assets && selectedEdge.assets.length > 0 ? (
            <div>
              <span className="text-[11px] text-slate-500 dark:text-zinc-500 uppercase tracking-wider font-semibold block mb-1.5">
                Transferred Assets ({selectedEdge.assets.length})
              </span>
              <div className="space-y-2">
                {selectedEdge.assets.map((asset, idx) => (
                  <div
                    key={idx}
                    className="bg-slate-50 dark:bg-zinc-950/80 border border-slate-200 dark:border-zinc-800 rounded-lg p-2.5 text-xs font-mono space-y-1"
                  >
                    <div className="flex justify-between items-center">
                      <span className="font-bold text-slate-900 dark:text-zinc-200">{asset.asset}</span>
                      <span className="text-cyan-700 dark:text-cyan-400 font-semibold">{asset.value} {asset.asset}</span>
                    </div>
                    {asset.tainted_value > 0 && (
                      <div className="text-[11px] text-amber-600 dark:text-amber-400 flex justify-between">
                        <span>FIFO Taint:</span>
                        <span>{asset.tainted_value} {asset.asset} ({(asset.tainted_fraction * 100).toFixed(1)}%)</span>
                      </div>
                    )}
                    {asset.tx_hash && (
                      <a
                        href={getTxUrl(explorerBase, asset.tx_hash)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[10px] text-slate-500 dark:text-zinc-400 hover:text-cyan-600 dark:hover:text-cyan-400 flex items-center gap-1 pt-1"
                      >
                        <span>Tx: {shortAddress(asset.tx_hash, 6, 6)}</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div>
              <span className="text-[11px] text-slate-500 dark:text-zinc-500 uppercase tracking-wider font-semibold block mb-1">
                Value Transferred
              </span>
              <p className="font-mono text-sm text-cyan-700 dark:text-cyan-300">
                {selectedEdge.value} {selectedEdge.asset || 'ETH'}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
