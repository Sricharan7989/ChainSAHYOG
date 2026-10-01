import { useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Shield, Database, ArrowRight, ArrowLeft, Sun, Moon } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { useTheme } from '../context/ThemeContext';

gsap.registerPlugin(useGSAP);

export default function Navbar({
  health,
  selectedChainId = 1,
  onSelectChain = () => {},
  chains = [],
  variant = 'dashboard',
}) {
  const navRef = useRef(null);
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const isLanding = variant === 'landing' || location.pathname === '/';

  useGSAP(() => {
    gsap.from(navRef.current, {
      y: -20,
      opacity: 0,
      duration: 0.6,
      ease: 'power3.out',
    });
  }, { scope: navRef });

  const isHealthy = health?.status === 'ok';
  const graphBackend = health?.graph?.backend || health?.graph || 'memory';

  return (
    <header
      ref={navRef}
      className="border-b border-slate-200 dark:border-zinc-800/80 bg-white/85 dark:bg-zinc-950/85 backdrop-blur-md sticky top-0 z-40 px-4 lg:px-8 py-3 transition-colors"
    >
      <div className="w-full max-w-[1920px] mx-auto flex items-center justify-between gap-4">
        {/* Brand identity */}
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="flex items-center gap-3 group focus:outline-none"
            title="ChainSAHYOG Home"
          >
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-md shadow-cyan-500/20 ring-1 ring-cyan-400/40 group-hover:scale-105 transition-transform">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg tracking-tight text-slate-900 dark:text-zinc-100 flex items-center">
                  Chain<span className="text-cyan-600 dark:text-cyan-400 font-extrabold">SAHYOG</span>
                </span>
                <span className="text-[10px] font-mono tracking-widest uppercase px-1.5 py-0.5 rounded bg-cyan-50 dark:bg-cyan-500/10 text-cyan-700 dark:text-cyan-400 border border-cyan-200 dark:border-cyan-500/20 font-semibold">
                  I4C / SIH26182
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-zinc-400 hidden sm:block">
                Crypto Wallet → VASP Attribution Engine
              </p>
            </div>
          </Link>
        </div>

        {/* Dynamic Center/Right Navigation */}
        <div className="flex items-center gap-3 sm:gap-5">
          {isLanding ? (
            /* LANDING PAGE NAV */
            <>
              <nav className="hidden md:flex items-center gap-5 text-xs text-slate-600 dark:text-zinc-400 font-medium">
                <a
                  href="#interactive-simulation"
                  className="hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors"
                >
                  Heist Simulation
                </a>
                <a
                  href="#typologies"
                  className="hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors"
                >
                  Typologies
                </a>
                <a
                  href="#capabilities"
                  className="hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors"
                >
                  Capabilities
                </a>
                <a
                  href="#workflow"
                  className="hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors"
                >
                  Workflow
                </a>
              </nav>

              <Link
                to="/dashboard"
                className="inline-flex items-center gap-2 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-semibold text-xs px-4 py-2 rounded-xl shadow-md shadow-cyan-600/20 transition-all cursor-pointer whitespace-nowrap active:scale-98"
              >
                <span>Launch Console</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </>
          ) : (
            /* DASHBOARD NAV */
            <>
              <Link
                to="/"
                className="hidden sm:inline-flex items-center gap-1.5 text-xs text-slate-600 hover:text-slate-900 dark:text-zinc-400 dark:hover:text-zinc-200 px-2.5 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-900 border border-transparent hover:border-slate-200 dark:hover:border-zinc-800 transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Landing Overview</span>
              </Link>

              {/* Engine & Backend Health */}
              <div className="hidden md:flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-slate-100 dark:bg-zinc-900/90 border border-slate-200 dark:border-zinc-800 text-xs">
                <span className="flex items-center gap-1.5">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      isHealthy ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'
                    }`}
                  />
                  <span className="text-slate-700 dark:text-zinc-300 font-medium">API</span>
                </span>
                <span className="text-slate-400 dark:text-zinc-600">|</span>
                <span className="flex items-center gap-1 text-slate-500 dark:text-zinc-400">
                  <Database className="w-3.5 h-3.5" />
                  <span className="font-mono text-[11px] uppercase text-slate-800 dark:text-zinc-300">
                    {graphBackend === 'neo4j' ? 'Neo4j' : 'Memory'}
                  </span>
                </span>
              </div>

              {/* Chain Selector */}
              <div className="relative">
                <select
                  value={selectedChainId}
                  onChange={(e) => onSelectChain(Number(e.target.value))}
                  className="bg-slate-100 dark:bg-zinc-900 border border-slate-300 dark:border-zinc-700/80 hover:border-slate-400 dark:hover:border-zinc-600 text-slate-800 dark:text-zinc-200 text-xs font-medium rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 appearance-none pr-8 cursor-pointer transition-colors"
                >
                  {chains && chains.length > 0 ? (
                    chains.map((chain) => (
                      <option key={chain.chain_id} value={chain.chain_id}>
                        {chain.name} ({chain.native}) {chain.requires_paid_plan ? '⚠️' : ''}
                      </option>
                    ))
                  ) : (
                    <option value={1}>Ethereum (ETH)</option>
                  )}
                </select>
                <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-slate-500 dark:text-zinc-400">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </div>
            </>
          )}

          {/* Monochrome Theme Toggle (Sun in Dark Mode, Moon in Light Mode) */}
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            className="p-2 rounded-lg border border-slate-200 dark:border-zinc-800 bg-slate-100 hover:bg-slate-200 dark:bg-zinc-900 dark:hover:bg-zinc-800 text-slate-700 dark:text-zinc-300 transition-colors cursor-pointer"
            title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          >
            {theme === 'dark' ? (
              <Sun className="w-4 h-4 stroke-[2]" />
            ) : (
              <Moon className="w-4 h-4 stroke-[2]" />
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
