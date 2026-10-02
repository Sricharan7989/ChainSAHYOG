import { useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { Shield, ArrowRight, Play, Layers, FileCheck, CheckCircle2 } from 'lucide-react';

gsap.registerPlugin(useGSAP);

export default function HeroSection() {
  const containerRef = useRef(null);
  const navigate = useNavigate();

  useGSAP(() => {
    const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });

    tl.from('.hero-badge', { y: -20, opacity: 0, duration: 0.6 })
      .from('.hero-title', { y: 25, opacity: 0, duration: 0.8 }, '-=0.3')
      .from('.hero-desc', { y: 20, opacity: 0, duration: 0.7 }, '-=0.4')
      .from('.hero-actions', { y: 25, opacity: 0, scale: 0.98, duration: 0.6 }, '-=0.3')
      .from('.hero-stat-item', { y: 15, opacity: 0, stagger: 0.1, duration: 0.6 }, '-=0.4');
  }, { scope: containerRef });

  const scrollToSimulation = () => {
    const element = document.getElementById('interactive-simulation');
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <section ref={containerRef} className="relative pt-12 pb-16 px-4 lg:px-8 overflow-hidden">
      <div className="max-w-5xl mx-auto flex flex-col items-center text-center space-y-8">
        {/* Law Enforcement / SIH Badge */}
        <div className="hero-badge inline-flex items-center gap-2.5 px-3.5 py-1.5 bg-[#ffffff] dark:bg-[#111111] border border-[#18181b] dark:border-[#627EEA]/40 text-[#627EEA] text-xs font-mono tracking-wide shadow-[3px_3px_0px_#627EEA]">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping inline-block" />
          <span className="font-semibold uppercase">SIH26182</span>
          <span className="text-[#a1a1aa] dark:text-[#555555]">•</span>
          <span className="text-[#52525b] dark:text-[#a3a3a3]">I4C Cybercrime Intelligence Framework</span>
        </div>

        {/* Hero Title */}
        <div className="space-y-4 max-w-4xl">
          <h1 className="hero-title text-3xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-[#09090b] dark:text-[#f5f5f5] leading-[1.15]">
            Track Illicit EVM Funds to{' '}
            <span className="text-[#627EEA] inline-block border-b-4 border-[#627EEA]">
              Exchange Chokepoints
            </span>
          </h1>

          <p className="hero-desc text-base sm:text-lg text-[#52525b] dark:text-[#a3a3a3] max-w-2xl mx-auto leading-relaxed">
            Perpetrators move stolen crypto through disposable burner wallets to obscure the trail.
            ChainSAHYOG follows the money forward through the public blockchain until it reaches
            centralized exchanges holding KYC records, enabling police to freeze accounts under cybercrime law.
          </p>
        </div>

        {/* Focused Hero Action CTAs (No search dialog on landing page) */}
        <div className="hero-actions flex flex-col sm:flex-row items-center justify-center gap-4 pt-2">
          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            className="flex items-center justify-center gap-2.5 bg-[#18181b] hover:bg-[#627EEA] dark:bg-[#627EEA] dark:hover:bg-[#748ef5] text-white font-semibold text-sm px-6 py-3.5 border-2 border-[#18181b] dark:border-[#627EEA] hover:border-[#627EEA] transition-all cursor-pointer whitespace-nowrap brutal-press shadow-[4px_4px_0px_#000] dark:shadow-[4px_4px_0px_#000]"
          >
            <span>Launch Forensic Console</span>
            <ArrowRight className="w-4 h-4" />
          </button>

          <button
            type="button"
            onClick={scrollToSimulation}
            className="flex items-center justify-center gap-2 bg-[#ffffff] hover:bg-[#f4f4f5] dark:bg-[#111111] dark:hover:bg-[#1a1a1a] text-[#09090b] dark:text-[#f5f5f5] font-semibold text-sm px-6 py-3.5 border-2 border-[#18181b] dark:border-[#262626] hover:border-[#627EEA] dark:hover:border-[#627EEA] transition-all cursor-pointer whitespace-nowrap brutal-press shadow-[4px_4px_0px_#627EEA]"
          >
            <Play className="w-4 h-4 text-[#627EEA]" />
            <span>See Step-by-Step Simulation</span>
          </button>
        </div>

        {/* Key Forensic Metrics Banner */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 w-full max-w-4xl pt-8">
          <div className="hero-stat-item p-4 bg-[#ffffff] dark:bg-[#111111] border border-[#18181b] dark:border-[#262626] hover:border-[#627EEA] text-left space-y-1 transition-colors shadow-[2px_2px_0px_#18181b] dark:shadow-[2px_2px_0px_#000]">
            <div className="flex items-center gap-2 text-[#627EEA] font-mono text-xs font-semibold">
              <Layers className="w-4 h-4" />
              <span>4 EVM Chains</span>
            </div>
            <p className="text-[#09090b] dark:text-[#f5f5f5] font-bold text-sm">Forward Multi-Hop</p>
            <p className="text-[11px] text-[#71717a] dark:text-[#777777]">
              Ethereum, Polygon, BNB Chain, and Arbitrum One.
            </p>
          </div>

          <div className="hero-stat-item p-4 bg-[#ffffff] dark:bg-[#111111] border border-[#18181b] dark:border-[#262626] hover:border-emerald-500 text-left space-y-1 transition-colors shadow-[2px_2px_0px_#18181b] dark:shadow-[2px_2px_0px_#000]">
            <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 font-mono text-xs font-semibold">
              <CheckCircle2 className="w-4 h-4" />
              <span>Allowlisted Tokens</span>
            </div>
            <p className="text-[#09090b] dark:text-[#f5f5f5] font-bold text-sm">Contract Pinned</p>
            <p className="text-[11px] text-[#71717a] dark:text-[#777777]">
              Pins verified smart contracts to ignore spoofed airdrops.
            </p>
          </div>

          <div className="hero-stat-item p-4 bg-[#ffffff] dark:bg-[#111111] border border-[#18181b] dark:border-[#262626] hover:border-[#627EEA] text-left space-y-1 transition-colors shadow-[2px_2px_0px_#18181b] dark:shadow-[2px_2px_0px_#000]">
            <div className="flex items-center gap-2 text-[#627EEA] font-mono text-xs font-semibold">
              <Shield className="w-4 h-4" />
              <span>FIFO Taint Math</span>
            </div>
            <p className="text-[#09090b] dark:text-[#f5f5f5] font-bold text-sm">Ledger Replay</p>
            <p className="text-[11px] text-[#71717a] dark:text-[#777777]">
              Chronological replay calculates exact stolen balances.
            </p>
          </div>

          <div className="hero-stat-item p-4 bg-[#ffffff] dark:bg-[#111111] border border-[#18181b] dark:border-[#262626] hover:border-amber-500 text-left space-y-1 transition-colors shadow-[2px_2px_0px_#18181b] dark:shadow-[2px_2px_0px_#000]">
            <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 font-mono text-xs font-semibold">
              <FileCheck className="w-4 h-4" />
              <span>Cybercrime Law</span>
            </div>
            <p className="text-[#09090b] dark:text-[#f5f5f5] font-bold text-sm">IPC Compliance</p>
            <p className="text-[11px] text-[#71717a] dark:text-[#777777]">
              Generates legal notices to freeze accounts and compel KYC.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
