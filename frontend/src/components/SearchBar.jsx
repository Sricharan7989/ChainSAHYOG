import { useState, useRef } from 'react';
import { Search, Sliders, X, Clipboard, ArrowRight, ShieldAlert } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { looksLikeAddress, describeAddressFormat } from '../utils/address';

gsap.registerPlugin(useGSAP);

export default function SearchBar({
  address,
  setAddress,
  onTrace,
  loading,
  maxDepth,
  setMaxDepth,
  dustThreshold,
  setDustThreshold,
  mode,
  setMode,
  saveDemo,
  setSaveDemo,
  chainId,
  asOfBlock = '',
  setAsOfBlock = () => {},
}) {
  const [showOptions, setShowOptions] = useState(false);
  const containerRef = useRef(null);
  const btnRef = useRef(null);

  useGSAP(() => {
    gsap.from(containerRef.current, {
      y: 12,
      opacity: 0,
      duration: 0.5,
      delay: 0.05,
      ease: 'power3.out',
    });
  }, { scope: containerRef });

  // Per chain family: never assume 0x. The backend verifies the checksum.
  const isValidAddress = (addr) => looksLikeAddress(addr, chainId);

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) setAddress(text.trim());
    } catch {
      // Clipboard access denied
    }
  };

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (address && !loading) {
      onTrace();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSubmit(e);
    }
  };

  const valid = isValidAddress(address);

  return (
    <div ref={containerRef} className="w-full">
      <form onSubmit={handleSubmit} className="relative flex flex-col gap-2">
        {/* Main Search Bar: Compact, Brutalist, Theme-Aware */}
        <div className="relative flex items-center bg-white dark:bg-[#111111] border-2 border-[#18181b] dark:border-[#262626] shadow-[3px_3px_0px_#18181b] dark:shadow-[3px_3px_0px_#000000] focus-within:border-[#627EEA] focus-within:shadow-[3px_3px_0px_#627EEA] p-1 sm:p-1.5 transition-all">
          <div className="pl-2.5 pr-2 text-[#71717a] dark:text-[#71717a] flex items-center shrink-0">
            <Search className="w-4 h-4" />
          </div>

          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter suspect EVM wallet address (0x...)"
            spellCheck="false"
            autoComplete="off"
            className="w-full bg-transparent text-xs sm:text-sm font-mono text-[#09090b] dark:text-[#f5f5f5] placeholder-[#71717a] dark:placeholder-[#666666] focus:outline-none px-1.5 py-1"
          />

          {/* Quick utility buttons inside input */}
          <div className="flex items-center gap-1.5 pr-0.5 shrink-0">
            {address && (
              <button
                type="button"
                onClick={() => setAddress('')}
                className="h-8 w-8 flex items-center justify-center text-[#71717a] hover:text-[#09090b] dark:hover:text-[#f5f5f5] hover:bg-[#f4f4f5] dark:hover:bg-[#1a1a1a] border border-[#d4d4d8] dark:border-[#262626] transition-colors cursor-pointer"
                title="Clear input"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}

            <button
              type="button"
              onClick={handlePaste}
              className="h-8 px-2 flex items-center gap-1 text-[#71717a] hover:text-[#627EEA] hover:bg-[#f4f4f5] dark:hover:bg-[#1a1a1a] border border-[#d4d4d8] dark:border-[#262626] transition-colors cursor-pointer text-xs font-mono"
              title="Paste from clipboard"
            >
              <Clipboard className="w-3.5 h-3.5" />
              <span className="hidden md:inline text-[11px]">Paste</span>
            </button>

            <button
              type="button"
              onClick={() => setShowOptions(!showOptions)}
              className={`h-8 px-2.5 border text-xs font-mono flex items-center gap-1.5 transition-all cursor-pointer ${
                showOptions
                  ? 'bg-[#627EEA]/15 text-[#627EEA] border-[#627EEA] font-semibold'
                  : 'bg-[#f4f4f5] dark:bg-[#1a1a1a] text-[#52525b] dark:text-[#a3a3a3] border-[#d4d4d8] dark:border-[#262626] hover:text-[#09090b] dark:hover:text-[#f5f5f5] hover:border-[#71717a]'
              }`}
              title="Forensic Trace Parameters"
            >
              <Sliders className="w-3.5 h-3.5" />
              <span className="hidden sm:inline text-xs">Options</span>
            </button>

            {/* Trace Action Button */}
            <button
              ref={btnRef}
              type="submit"
              disabled={loading || !address}
              className={`h-8 px-3.5 sm:px-4 font-bold text-xs uppercase flex items-center gap-1.5 transition-all cursor-pointer border ${
                loading
                  ? 'bg-[#e4e4e7] dark:bg-[#1a1a1a] text-[#71717a] dark:text-[#666666] border-[#d4d4d8] dark:border-[#262626] cursor-not-allowed'
                  : valid
                  ? 'bg-[#627EEA] hover:bg-[#5068cf] text-white border-[#18181b] dark:border-[#627EEA] shadow-[2px_2px_0px_#18181b] dark:shadow-[2px_2px_0px_#000000] active:translate-x-[1px] active:translate-y-[1px]'
                  : 'bg-[#f4f4f5] dark:bg-[#1a1a1a] hover:bg-[#e4e4e7] dark:hover:bg-[#262626] text-[#71717a] dark:text-[#666666] border-[#d4d4d8] dark:border-[#262626]'
              }`}
            >
              {loading ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-[#627EEA] border-t-transparent animate-spin" />
                  <span>Tracing…</span>
                </>
              ) : (
                <>
                  <span>Trace</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </div>
        </div>

        {/* Address Format Notice if invalid */}
        {address && !valid && (
          <div className="flex items-center gap-1.5 px-3 text-xs text-amber-600 dark:text-amber-400 font-sans">
            <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
            <span>Expected {describeAddressFormat(chainId)}.</span>
          </div>
        )}

        {/* Expandable Forensic Options */}
        {showOptions && (
          <div className="bg-white dark:bg-[#111111] border-2 border-[#18181b] dark:border-[#262626] shadow-[3px_3px_0px_#18181b] dark:shadow-[3px_3px_0px_#000000] p-4 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 animate-in fade-in duration-150">
            {/* Hop Depth */}
            <div>
              <div className="flex justify-between text-xs mb-1.5 font-mono">
                <span className="text-[#52525b] dark:text-[#a3a3a3] font-medium">Max Depth (Hops)</span>
                <span className="text-[#627EEA] font-bold">{maxDepth} hops</span>
              </div>
              <input
                type="range"
                min="1"
                max="6"
                step="1"
                value={maxDepth}
                onChange={(e) => setMaxDepth(Number(e.target.value))}
                className="w-full accent-[#627EEA] cursor-pointer h-1.5 bg-[#e4e4e7] dark:bg-[#2a2a2a]"
              />
              <span className="text-[11px] text-[#71717a] dark:text-[#666666] font-mono">Standard: 4 hops</span>
            </div>

            {/* Dust Floor */}
            <div>
              <div className="flex justify-between text-xs mb-1.5 font-mono">
                <span className="text-[#52525b] dark:text-[#a3a3a3] font-medium">Dust Floor (Native)</span>
                <span className="text-[#627EEA] font-bold">{dustThreshold} ETH</span>
              </div>
              <input
                type="number"
                min="0.0001"
                max="1.0"
                step="0.005"
                value={dustThreshold}
                onChange={(e) => setDustThreshold(parseFloat(e.target.value) || 0)}
                className="w-full bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] px-2.5 py-1 text-xs font-mono text-[#09090b] dark:text-[#f5f5f5] focus:outline-none focus:border-[#627EEA]"
              />
              {/* Quick preset buttons */}
              <div className="flex items-center gap-1 mt-1.5">
                {[0.005, 0.01, 0.05, 0.1].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setDustThreshold(val)}
                    className={`text-[10px] font-mono px-1.5 py-0.5 border cursor-pointer transition-colors ${
                      dustThreshold === val
                        ? 'bg-[#627EEA] text-white border-[#627EEA] font-bold'
                        : 'bg-[#f4f4f5] dark:bg-[#1a1a1a] text-[#52525b] dark:text-[#a3a3a3] border-[#d4d4d8] dark:border-[#262626] hover:border-[#627EEA]'
                    }`}
                  >
                    {val === 0.01 ? '0.01 (Std)' : val}
                  </button>
                ))}
              </div>
              <span className="text-[10px] text-[#71717a] dark:text-[#666666] font-mono mt-0.5 block">Standard: 0.01 ETH (~₹2,500)</span>
            </div>

            {/* As-of height: pin the trace to a past block. Empty = the chain head
                when the trace starts. The same height always reproduces the same trace. */}
            <div>
              <div className="flex justify-between text-xs mb-1.5 font-mono">
                <span className="text-[#52525b] dark:text-[#a3a3a3] font-medium">As-of Block (optional)</span>
                <span className="text-[#627EEA] font-bold">{asOfBlock ? `#${asOfBlock}` : 'chain head'}</span>
              </div>
              <input
                type="number"
                min="0"
                step="1"
                placeholder="e.g. 23500000"
                value={asOfBlock}
                onChange={(e) => setAsOfBlock(e.target.value.replace(/[^0-9]/g, ''))}
                className="w-full bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] px-2.5 py-1 text-xs font-mono text-[#09090b] dark:text-[#f5f5f5] focus:outline-none focus:border-[#627EEA]"
              />
              <span className="text-[10px] text-[#71717a] dark:text-[#666666] font-mono mt-0.5 block">
                Re-running at the same height reproduces the result
              </span>
            </div>

            {/* Execution Mode */}
            <div>
              <label className="block text-xs font-medium text-[#52525b] dark:text-[#a3a3a3] mb-1.5 font-mono">Trace Mode</label>
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value)}
                className="w-full bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] px-2.5 py-1 text-xs font-mono text-[#09090b] dark:text-[#f5f5f5] focus:outline-none focus:border-[#627EEA] cursor-pointer"
              >
                <option value="auto">Auto (Cache if available, else Live)</option>
                <option value="live">Live (Force fresh query)</option>
                <option value="cache">Cache Only (Offline demo)</option>
              </select>
              <span className="text-[11px] text-[#71717a] dark:text-[#666666] font-mono">Instant replay on demo cases</span>
            </div>

            {/* Save to Replay Toggle */}
            <div className="flex flex-col justify-between">
              <label className="text-xs font-medium text-[#52525b] dark:text-[#a3a3a3] mb-1 font-mono">Save to Demo Cache</label>
              <label className="inline-flex items-center cursor-pointer mt-1">
                <input
                  type="checkbox"
                  checked={saveDemo}
                  onChange={(e) => setSaveDemo(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="relative w-8 h-4 bg-[#d4d4d8] dark:bg-[#2a2a2a] peer-focus:outline-none peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:start-0.5 after:bg-white dark:after:bg-[#111] after:border after:border-[#a1a1aa] dark:after:border-[#404040] after:h-3 after:w-3 after:transition-all peer-checked:bg-[#627EEA]"></div>
                <span className="ms-2 text-xs font-mono text-[#52525b] dark:text-[#a3a3a3]">Record trace snapshot</span>
              </label>
              <span className="text-[11px] text-[#71717a] dark:text-[#666666] font-mono">Saved to data/cache</span>
            </div>
          </div>
        )}
      </form>
    </div>
  );
}
