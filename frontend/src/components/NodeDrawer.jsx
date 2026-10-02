import { useRef, useState } from 'react';
import { X, ExternalLink, Copy, Check, Coins } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { shortAddress, formatAssets, getExplorerUrl, getTxUrl } from '../utils/formatters';

gsap.registerPlugin(useGSAP);

export default function NodeDrawer({
  selectedNode,
  selectedEdge,
  onClose,
  explorerBase,
  position,
}) {
  const drawerRef = useRef(null);
  const [copied, setCopied] = useState(false);

  useGSAP(() => {
    if (selectedNode || selectedEdge) {
      gsap.fromTo(
        drawerRef.current,
        { scale: 0.95, opacity: 0 },
        { scale: 1, opacity: 1, duration: 0.2, ease: 'power2.out' }
      );
    }
  }, { dependencies: [selectedNode, selectedEdge], scope: drawerRef });

  if (!selectedNode && !selectedEdge) return null;

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Compute smart contextual coordinates near the clicked node / edge
  const containerW = position?.containerWidth || 600;
  const containerH = position?.containerHeight || 640;
  const popoverW = 268;
  const popoverH = 190;

  let left;
  let top;

  if (position?.x !== undefined && position?.y !== undefined) {
    // Attempt placing to the right of node
    if (position.x + 28 + popoverW < containerW - 12) {
      left = position.x + 28;
    } else if (position.x - 28 - popoverW > 12) {
      // Place to the left if right side overflows
      left = position.x - 28 - popoverW;
    } else {
      left = Math.max(12, (containerW - popoverW) / 2);
    }

    // Vertically clamp between top controls bar (76px) and bottom container border
    top = Math.max(76, Math.min(position.y - 25, containerH - popoverH - 12));
  } else {
    left = Math.max(12, containerW - popoverW - 16);
    top = 76;
  }

  // Determine node role badge styling
  const isStart = selectedNode?.is_start;
  const isVasp = selectedNode?.is_vasp || selectedNode?.entity_type === 'exchange';
  const isObfuscator =
    selectedNode?.is_mixer ||
    selectedNode?.is_bridge ||
    selectedNode?.entity_type === 'suspected_exchange' ||
    selectedNode?.entity_type === 'sanctioned';

  const roleLabel = isStart
    ? 'SUSPECT'
    : isVasp
    ? (selectedNode?.entity || 'EXCHANGE').toUpperCase()
    : isObfuscator
    ? (selectedNode?.entity || (selectedNode?.is_mixer ? 'MIXER' : 'BRIDGE')).toUpperCase()
    : 'CONDUIT';

  const badgeColor = isStart
    ? 'bg-red-500/20 text-red-400 border-red-500/40'
    : isVasp
    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
    : isObfuscator
    ? 'bg-amber-500/20 text-amber-400 border-amber-500/40'
    : 'bg-[#18181b] text-[#a3a3a3] border-[#333338]';

  return (
    <div
      ref={drawerRef}
      style={{ left: `${left}px`, top: `${top}px` }}
      className="absolute z-30 w-[268px] bg-[#121214] border border-[#2a2a2a] p-3 text-[#f5f5f5] shadow-[4px_4px_0px_#000000] transition-[left,top] duration-75 select-none"
    >
      {/* Header Row */}
      <div className="flex items-center justify-between gap-1.5 pb-2 border-b border-[#262626]">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className={`px-2 py-0.5 text-[10px] font-mono font-bold border truncate ${badgeColor}`}>
            {selectedNode ? roleLabel : 'TRANSFER HOP'}
          </span>
          {selectedNode?.depth !== undefined && (
            <span className="text-[10px] font-mono text-[#888888] bg-[#1a1a1a] px-1.5 py-0.5 border border-[#262626] shrink-0">
              Hop {selectedNode.depth}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1 text-[#888888] hover:text-white hover:bg-[#222225] transition-colors cursor-pointer border border-[#262626] shrink-0"
          title="Close details"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* NODE FORENSICS */}
      {selectedNode && (
        <div className="mt-2.5 space-y-2.5 text-xs font-mono">
          {/* Address with Action Buttons */}
          <div className="bg-[#0a0a0a] border border-[#262626] p-2 flex items-center justify-between gap-1.5">
            <span className="text-[#627EEA] font-bold tracking-tight text-[11px] truncate">
              {shortAddress(selectedNode.id, 8, 6)}
            </span>
            <div className="flex items-center gap-1 shrink-0">
              <button
                type="button"
                onClick={() => handleCopy(selectedNode.id)}
                className="p-1 text-[#888888] hover:text-white hover:bg-[#1a1a1a] transition-colors cursor-pointer border border-[#262626]"
                title="Copy Address"
              >
                {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              </button>
              <a
                href={getExplorerUrl(explorerBase, selectedNode.id)}
                target="_blank"
                rel="noopener noreferrer"
                className="p-1 text-[#888888] hover:text-[#627EEA] hover:bg-[#1a1a1a] transition-colors cursor-pointer border border-[#262626]"
                title="View on Explorer"
              >
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>

          {/* Tainted Value Card if Available */}
          {selectedNode.tainted_in && Object.keys(selectedNode.tainted_in).length > 0 && (
            <div className="bg-[#151726] border border-[#627EEA]/30 p-2">
              <span className="text-[10px] text-[#627EEA] font-bold flex items-center gap-1 mb-0.5">
                <Coins className="w-3 h-3" />
                <span>Tainted Inflow</span>
              </span>
              <p className="text-xs font-bold text-white">
                {formatAssets(selectedNode.tainted_in)}
              </p>
              <span className="text-[9px] text-[#888888] block mt-0.5">
                FIFO chronological taint
              </span>
            </div>
          )}
        </div>
      )}

      {/* EDGE FORENSICS */}
      {selectedEdge && (
        <div className="mt-2.5 space-y-2 text-xs font-mono">
          <div className="bg-[#0a0a0a] border border-[#262626] p-2 space-y-1 text-[11px]">
            <div className="flex justify-between text-[#888888]">
              <span>FROM:</span>
              <span className="text-[#f5f5f5]">{shortAddress(selectedEdge.source, 6, 4)}</span>
            </div>
            <div className="flex justify-between text-[#888888]">
              <span>TO:</span>
              <span className="text-[#627EEA]">{shortAddress(selectedEdge.target, 6, 4)}</span>
            </div>
          </div>

          <div className="bg-[#151726] border border-[#627EEA]/30 p-2 flex items-center justify-between">
            <span className="text-[10px] text-[#627EEA] font-bold">Transfer Amount</span>
            <span className="text-xs font-bold text-white">
              {selectedEdge.value} {selectedEdge.asset || 'ETH'}
            </span>
          </div>

          {selectedEdge.tx_hash && (
            <a
              href={getTxUrl(explorerBase, selectedEdge.tx_hash)}
              target="_blank"
              rel="noopener noreferrer"
              className="py-1.5 px-2 bg-[#1a1a1a] hover:bg-[#222225] text-[10px] text-[#a3a3a3] hover:text-white flex items-center justify-center gap-1.5 border border-[#262626] transition-colors cursor-pointer"
            >
              <span>Tx: {shortAddress(selectedEdge.tx_hash, 6, 4)}</span>
              <ExternalLink className="w-3 h-3 text-[#627EEA]" />
            </a>
          )}
        </div>
      )}
    </div>
  );
}
