import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { Shield, ArrowRight, Play, Terminal, Layers, FileCheck, CheckCircle2 } from 'lucide-react';

gsap.registerPlugin(useGSAP);

export default function HeroSection({ demos = [] }) {
  const containerRef = useRef(null);
  const navigate = useNavigate();
  const [quickAddress, setQuickAddress] = useState('');
  const [quickChain, setQuickChain] = useState(1);

  useGSAP(() => {
    const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });

    tl.from('.hero-badge', { y: -20, opacity: 0, duration: 0.6 })
      .from('.hero-title', { y: 25, opacity: 0, duration: 0.8 }, '-=0.3')
      .from('.hero-desc', { y: 20, opacity: 0, duration: 0.7 }, '-=0.4')
      .from('.hero-search-box', { y: 25, opacity: 0, scale: 0.98, duration: 0.7 }, '-=0.3')
      .from('.hero-stat-item', { y: 15, opacity: 0, stagger: 0.1, duration: 0.6 }, '-=0.4');
  }, { scope: containerRef });

  const handleLaunchTrace = (e) => {
    e?.preventDefault();
    const addr = quickAddress.trim();
    if (addr) {
      navigate(`/dashboard?address=${encodeURIComponent(addr)}&chain=${quickChain}`);
    } else {
      navigate('/dashboard');
    }
  };

  const handleSelectDemo = (demo) => {
    navigate(`/dashboard?address=${encodeURIComponent(demo.address)}&chain=${demo.chain_id || 1}`);
  };

  const scrollToSimulation = () => {
    const element = document.getElementById('interactive-simulation');
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <section ref={containerRef} className="relative pt-12 pb-20 px-4 lg:px-8 overflow-hidden">
      <div className="max-w-5xl mx-auto flex flex-col items-center text-center space-y-8">
        {/* Law Enforcement / SIH Badge */}
        <div className="hero-badge inline-flex items-center gap-2.5 px-3.5 py-1.5 rounded-full bg-cyan-50 dark:bg-cyan-950/60 border border-cyan-200 dark:border-cyan-500/30 text-cyan-700 dark:text-cyan-400 text-xs font-mono tracking-wide shadow-sm">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping inline-block" />
          <span className="font-semibold uppercase">SIH26182</span>
          <span className="text-slate-400 dark:text-zinc-500">•</span>
          <span className="text-slate-700 dark:text-zinc-300">I4C / SAHYOG Cybercrime Workflow</span>
        </div>

        {/* Hero Title */}
        <div className="space-y-4 max-w-4xl">
          <h1 className="hero-title text-3xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-slate-900 dark:text-zinc-100 leading-[1.15]">
            Track Illicit EVM Funds to{' '}
            <span className="bg-gradient-to-r from-cyan-600 via-teal-600 to-emerald-600 dark:from-cyan-400 dark:via-teal-300 dark:to-emerald-400 bg-clip-text text-transparent">
              Exchange Chokepoints
            </span>
          </h1>

          <p className="hero-desc text-base sm:text-lg text-slate-600 dark:text-zinc-400 max-w-2xl mx-auto leading-relaxed">
            Criminals move stolen crypto through disposable burner wallets to obscure the trail.
            ChainSAHYOG traces the money through them to the centralized exchanges holding KYC records,
            enabling police to freeze accounts under Section 91 CrPC.
          </p>
        </div>

        {/* Quick Launch / Investigation Bar */}
        <div className="hero-search-box w-full max-w-2xl bg-white/95 dark:bg-zinc-900/90 border border-slate-200 dark:border-zinc-800 p-2 sm:p-2.5 rounded-2xl shadow-xl shadow-slate-200/50 dark:shadow-cyan-950/20 backdrop-blur-xl space-y-3">
          <form onSubmit={handleLaunchTrace} className="flex flex-col sm:flex-row items-center gap-2">
            <div className="relative flex-1 w-full">
              <input
                type="text"
                value={quickAddress}
                onChange={(e) => setQuickAddress(e.target.value)}
                placeholder="Enter suspect EVM wallet address (0x...)"
                className="w-full bg-slate-50 dark:bg-zinc-950/90 border border-slate-300 dark:border-zinc-700/80 rounded-xl px-4 py-3 text-xs sm:text-sm text-slate-900 dark:text-zinc-100 placeholder-slate-400 dark:placeholder-zinc-500 font-mono focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
              />
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <select
                value={quickChain}
                onChange={(e) => setQuickChain(Number(e.target.value))}
                className="bg-slate-50 dark:bg-zinc-950 border border-slate-300 dark:border-zinc-700/80 text-slate-700 dark:text-zinc-300 text-xs rounded-xl px-3 py-3 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 cursor-pointer"
              >
                <option value={1}>Ethereum</option>
                <option value={137}>Polygon</option>
                <option value={56}>BNB Chain</option>
                <option value={42161}>Arbitrum</option>
              </select>

              <button
                type="submit"
                className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-semibold text-xs sm:text-sm px-5 py-3 rounded-xl shadow-md shadow-cyan-600/20 transition-all cursor-pointer whitespace-nowrap active:scale-98"
              >
                <span>Launch Trace</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </form>

          {/* Quick Demo Badges */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-slate-100 dark:border-zinc-800/80 px-2 text-[11px] text-slate-500 dark:text-zinc-400">
            <span className="flex items-center gap-1.5 font-mono">
              <Terminal className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
              Verified Case Studies:
            </span>
            <div className="flex flex-wrap items-center gap-2">
              {demos && demos.length > 0 ? (
                demos.map((d) => (
                  <button
                    key={d.address}
                    type="button"
                    onClick={() => handleSelectDemo(d)}
                    className="px-2.5 py-1 rounded-md bg-slate-100 hover:bg-cyan-50 hover:text-cyan-700 hover:border-cyan-300 dark:bg-zinc-800/80 dark:hover:bg-cyan-950 dark:hover:text-cyan-300 dark:hover:border-cyan-500/40 border border-slate-200 dark:border-zinc-700/60 font-mono transition-colors cursor-pointer"
                  >
                    {d.title || d.label || `${d.address.slice(0, 10)}...`}
                  </button>
                ))
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() =>
                      handleSelectDemo({
                        address: '0x62425cd6bdcb6bfe51558ea465b063486b70dc9f',
                        chain_id: 1,
                      })
                    }
                    className="px-2.5 py-1 rounded-md bg-slate-100 hover:bg-cyan-50 hover:text-cyan-700 hover:border-cyan-300 dark:bg-zinc-800/80 dark:hover:bg-cyan-950 dark:hover:text-cyan-300 dark:hover:border-cyan-500/40 border border-slate-200 dark:border-zinc-700/60 font-mono transition-colors cursor-pointer"
                  >
                    Binance Deposit Sweep (500 ETH)
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      handleSelectDemo({
                        address: '0x098b716b8aaf21512996dc57eb0615e2383e2f96',
                        chain_id: 1,
                      })
                    }
                    className="px-2.5 py-1 rounded-md bg-slate-100 hover:bg-amber-50 hover:text-amber-700 hover:border-amber-300 dark:bg-zinc-800/80 dark:hover:bg-amber-950 dark:hover:text-amber-300 dark:hover:border-amber-500/40 border border-slate-200 dark:border-zinc-700/60 font-mono transition-colors cursor-pointer"
                  >
                    Multi-Hop Obfuscator
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Secondary Action CTA: Interactive simulation jump */}
        <div className="flex items-center gap-4 text-xs">
          <button
            onClick={scrollToSimulation}
            className="inline-flex items-center gap-2 text-slate-600 hover:text-cyan-600 dark:text-zinc-400 dark:hover:text-cyan-400 transition-colors py-2 cursor-pointer group font-medium"
          >
            <Play className="w-4 h-4 text-cyan-600 dark:text-cyan-400 group-hover:scale-110 transition-transform" />
            <span>See Step-by-Step Chokepoint Attribution (Interactive Simulation)</span>
          </button>
        </div>

        {/* Key Forensic Metrics Banner */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 w-full max-w-4xl pt-6">
          <div className="hero-stat-item p-4 rounded-xl bg-white dark:bg-zinc-900/60 border border-slate-200 dark:border-zinc-800/80 text-left space-y-1 shadow-sm">
            <div className="flex items-center gap-2 text-cyan-600 dark:text-cyan-400 font-mono text-xs font-semibold">
              <Layers className="w-4 h-4" />
              <span>4 EVM Chains</span>
            </div>
            <p className="text-slate-900 dark:text-zinc-100 font-bold text-sm">Forward Multi-Hop</p>
            <p className="text-[11px] text-slate-500 dark:text-zinc-500">
              Ethereum, Polygon, BNB Chain, and Arbitrum One.
            </p>
          </div>

          <div className="hero-stat-item p-4 rounded-xl bg-white dark:bg-zinc-900/60 border border-slate-200 dark:border-zinc-800/80 text-left space-y-1 shadow-sm">
            <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 font-mono text-xs font-semibold">
              <CheckCircle2 className="w-4 h-4" />
              <span>Allowlisted Tokens</span>
            </div>
            <p className="text-slate-900 dark:text-zinc-100 font-bold text-sm">Contract Pinned</p>
            <p className="text-[11px] text-slate-500 dark:text-zinc-500">
              Pins verified smart contracts to ignore spoofed airdrops.
            </p>
          </div>

          <div className="hero-stat-item p-4 rounded-xl bg-white dark:bg-zinc-900/60 border border-slate-200 dark:border-zinc-800/80 text-left space-y-1 shadow-sm">
            <div className="flex items-center gap-2 text-purple-600 dark:text-purple-400 font-mono text-xs font-semibold">
              <Shield className="w-4 h-4" />
              <span>FIFO Taint Math</span>
            </div>
            <p className="text-slate-900 dark:text-zinc-100 font-bold text-sm">Clayton’s Case</p>
            <p className="text-[11px] text-slate-500 dark:text-zinc-500">
              First-in first-out replay calculates exact stolen balances.
            </p>
          </div>

          <div className="hero-stat-item p-4 rounded-xl bg-white dark:bg-zinc-900/60 border border-slate-200 dark:border-zinc-800/80 text-left space-y-1 shadow-sm">
            <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 font-mono text-xs font-semibold">
              <FileCheck className="w-4 h-4" />
              <span>Section 91 CrPC</span>
            </div>
            <p className="text-slate-900 dark:text-zinc-100 font-bold text-sm">Statutory Requisition</p>
            <p className="text-[11px] text-slate-500 dark:text-zinc-500">
              Generates legal notices to freeze accounts and compel KYC.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
