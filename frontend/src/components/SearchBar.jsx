import { useState, useRef } from 'react';
import { Search, Sliders, X, Clipboard, ArrowRight, ShieldAlert } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

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
}) {
  const [showOptions, setShowOptions] = useState(false);
  const containerRef = useRef(null);
  const btnRef = useRef(null);

  useGSAP(() => {
    gsap.from(containerRef.current, {
      y: 15,
      opacity: 0,
      duration: 0.7,
      delay: 0.1,
      ease: 'power3.out',
    });
  }, { scope: containerRef });

  const isValidAddress = (addr) => /^0x[a-fA-F0-9]{40}$/.test(addr.trim());

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
        {/* Main Search Bar */}
        <div className="relative flex items-center bg-white dark:bg-zinc-900/90 border border-slate-200 dark:border-zinc-700/80 hover:border-slate-300 dark:hover:border-zinc-600 focus-within:border-cyan-500 focus-within:ring-2 focus-within:ring-cyan-500/20 rounded-xl p-1.5 shadow-sm dark:shadow-xl transition-all">
          <div className="pl-3 pr-2 text-slate-400 dark:text-zinc-400">
            <Search className="w-5 h-5" />
          </div>

          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter suspect EVM wallet address (0x...)"
            spellCheck="false"
            autoComplete="off"
            className="w-full bg-transparent text-sm sm:text-base font-mono text-slate-900 dark:text-zinc-100 placeholder-slate-400 dark:placeholder-zinc-500 focus:outline-none px-1 py-1.5"
          />

          {/* Quick utility buttons inside input */}
          <div className="flex items-center gap-1.5 pr-1">
            {address && (
              <button
                type="button"
                onClick={() => setAddress('')}
                className="p-1.5 text-slate-400 dark:text-zinc-400 hover:text-slate-700 dark:hover:text-zinc-200 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-md transition-colors cursor-pointer"
                title="Clear input"
              >
                <X className="w-4 h-4" />
              </button>
            )}

            <button
              type="button"
              onClick={handlePaste}
              className="p-1.5 text-slate-400 dark:text-zinc-400 hover:text-cyan-600 dark:hover:text-cyan-400 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-md transition-colors cursor-pointer"
              title="Paste from clipboard"
            >
              <Clipboard className="w-4 h-4" />
            </button>

            <button
              type="button"
              onClick={() => setShowOptions(!showOptions)}
              className={`p-1.5 rounded-md border text-xs flex items-center gap-1 transition-all cursor-pointer ${
                showOptions
                  ? 'bg-cyan-50 dark:bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-200 dark:border-cyan-500/30 font-semibold'
                  : 'bg-slate-100 dark:bg-zinc-800/80 text-slate-600 dark:text-zinc-400 border-slate-200 dark:border-zinc-700 hover:text-slate-900 dark:hover:text-zinc-200 hover:bg-slate-200 dark:hover:bg-zinc-700'
              }`}
              title="Forensic Trace Parameters"
            >
              <Sliders className="w-4 h-4" />
              <span className="hidden sm:inline font-sans text-xs font-medium">Options</span>
            </button>

            {/* Trace Action Button */}
            <button
              ref={btnRef}
              type="submit"
              disabled={loading || !address}
              className={`px-4 sm:px-5 py-2 rounded-lg font-semibold text-xs sm:text-sm flex items-center gap-2 transition-all cursor-pointer ${
                loading
                  ? 'bg-slate-100 dark:bg-zinc-800 text-slate-400 dark:text-zinc-500 cursor-not-allowed'
                  : valid
                  ? 'bg-linear-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white shadow-md shadow-cyan-500/20 hover:shadow-cyan-500/30 active:scale-95'
                  : 'bg-slate-100 dark:bg-zinc-800 hover:bg-slate-200 dark:hover:bg-zinc-700 text-slate-500 dark:text-zinc-300'
              }`}
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
                  <span>Tracing…</span>
                </>
              ) : (
                <>
                  <span>Trace Funds</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>

        {/* Address Format Notice if invalid */}
        {address && !valid && (
          <div className="flex items-center gap-1.5 px-3 text-xs text-amber-600 dark:text-amber-400 font-sans">
            <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
            <span>Expected a 42-character hexadecimal EVM address beginning with 0x.</span>
          </div>
        )}

        {/* Expandable Forensic Options */}
        {showOptions && (
          <div className="bg-white/95 dark:bg-zinc-900/95 border border-slate-200 dark:border-zinc-800 rounded-xl p-4 shadow-xl dark:shadow-2xl backdrop-blur-md grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 animate-in fade-in slide-in-from-top-2 duration-200">
            {/* Hop Depth */}
            <div>
              <div className="flex justify-between text-xs mb-1.5">
                <span className="text-slate-600 dark:text-zinc-400 font-medium">Max Depth (Hops)</span>
                <span className="font-mono text-cyan-600 dark:text-cyan-400 font-semibold">{maxDepth} hops</span>
              </div>
              <input
                type="range"
                min="1"
                max="6"
                step="1"
                value={maxDepth}
                onChange={(e) => setMaxDepth(Number(e.target.value))}
                className="w-full accent-cyan-500 cursor-pointer h-1.5 bg-slate-200 dark:bg-zinc-700 rounded-lg"
              />
              <span className="text-[11px] text-slate-500 dark:text-zinc-500">Depth 4 is the investigative standard</span>
            </div>

            {/* Dust Floor */}
            <div>
              <div className="flex justify-between text-xs mb-1.5">
                <span className="text-slate-600 dark:text-zinc-400 font-medium">Dust Floor (Native)</span>
                <span className="font-mono text-cyan-600 dark:text-cyan-400 font-semibold">{dustThreshold} ETH</span>
              </div>
              <input
                type="number"
                min="0.0001"
                max="1.0"
                step="0.001"
                value={dustThreshold}
                onChange={(e) => setDustThreshold(parseFloat(e.target.value) || 0)}
                className="w-full bg-slate-50 dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 rounded-md px-2.5 py-1 text-xs font-mono text-slate-900 dark:text-zinc-100 focus:outline-none focus:border-cyan-500"
              />
              <span className="text-[11px] text-slate-500 dark:text-zinc-500">Filters out micro-transactions</span>
            </div>

            {/* Execution Mode */}
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-zinc-400 mb-1.5">Trace Mode</label>
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value)}
                className="w-full bg-slate-50 dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 rounded-md px-2.5 py-1 text-xs font-mono text-slate-900 dark:text-zinc-100 focus:outline-none focus:border-cyan-500 cursor-pointer"
              >
                <option value="auto">Auto (Replay Cache if exists, else Live)</option>
                <option value="live">Live (Force fresh blockchain query)</option>
                <option value="cache">Cache Only (Fail-safe offline mode)</option>
              </select>
              <span className="text-[11px] text-slate-500 dark:text-zinc-500">Auto provides instant demo playback</span>
            </div>

            {/* Save to Replay Toggle */}
            <div className="flex flex-col justify-between">
              <label className="text-xs font-medium text-slate-600 dark:text-zinc-400 mb-1">Save to Demo Cache</label>
              <label className="inline-flex items-center cursor-pointer mt-1">
                <input
                  type="checkbox"
                  checked={saveDemo}
                  onChange={(e) => setSaveDemo(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="relative w-9 h-5 bg-slate-200 dark:bg-zinc-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:inset-s-0.5 after:bg-white after:border-slate-300 dark:after:border-zinc-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-cyan-500"></div>
                <span className="ms-2 text-xs text-slate-700 dark:text-zinc-300">Record trace</span>
              </label>
              <span className="text-[11px] text-slate-500 dark:text-zinc-500">Stores snapshot in data/cache</span>
            </div>
          </div>
        )}
      </form>
    </div>
  );
}
