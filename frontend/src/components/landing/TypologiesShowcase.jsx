import { useState, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { GitFork, Network, Split, Clock, CheckCircle2, AlertOctagon } from 'lucide-react';

gsap.registerPlugin(ScrollTrigger, useGSAP);

const TYPOLOGIES = [
  {
    id: 'peel_chain',
    name: 'Peel Chain',
    icon: GitFork,
    tag: 'Asymmetric Splitting',
    summary:
      'Suspects route ~85% of funds to a fresh wallet while peeling off ~15% to burner addresses or cash-out points at each hop to disguise the main trail.',
    algorithm: 'Trunk Ratio > 0.80 across ≥ 3 consecutive hops with minimum value threshold.',
    metric: 'Peel Ratio ≥ 85% / 15%',
    exemption: 'Suppressed if recipient is a recognized liquidity pool or staking contract.',
    svgType: 'peel',
  },
  {
    id: 'layering',
    name: 'Layering & Smurfing',
    icon: Network,
    tag: 'Temporal Fan-Out',
    summary:
      'Funds are rapidly fanned out across 3 or more wallet layers within 48 hours to create a dense web of transactions that confounds manual block explorers.',
    algorithm: 'Hop Distance ≥ 3, Max Temporal Dispersion < 48 hrs, Inflow/Outflow ratio > 0.90.',
    metric: 'Depth ≥ 3 hops in < 48 hours',
    exemption: 'Excluded for bridge contracts and batch disbursement services.',
    svgType: 'layering',
  },
  {
    id: 'structuring',
    name: 'Structuring (Smurfing)',
    icon: Split,
    tag: 'Threshold Evasion',
    summary:
      'A large sum is divided into multiple parallel transfers of near-identical amounts, kept just below exchange KYC and statutory reporting limits.',
    algorithm: 'Coefficient of Variation (CV = σ / μ) < 0.15 over ≥ 3 parallel transfers.',
    metric: 'CV = σ/μ < 0.15',
    exemption: 'Payroll multisigs and airdrop distributors filtered via contract bytecode check.',
    svgType: 'structuring',
  },
  {
    id: 'pass_through',
    name: 'Rapid Pass-Through',
    icon: Clock,
    tag: 'Transit Conduit',
    summary:
      'Intermediate wallets act as brief conduits, holding funds for less than 5 minutes before forwarding them onward with near-zero retained balance.',
    algorithm: 'Median Hold Time < 300s, Inflow ≈ Outflow (Net balance Δ < 1%).',
    metric: 'Hold Time < 300s, Net Δ ≈ 0',
    exemption: 'MEV flashbots and automated arbitrage routing bots recognized and tagged.',
    svgType: 'passthrough',
  },
];

export default function TypologiesShowcase() {
  const containerRef = useRef(null);
  const [selectedId, setSelectedId] = useState('peel_chain');

  useGSAP(() => {
    gsap.fromTo(
      '.typology-panel-content',
      { opacity: 0, y: 15 },
      {
        opacity: 1,
        y: 0,
        duration: 0.5,
        ease: 'power2.out',
        scrollTrigger: {
          trigger: containerRef.current,
          start: 'top 85%',
        },
      }
    );
  }, { scope: containerRef, dependencies: [selectedId] });

  const active = TYPOLOGIES.find((t) => t.id === selectedId) || TYPOLOGIES[0];
  const Icon = active.icon;

  return (
    <section id="typologies" ref={containerRef} className="py-16 px-4 lg:px-6 relative scroll-mt-20">
      <div className="max-w-6xl mx-auto space-y-10">
        {/* Title */}
        <div className="text-center space-y-3 max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-purple-100 dark:bg-purple-950/40 border border-purple-300 dark:border-purple-500/30 text-purple-700 dark:text-purple-400 text-xs font-mono">
            <span>Algorithmic Detection</span>
            <span className="text-slate-400 dark:text-zinc-500">•</span>
            <span>Forensic Typologies</span>
          </div>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 dark:text-zinc-100">
            Automated Laundering Pattern Detection
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-zinc-400 leading-relaxed">
            Every transaction hop is evaluated against mathematical laundering formulas,
            separating deliberate peeling and structuring from normal protocol operations.
          </p>
        </div>

        {/* Tab Selection */}
        <div className="flex flex-wrap items-center justify-center gap-2 p-1.5 rounded-2xl bg-slate-100 dark:bg-zinc-900/80 border border-slate-200 dark:border-zinc-800 max-w-3xl mx-auto">
          {TYPOLOGIES.map((t) => {
            const TIcon = t.icon;
            const isSelected = t.id === selectedId;
            return (
              <button
                key={t.id}
                onClick={() => setSelectedId(t.id)}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-white dark:bg-zinc-800 text-cyan-700 dark:text-cyan-300 border border-cyan-500/40 shadow-sm dark:shadow-cyan-950/30'
                    : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200 hover:bg-slate-200/50 dark:hover:bg-zinc-800/40 border border-transparent'
                }`}
              >
                <TIcon className="w-4 h-4" />
                <span>{t.name}</span>
              </button>
            );
          })}
        </div>

        {/* Main Interactive Showcase Display */}
        <div className="typology-panel-content grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
          {/* Visual Schematic Box (6 cols) */}
          <div className="lg:col-span-6 bg-white dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-2xl p-6 flex flex-col justify-between relative overflow-hidden shadow-sm dark:shadow-2xl">
            <div className="flex items-center justify-between z-10">
              <span className="text-xs font-mono text-slate-600 dark:text-zinc-400 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
                Pattern Schematic
              </span>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-cyan-600 dark:text-cyan-400 font-semibold">
                {active.metric}
              </span>
            </div>

            {/* Dynamic Pattern SVG */}
            <div className="my-8 flex items-center justify-center">
              <svg viewBox="0 0 500 240" className="w-full max-w-md h-auto select-none">
                {/* 1. PEEL CHAIN SVG */}
                {active.svgType === 'peel' && (
                  <g>
                    {/* Trunk Line */}
                    <path d="M 60 120 L 200 120 L 340 120 L 440 120" stroke="#06b6d4" strokeWidth="4" />
                    {/* Peels */}
                    <path d="M 200 120 L 240 50" stroke="#f59e0b" strokeWidth="2.5" strokeDasharray="4 3" />
                    <path d="M 340 120 L 380 50" stroke="#f59e0b" strokeWidth="2.5" strokeDasharray="4 3" />

                    {/* Nodes */}
                    <circle cx="60" cy="120" r="18" fill="#7f1d1d" stroke="#ef4444" strokeWidth="2" />
                    <text x="60" y="124" textAnchor="middle" fill="#fff" fontSize="9" fontWeight="bold">Loot</text>

                    <circle cx="200" cy="120" r="14" fill="#064e3b" stroke="#10b981" strokeWidth="2" />
                    <text x="200" y="123" textAnchor="middle" fill="#fff" fontSize="8">85%</text>

                    <circle cx="340" cy="120" r="14" fill="#064e3b" stroke="#10b981" strokeWidth="2" />
                    <text x="340" y="123" textAnchor="middle" fill="#fff" fontSize="8">70%</text>

                    <circle cx="440" cy="120" r="16" fill="#1e1b4b" stroke="#8b5cf6" strokeWidth="2" />
                    <text x="440" y="124" textAnchor="middle" fill="#fff" fontSize="9" fontWeight="bold">VASP</text>

                    {/* Peel drops */}
                    <circle cx="240" cy="50" r="10" fill="#78350f" stroke="#f59e0b" strokeWidth="1.5" />
                    <text x="240" y="53" textAnchor="middle" fill="#fef3c7" fontSize="7">15%</text>

                    <circle cx="380" cy="50" r="10" fill="#78350f" stroke="#f59e0b" strokeWidth="1.5" />
                    <text x="380" y="53" textAnchor="middle" fill="#fef3c7" fontSize="7">15%</text>

                    <text x="200" y="150" fill="#a1a1aa" fontSize="9" textAnchor="middle">Trunk: 85-90% Continues</text>
                    <text x="310" y="35" fill="#f59e0b" fontSize="9" textAnchor="middle">Iterative Peels (Burners)</text>
                  </g>
                )}

                {/* 2. LAYERING SVG */}
                {active.svgType === 'layering' && (
                  <g>
                    {/* Fan out lines */}
                    <path d="M 60 120 L 180 60" stroke="#8b5cf6" strokeWidth="2.5" />
                    <path d="M 60 120 L 180 120" stroke="#8b5cf6" strokeWidth="2.5" />
                    <path d="M 60 120 L 180 180" stroke="#8b5cf6" strokeWidth="2.5" />

                    <path d="M 180 60 L 320 90" stroke="#8b5cf6" strokeWidth="2" />
                    <path d="M 180 120 L 320 120" stroke="#8b5cf6" strokeWidth="2" />
                    <path d="M 180 180 L 320 150" stroke="#8b5cf6" strokeWidth="2" />

                    <path d="M 320 90 L 440 120" stroke="#10b981" strokeWidth="3" />
                    <path d="M 320 120 L 440 120" stroke="#10b981" strokeWidth="3" />
                    <path d="M 320 150 L 440 120" stroke="#10b981" strokeWidth="3" />

                    <circle cx="60" cy="120" r="18" fill="#7f1d1d" stroke="#ef4444" strokeWidth="2" />
                    <text x="60" y="124" textAnchor="middle" fill="#fff" fontSize="9" fontWeight="bold">Suspect</text>

                    {/* Hop 1 */}
                    <circle cx="180" cy="60" r="11" fill="#2e1065" stroke="#a855f7" strokeWidth="1.5" />
                    <circle cx="180" cy="120" r="11" fill="#2e1065" stroke="#a855f7" strokeWidth="1.5" />
                    <circle cx="180" cy="180" r="11" fill="#2e1065" stroke="#a855f7" strokeWidth="1.5" />

                    {/* Hop 2 */}
                    <circle cx="320" cy="90" r="11" fill="#2e1065" stroke="#a855f7" strokeWidth="1.5" />
                    <circle cx="320" cy="120" r="11" fill="#2e1065" stroke="#a855f7" strokeWidth="1.5" />
                    <circle cx="320" cy="150" r="11" fill="#2e1065" stroke="#a855f7" strokeWidth="1.5" />

                    {/* VASP Destination */}
                    <circle cx="440" cy="120" r="20" fill="#064e3b" stroke="#10b981" strokeWidth="3" />
                    <text x="440" y="124" textAnchor="middle" fill="#fff" fontSize="9" fontWeight="bold">Exchange</text>

                    <text x="250" y="215" fill="#a1a1aa" fontSize="9" textAnchor="middle">
                      Rapid Multi-Hop Dispersion (Hop ≥ 3, &lt; 48h)
                    </text>
                  </g>
                )}

                {/* 3. STRUCTURING SVG */}
                {active.svgType === 'structuring' && (
                  <g>
                    <path d="M 60 120 L 200 50" stroke="#f59e0b" strokeWidth="2.5" />
                    <path d="M 60 120 L 200 95" stroke="#f59e0b" strokeWidth="2.5" />
                    <path d="M 60 120 L 200 145" stroke="#f59e0b" strokeWidth="2.5" />
                    <path d="M 60 120 L 200 190" stroke="#f59e0b" strokeWidth="2.5" />

                    <path d="M 200 50 L 400 120" stroke="#10b981" strokeWidth="2" strokeDasharray="3 3" />
                    <path d="M 200 95 L 400 120" stroke="#10b981" strokeWidth="2" strokeDasharray="3 3" />
                    <path d="M 200 145 L 400 120" stroke="#10b981" strokeWidth="2" strokeDasharray="3 3" />
                    <path d="M 200 190 L 400 120" stroke="#10b981" strokeWidth="2" strokeDasharray="3 3" />

                    <circle cx="60" cy="120" r="18" fill="#7f1d1d" stroke="#ef4444" strokeWidth="2" />
                    <text x="60" y="124" textAnchor="middle" fill="#fff" fontSize="9" fontWeight="bold">100 ETH</text>

                    {/* Smurfs */}
                    <circle cx="200" cy="50" r="12" fill="#78350f" stroke="#f59e0b" strokeWidth="1.5" />
                    <text x="200" y="53" textAnchor="middle" fill="#fff" fontSize="7">9.8 ETH</text>

                    <circle cx="200" cy="95" r="12" fill="#78350f" stroke="#f59e0b" strokeWidth="1.5" />
                    <text x="200" y="98" textAnchor="middle" fill="#fff" fontSize="7">9.9 ETH</text>

                    <circle cx="200" cy="145" r="12" fill="#78350f" stroke="#f59e0b" strokeWidth="1.5" />
                    <text x="200" y="148" textAnchor="middle" fill="#fff" fontSize="7">9.8 ETH</text>

                    <circle cx="200" cy="190" r="12" fill="#78350f" stroke="#f59e0b" strokeWidth="1.5" />
                    <text x="200" y="193" textAnchor="middle" fill="#fff" fontSize="7">9.9 ETH</text>

                    <circle cx="400" cy="120" r="20" fill="#064e3b" stroke="#10b981" strokeWidth="2.5" />
                    <text x="400" y="124" textAnchor="middle" fill="#fff" fontSize="9" fontWeight="bold">Exchange</text>

                    <text x="250" y="225" fill="#a1a1aa" fontSize="9" textAnchor="middle">
                      Low CV (σ / μ &lt; 0.15) — Below KYC Thresholds
                    </text>
                  </g>
                )}

                {/* 4. RAPID PASS-THROUGH SVG */}
                {active.svgType === 'passthrough' && (
                  <g>
                    <path d="M 60 120 L 250 120" stroke="#06b6d4" strokeWidth="4" />
                    <path d="M 250 120 L 440 120" stroke="#10b981" strokeWidth="4" />

                    <circle cx="60" cy="120" r="18" fill="#7f1d1d" stroke="#ef4444" strokeWidth="2" />
                    <text x="60" y="124" textAnchor="middle" fill="#fff" fontSize="9" fontWeight="bold">Inflow</text>

                    {/* Fast Transit Wallet */}
                    <circle cx="250" cy="120" r="26" fill="#083344" stroke="#06b6d4" strokeWidth="3" className="animate-spin" strokeDasharray="8 6" />
                    <text x="250" y="117" textAnchor="middle" fill="#67e8f9" fontSize="10" fontWeight="bold">PIPE</text>
                    <text x="250" y="130" textAnchor="middle" fill="#a5f3fc" fontSize="8">Δ ≈ 0</text>

                    <circle cx="440" cy="120" r="18" fill="#064e3b" stroke="#10b981" strokeWidth="2.5" />
                    <text x="440" y="124" textAnchor="middle" fill="#fff" fontSize="9" fontWeight="bold">Outflow</text>

                    <text x="250" y="170" fill="#06b6d4" fontSize="10" fontWeight="mono" textAnchor="middle">
                      Median Holding Time: 142 seconds (&lt; 300s)
                    </text>
                    <text x="250" y="188" fill="#a1a1aa" fontSize="8" textAnchor="middle">
                      Wallet retains zero liquidity; acts as automated forwarder
                    </text>
                  </g>
                )}
              </svg>
            </div>

            <div className="bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 p-3 rounded-xl flex items-center justify-between text-xs font-mono">
              <span className="text-slate-500 dark:text-zinc-500">Detector State:</span>
              <span className="text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Active in Tracing Engine
              </span>
            </div>
          </div>

          {/* Forensic Specification Details (6 cols) */}
          <div className="lg:col-span-6 bg-white dark:bg-zinc-900/60 border border-slate-200 dark:border-zinc-800/80 rounded-2xl p-6 sm:p-8 flex flex-col justify-between space-y-6 shadow-sm dark:shadow-none">
            <div className="space-y-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-600 dark:text-purple-400">
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-xs font-mono text-purple-600 dark:text-purple-400 uppercase font-semibold">
                    {active.tag}
                  </span>
                  <h3 className="text-xl font-bold text-slate-900 dark:text-zinc-100">
                    {active.name} Pattern
                  </h3>
                </div>
              </div>

              <p className="text-xs sm:text-sm text-slate-600 dark:text-zinc-300 leading-relaxed">
                {active.summary}
              </p>

              {/* Formula & Rule box */}
              <div className="bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800/90 rounded-xl p-4 space-y-2">
                <span className="text-xs font-mono text-cyan-600 dark:text-cyan-400 font-semibold uppercase">
                  Mathematical Detection Rule
                </span>
                <p className="text-xs font-mono text-slate-800 dark:text-zinc-300 bg-white dark:bg-zinc-900 p-2.5 rounded-lg border border-slate-200 dark:border-zinc-800">
                  {active.algorithm}
                </p>
              </div>

              {/* False Positive Guard */}
              <div className="bg-slate-50/80 dark:bg-zinc-950/60 border border-slate-200 dark:border-zinc-800/80 rounded-xl p-4 space-y-1.5">
                <span className="text-xs font-semibold text-slate-800 dark:text-zinc-200 flex items-center gap-1.5">
                  <AlertOctagon className="w-3.5 h-3.5 text-amber-500" />
                  False-Positive Suppression Guard
                </span>
                <p className="text-xs text-slate-600 dark:text-zinc-400 leading-relaxed">
                  {active.exemption}
                </p>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-200 dark:border-zinc-800 flex items-center justify-between text-xs text-slate-500 dark:text-zinc-400 font-mono">
              <span>Standard: FATF Red Flags & PMLA 2002</span>
              <span className="text-cyan-600 dark:text-cyan-400 font-semibold">SIH26182 Core</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
