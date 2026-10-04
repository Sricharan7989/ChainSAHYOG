import { Shield, ArrowUpRight } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function LandingFooter() {
  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <footer className="border-t border-[#d4d4d8] dark:border-[#262626] bg-[#f4f4f5] dark:bg-[#0e0e0e] text-[#52525b] dark:text-[#a3a3a3] py-12 px-4 lg:px-6 relative z-10 transition-colors duration-200">
      <div className="max-w-6xl mx-auto space-y-10">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
          {/* Brand & Mission (5 cols) */}
          <div className="md:col-span-5 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 bg-[#ffffff] dark:bg-[#111111] border-2 border-[#627EEA] flex items-center justify-center text-[#627EEA]">
                <Shield className="w-5 h-5" />
              </div>
              <span className="font-bold text-lg text-[#09090b] dark:text-[#f5f5f5]">
                Chain<span className="text-[#627EEA]">SAHYOG</span>
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 bg-[#e4e4e7] dark:bg-[#1a1a1a] text-[#627EEA] border border-[#627EEA]/40 uppercase font-semibold">
                SIH26182
              </span>
            </div>

            <p className="text-xs text-[#52525b] dark:text-[#a3a3a3] leading-relaxed max-w-sm">
              Lightweight blockchain intelligence engine for the Indian Cybercrime Coordination
              Centre (I4C) SAHYOG workflow. Traces illicit EVM funds forward to regulated
              VASPs, so police can serve a lawful request under the applicable provisions of the Bharatiya Nagarik Suraksha Sanhita, 2023 and the Information Technology Act, 2000.
            </p>

            <div className="text-[11px] text-[#71717a] dark:text-[#666666] font-mono">
              Designed for Smart India Hackathon 2026 (SIH26182)
            </div>
          </div>

          {/* Navigation Links (3 cols) */}
          <div className="md:col-span-3 space-y-3 font-mono">
            <span className="text-xs font-semibold uppercase text-[#09090b] dark:text-[#f5f5f5] tracking-wider">
              Investigation System
            </span>
            <ul className="space-y-2 text-xs text-[#52525b] dark:text-[#a3a3a3]">
              <li>
                <a href="#interactive-simulation" className="hover:text-[#627EEA] transition-colors">
                  Heist Simulation
                </a>
              </li>
              <li>
                <a href="#typologies" className="hover:text-[#627EEA] transition-colors">
                  Laundering Typologies
                </a>
              </li>
              <li>
                <a href="#capabilities" className="hover:text-[#627EEA] transition-colors">
                  Engine Capabilities
                </a>
              </li>
              <li>
                <a href="#workflow" className="hover:text-[#627EEA] transition-colors">
                  Investigative Workflow
                </a>
              </li>
            </ul>
          </div>

          {/* Actions & Console (4 cols) */}
          <div className="md:col-span-4 space-y-4">
            <span className="text-xs font-mono font-semibold uppercase text-[#09090b] dark:text-[#f5f5f5] tracking-wider">
              Live Investigation
            </span>
            <p className="text-xs text-[#52525b] dark:text-[#a3a3a3]">
              Ready to trace suspect EVM wallets? Access the full forensic graph workspace.
            </p>

            <Link
              to="/dashboard"
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#627EEA] hover:bg-[#748ef5] text-white font-semibold text-xs transition-all brutal-press hover:shadow-[4px_4px_0px_#000]"
            >
              <span>Launch Forensic Console</span>
              <ArrowUpRight className="w-4 h-4" />
            </Link>
          </div>
        </div>

        {/* Legal & North Star Disclaimer */}
        <div className="pt-8 border-t border-[#d4d4d8] dark:border-[#262626] flex flex-col sm:flex-row items-center justify-between gap-4 text-[11px] text-[#71717a] dark:text-[#666666]">
          <p className="max-w-2xl leading-relaxed text-center sm:text-left">
            <strong className="text-[#3f3f46] dark:text-[#888888]">Core Insight:</strong> The engine never breaks cryptography, never decrypts
            private keys, and never unmasks anyone itself. It traces public blockchain ledger data
            to regulated corporate chokepoints holding statutory KYC records.
          </p>

          <button
            onClick={scrollToTop}
            className="hover:text-[#09090b] dark:hover:text-white transition-colors font-mono cursor-pointer shrink-0"
          >
            ↑ Back to Top
          </button>
        </div>
      </div>
    </footer>
  );
}
