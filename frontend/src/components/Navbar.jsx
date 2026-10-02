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
      y: -25,
      opacity: 0,
      duration: 0.6,
      ease: 'power3.out',
    });
  }, { scope: navRef });

  const isHealthy = health?.status === 'ok';
  const graphBackend = health?.graph?.backend || health?.graph || 'memory';
  const isDark = theme === 'dark';

  return (
    <div className="sticky top-3 sm:top-4 z-40 px-3 sm:px-6 w-full max-w-6xl mx-auto mb-5 sm:mb-6">
      <header
        ref={navRef}
        className="border-2 border-[#18181b] dark:border-[#262626] bg-[#ffffff] dark:bg-[#0e0e0e] shadow-[4px_4px_0px_#627EEA] px-3 sm:px-6 py-2.5 flex items-center justify-between gap-3 sm:gap-4 transition-colors"
      >
        {/* Brand identity */}
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="flex items-center gap-2.5 sm:gap-3 group focus:outline-none"
            title="ChainSAHYOG Home"
          >
            <div className="w-8 h-8 sm:w-9 sm:h-9 bg-[#18181b] dark:bg-[#1a1a1a] border border-[#627EEA] flex items-center justify-center text-[#627EEA] group-hover:bg-[#627EEA] group-hover:text-white transition-colors">
              <Shield className="w-4 h-4 sm:w-5 sm:h-5" />
            </div>
            <div>
              <div className="flex items-center gap-1.5 sm:gap-2">
                <span className="font-bold text-base sm:text-lg tracking-tight text-[#09090b] dark:text-[#f5f5f5] flex items-center">
                  Chain<span className="text-[#627EEA] font-extrabold ml-0.5">SAHYOG</span>
                </span>
                <span className="text-[9px] sm:text-[10px] font-mono tracking-wider uppercase px-1.5 py-0.5 bg-[#627EEA]/15 text-[#627EEA] border border-[#627EEA]/30 font-semibold">
                  I4C
                </span>
              </div>
              <p className="text-[10px] sm:text-[11px] text-[#71717a] dark:text-[#888888] hidden sm:block font-mono">
                Crypto Wallet → VASP Attribution Engine
              </p>
            </div>
          </Link>
        </div>

        {/* Dynamic Center/Right Navigation */}
        <div className="flex items-center gap-2 sm:gap-4">
          {isLanding ? (
            /* LANDING PAGE NAV */
            <>
              <nav className="hidden md:flex items-center gap-5 text-xs text-[#71717a] dark:text-[#a3a3a3] font-mono uppercase tracking-wider">
                <a
                  href="#interactive-simulation"
                  className="hover:text-[#627EEA] transition-colors"
                >
                  Simulation
                </a>
                <a
                  href="#typologies"
                  className="hover:text-[#627EEA] transition-colors"
                >
                  Typologies
                </a>
                <a
                  href="#capabilities"
                  className="hover:text-[#627EEA] transition-colors"
                >
                  Capabilities
                </a>
                <a
                  href="#workflow"
                  className="hover:text-[#627EEA] transition-colors"
                >
                  Workflow
                </a>
              </nav>

              {/* Theme Toggle Button */}
              <button
                type="button"
                onClick={toggleTheme}
                className="p-2 border border-[#18181b] dark:border-[#262626] bg-[#f4f4f5] dark:bg-[#1a1a1a] text-[#09090b] dark:text-[#f5f5f5] hover:text-[#627EEA] dark:hover:text-[#627EEA] transition-colors cursor-pointer brutal-press"
                title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
                aria-label="Toggle theme"
              >
                {isDark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-[#627EEA]" />}
              </button>

              <Link
                to="/dashboard"
                className="inline-flex items-center gap-1.5 sm:gap-2 bg-[#18181b] hover:bg-[#627EEA] dark:bg-[#f5f5f5] dark:hover:bg-[#627EEA] text-white dark:text-[#0a0a0a] dark:hover:text-white font-semibold text-xs px-3 sm:px-4 py-2 border border-[#18181b] dark:border-[#f5f5f5] hover:border-[#627EEA] dark:hover:border-[#627EEA] transition-all cursor-pointer whitespace-nowrap brutal-press"
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
                className="hidden sm:inline-flex items-center gap-1.5 text-xs font-mono text-[#71717a] dark:text-[#a3a3a3] hover:text-[#09090b] dark:hover:text-[#f5f5f5] px-2.5 py-1.5 hover:bg-[#f4f4f5] dark:hover:bg-[#1a1a1a] border border-transparent hover:border-[#18181b] dark:hover:border-[#262626] transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Overview</span>
              </Link>

              {/* Engine & Backend Health */}
              <div className="hidden md:flex items-center gap-2 px-2.5 py-1.5 bg-[#f4f4f5] dark:bg-[#111111] border border-[#18181b] dark:border-[#262626] text-xs">
                <span className="flex items-center gap-1.5">
                  <span
                    className={`w-2.5 h-2.5 rounded-full ${
                      isHealthy
                        ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]'
                        : 'bg-red-500 shadow-[0_0_8px_#ef4444]'
                    }`}
                  />
                  <span className="text-[#71717a] dark:text-[#a3a3a3] font-medium font-mono">API</span>
                </span>
                <span className="text-[#a1a1aa] dark:text-[#333333]">|</span>
                <span className="flex items-center gap-1 text-[#71717a] dark:text-[#666666]">
                  <Database className="w-3.5 h-3.5" />
                  <span className="font-mono text-[11px] uppercase text-[#09090b] dark:text-[#a3a3a3]">
                    {graphBackend === 'neo4j' ? 'Neo4j' : 'Memory'}
                  </span>
                </span>
              </div>

              {/* Chain Selector */}
              <div className="relative">
                <select
                  value={selectedChainId}
                  onChange={(e) => onSelectChain(Number(e.target.value))}
                  className="bg-[#f4f4f5] dark:bg-[#111111] border border-[#18181b] dark:border-[#262626] hover:border-[#627EEA] text-[#09090b] dark:text-[#f5f5f5] text-xs font-mono px-3 py-1.5 focus:outline-none focus:border-[#627EEA] appearance-none pr-8 cursor-pointer transition-colors"
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
                <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-[#71717a] dark:text-[#666666]">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </div>

              {/* Theme Toggle Button in Dashboard */}
              <button
                type="button"
                onClick={toggleTheme}
                className="p-1.5 sm:p-2 border border-[#18181b] dark:border-[#262626] bg-[#f4f4f5] dark:bg-[#1a1a1a] text-[#09090b] dark:text-[#f5f5f5] hover:text-[#627EEA] dark:hover:text-[#627EEA] transition-colors cursor-pointer brutal-press"
                title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
                aria-label="Toggle theme"
              >
                {isDark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-[#627EEA]" />}
              </button>
            </>
          )}
        </div>
      </header>
    </div>
  );
}
