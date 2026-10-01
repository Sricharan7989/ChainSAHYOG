import { Shield, ArrowUpRight } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function LandingFooter() {
  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <footer className="border-t border-slate-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-950 text-slate-600 dark:text-zinc-400 py-12 px-4 lg:px-6 relative z-10">
      <div className="max-w-6xl mx-auto space-y-10">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
          {/* Brand & Mission (5 cols) */}
          <div className="md:col-span-5 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-white shadow-lg shadow-cyan-500/20">
                <Shield className="w-5 h-5" />
              </div>
              <span className="font-bold text-lg text-slate-900 dark:text-zinc-100">
                Chain<span className="text-cyan-600 dark:text-cyan-400">SAHYOG</span>
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-100 dark:bg-cyan-950 text-cyan-700 dark:text-cyan-400 border border-cyan-300 dark:border-cyan-800">
                SIH26182
              </span>
            </div>

            <p className="text-xs text-slate-600 dark:text-zinc-400 leading-relaxed max-w-sm">
              Lightweight blockchain intelligence engine for the Indian Cybercrime Coordination
              Centre (I4C) SAHYOG workflow. Traces illicit EVM funds forward to regulated
              VASPs for swift Section 91 CrPC / Section 94 BNSS lawful asset freezing.
            </p>

            <div className="text-[11px] text-slate-400 dark:text-zinc-500 font-mono">
              Designed for Smart India Hackathon 2026 (SIH26182)
            </div>
          </div>

          {/* Navigation Links (3 cols) */}
          <div className="md:col-span-3 space-y-3">
            <span className="text-xs font-mono font-semibold uppercase text-slate-800 dark:text-zinc-200">
              Investigation System
            </span>
            <ul className="space-y-2 text-xs">
              <li>
                <a href="#interactive-simulation" className="hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors">
                  Heist Simulation
                </a>
              </li>
              <li>
                <a href="#typologies" className="hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors">
                  Laundering Typologies
                </a>
              </li>
              <li>
                <a href="#capabilities" className="hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors">
                  Engine Capabilities
                </a>
              </li>
              <li>
                <a href="#workflow" className="hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors">
                  Investigative Workflow
                </a>
              </li>
            </ul>
          </div>

          {/* Actions & Console (4 cols) */}
          <div className="md:col-span-4 space-y-4">
            <span className="text-xs font-mono font-semibold uppercase text-slate-800 dark:text-zinc-200">
              Live Investigation
            </span>
            <p className="text-xs text-slate-600 dark:text-zinc-400">
              Ready to trace suspect EVM wallets? Access the full forensic graph workspace.
            </p>

            <Link
              to="/dashboard"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-semibold text-xs shadow-lg shadow-cyan-950/40 transition-all"
            >
              <span>Launch Forensic Console</span>
              <ArrowUpRight className="w-4 h-4" />
            </Link>
          </div>
        </div>

        {/* Legal & North Star Disclaimer */}
        <div className="pt-8 border-t border-slate-200 dark:border-zinc-900 flex flex-col sm:flex-row items-center justify-between gap-4 text-[11px] text-slate-500 dark:text-zinc-500">
          <p className="max-w-2xl leading-relaxed text-center sm:text-left">
            <strong>Core Insight:</strong> The engine never breaks cryptography, never decrypts
            private keys, and never unmasks anyone itself. It traces public blockchain ledger data
            to regulated corporate chokepoints holding statutory KYC records.
          </p>

          <button
            onClick={scrollToTop}
            className="hover:text-slate-800 dark:hover:text-zinc-300 transition-colors font-mono cursor-pointer shrink-0"
          >
            ↑ Back to Top
          </button>
        </div>
      </div>
    </footer>
  );
}
