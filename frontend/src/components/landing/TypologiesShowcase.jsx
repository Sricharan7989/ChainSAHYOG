import { useState, useRef } from 'react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import {
  Layers,
  GitBranch,
  Filter,
  Zap,
  AlertOctagon,
  CheckCircle2,
} from 'lucide-react';

gsap.registerPlugin(useGSAP);

const TYPOLOGIES = [
  {
    id: 'peel',
    name: 'Peel Chains',
    tag: 'Structural Laundering',
    icon: GitBranch,
    metric: 'Trunk ≥ 80% • Peel ≤ 20%',
    summary:
      'Iterative peeling separates a small chunk of funds at each hop while the main balance moves along a dominant trunk line. Commonly observed in bot-driven layering.',
    algorithm:
      'Trunk dominance threshold: 80% of node inflow. Side peel threshold: ≤ 20% transferred to a distinct leaf node. Detected across ≥ 3 consecutive hops.',
    exemption:
      'Sweeps from known exchange hot wallets and high-frequency market-maker routers are suppressed to avoid false positives.',
    svgType: 'peel',
  },
  {
    id: 'layering',
    name: 'Rapid Layering',
    tag: 'Temporal Dispersion',
    icon: Layers,
    metric: 'Transit Time < 48 Hours • Hops ≥ 3',
    summary:
      'Rapidly dispersing assets through multiple intermediaries within a tight time window to make real-time forensic interception difficult for law enforcement.',
    algorithm:
      'Transit window ≤ 172,800s (48h) across a chain of ≥ 3 hops where intermediate wallet holding time is less than 6 hours.',
    exemption:
      'Aggregator contracts, DEX routers, and flash loan liquidity pools are classified by contract code and exempted.',
    svgType: 'layering',
  },
  {
    id: 'structuring',
    name: 'Structuring / Smurfing',
    tag: 'Volume Splitting',
    icon: Filter,
    metric: 'Coeff of Variation (σ / μ) < 0.15',
    summary:
      'Splitting large transactions into numerous nearly identical smaller amounts just below mandatory exchange reporting limits.',
    algorithm:
      'Evaluates fan-out clusters with ≥ 4 child outputs where standard deviation divided by mean value is less than 0.15.',
    exemption:
      'Airdrop distributors, salary payouts, and batching contracts are distinguished by transaction frequency and bytecode.',
    svgType: 'structuring',
  },
  {
    id: 'passthrough',
    name: 'Rapid Pass-Through',
    tag: 'Conduit Wallets',
    icon: Zap,
    metric: 'Holding Time < 300s • Delta ≈ 0',
    summary:
      'Automated conduit addresses that hold funds for only seconds before relaying the entire balance forward without retaining reserve liquidity.',
    algorithm:
      'Inflow-to-outflow time delta ≤ 300 seconds with forwarded value ratio between 95% and 100% of received balance.',
    exemption:
      'Gas relayers and automated bots are filtered out based on execution patterns and smart contract metadata.',
    svgType: 'passthrough',
  },
];

export default function TypologiesShowcase() {
  const [selectedId, setSelectedId] = useState('peel');
  const containerRef = useRef(null);

  useGSAP(() => {
    gsap.fromTo(
      '.typology-panel-content',
      { opacity: 0, y: 15 },
      { opacity: 1, y: 0, duration: 0.4, ease: 'power2.out' }
    );
  }, { scope: containerRef, dependencies: [selectedId] });

  const active = TYPOLOGIES.find((t) => t.id === selectedId) || TYPOLOGIES[0];
  const Icon = active.icon;

  return (
    <section id="typologies" ref={containerRef} className="py-16 px-4 lg:px-8 relative scroll-mt-20">
      <div className="max-w-6xl mx-auto space-y-10">
        {/* Title */}
        <div className="text-center space-y-3 max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-[#ffffff] dark:bg-[#111111] border border-[#18181b] dark:border-[#627EEA]/40 text-[#627EEA] text-xs font-mono shadow-[2px_2px_0px_#627EEA]">
            <span>Behavioral Typology Engine</span>
            <span className="text-[#a1a1aa] dark:text-[#555555]">•</span>
            <span>Forensic Pattern Recognition</span>
          </div>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-[#09090b] dark:text-[#f5f5f5]">
            Automated Laundering Pattern Detection
          </h2>
          <p className="text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3] leading-relaxed">
            Every transaction hop is evaluated against mathematical laundering formulas,
            separating deliberate peeling and structuring from normal protocol operations.
          </p>
        </div>

        {/* Tab Selection */}
        <div className="flex flex-wrap items-center justify-center gap-2 p-1.5 bg-[#ffffff] dark:bg-[#111111] border-2 border-[#18181b] dark:border-[#262626] max-w-3xl mx-auto shadow-[3px_3px_0px_#18181b] dark:shadow-[3px_3px_0px_#000]">
          {TYPOLOGIES.map((t) => {
            const TIcon = t.icon;
            const isSelected = t.id === selectedId;
            return (
              <button
                key={t.id}
                onClick={() => setSelectedId(t.id)}
                className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold font-mono transition-all cursor-pointer brutal-press ${
                  isSelected
                    ? 'bg-[#f4f4f5] dark:bg-[#1a1a1a] text-[#627EEA] border border-[#627EEA] shadow-[2px_2px_0px_#627EEA]'
                    : 'text-[#71717a] dark:text-[#a3a3a3] hover:text-[#09090b] dark:hover:text-[#f5f5f5] hover:bg-[#f4f4f5] dark:hover:bg-[#161616] border border-transparent'
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
          <div className="lg:col-span-6 bg-[#ffffff] dark:bg-[#111111] border-2 border-[#18181b] dark:border-[#262626] p-6 flex flex-col justify-between relative overflow-hidden shadow-[4px_4px_0px_#18181b] dark:shadow-[4px_4px_0px_#000]">
            <div className="flex items-center justify-between z-10">
              <span className="text-xs font-mono text-[#52525b] dark:text-[#a3a3a3] flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#627EEA] animate-pulse" />
                Pattern Schematic
              </span>
              <span className="text-[11px] font-mono px-2 py-0.5 bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#18181b] dark:border-[#262626] text-[#627EEA] font-semibold">
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
                    <path d="M 60 120 L 200 120 L 340 120 L 440 120" stroke="#627EEA" strokeWidth="4" />
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

                    <circle cx="440" cy="120" r="16" fill="#1e1b4b" stroke="#627EEA" strokeWidth="2" />
                    <text x="440" y="124" textAnchor="middle" fill="#fff" fontSize="9" fontWeight="bold">VASP</text>

                    {/* Peel drops */}
                    <circle cx="240" cy="50" r="10" fill="#78350f" stroke="#f59e0b" strokeWidth="1.5" />
                    <text x="240" y="53" textAnchor="middle" fill="#fef3c7" fontSize="7">15%</text>

                    <circle cx="380" cy="50" r="10" fill="#78350f" stroke="#f59e0b" strokeWidth="1.5" />
                    <text x="380" y="53" textAnchor="middle" fill="#fef3c7" fontSize="7">15%</text>

                    <text x="200" y="150" fill="#71717a" fontSize="9" textAnchor="middle" fontFamily="monospace">Trunk: 85-90% Continues</text>
                    <text x="310" y="35" fill="#f59e0b" fontSize="9" textAnchor="middle" fontFamily="monospace">Iterative Peels (Burners)</text>
                  </g>
                )}

                {/* 2. LAYERING SVG */}
                {active.svgType === 'layering' && (
                  <g>
                    <path d="M 60 120 L 180 60" stroke="#627EEA" strokeWidth="2.5" />
                    <path d="M 60 120 L 180 120" stroke="#627EEA" strokeWidth="2.5" />
                    <path d="M 60 120 L 180 180" stroke="#627EEA" strokeWidth="2.5" />

                    <path d="M 180 60 L 320 90" stroke="#627EEA" strokeWidth="2" />
                    <path d="M 180 120 L 320 120" stroke="#627EEA" strokeWidth="2" />
                    <path d="M 180 180 L 320 150" stroke="#627EEA" strokeWidth="2" />

                    <path d="M 320 90 L 440 120" stroke="#10b981" strokeWidth="3" />
                    <path d="M 320 120 L 440 120" stroke="#10b981" strokeWidth="3" />
                    <path d="M 320 150 L 440 120" stroke="#10b981" strokeWidth="3" />

                    <circle cx="60" cy="120" r="18" fill="#7f1d1d" stroke="#ef4444" strokeWidth="2" />
                    <text x="60" y="124" textAnchor="middle" fill="#fff" fontSize="9" fontWeight="bold">Suspect</text>

                    {/* Hop 1 */}
                    <circle cx="180" cy="60" r="11" fill="#181e3a" stroke="#627EEA" strokeWidth="1.5" />
                    <circle cx="180" cy="120" r="11" fill="#181e3a" stroke="#627EEA" strokeWidth="1.5" />
                    <circle cx="180" cy="180" r="11" fill="#181e3a" stroke="#627EEA" strokeWidth="1.5" />

                    {/* Hop 2 */}
                    <circle cx="320" cy="90" r="11" fill="#181e3a" stroke="#627EEA" strokeWidth="1.5" />
                    <circle cx="320" cy="120" r="11" fill="#181e3a" stroke="#627EEA" strokeWidth="1.5" />
                    <circle cx="320" cy="150" r="11" fill="#181e3a" stroke="#627EEA" strokeWidth="1.5" />

                    {/* VASP Destination */}
                    <circle cx="440" cy="120" r="20" fill="#064e3b" stroke="#10b981" strokeWidth="3" />
                    <text x="440" y="124" textAnchor="middle" fill="#fff" fontSize="9" fontWeight="bold">Exchange</text>

                    <text x="250" y="215" fill="#71717a" fontSize="9" textAnchor="middle" fontFamily="monospace">
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

                    <text x="250" y="225" fill="#71717a" fontSize="9" textAnchor="middle" fontFamily="monospace">
                      Low CV (σ / μ &lt; 0.15) — Below KYC Thresholds
                    </text>
                  </g>
                )}

                {/* 4. RAPID PASS-THROUGH SVG */}
                {active.svgType === 'passthrough' && (
                  <g>
                    <path d="M 60 120 L 250 120" stroke="#627EEA" strokeWidth="4" />
                    <path d="M 250 120 L 440 120" stroke="#10b981" strokeWidth="4" />

                    <circle cx="60" cy="120" r="18" fill="#7f1d1d" stroke="#ef4444" strokeWidth="2" />
                    <text x="60" y="124" textAnchor="middle" fill="#fff" fontSize="9" fontWeight="bold">Inflow</text>

                    {/* Fast Transit Wallet */}
                    <circle cx="250" cy="120" r="26" fill="#181e3a" stroke="#627EEA" strokeWidth="3" className="animate-spin" strokeDasharray="8 6" />
                    <text x="250" y="117" textAnchor="middle" fill="#627EEA" fontSize="10" fontWeight="bold">PIPE</text>
                    <text x="250" y="130" textAnchor="middle" fill="#dbeafe" fontSize="8">Δ ≈ 0</text>

                    <circle cx="440" cy="120" r="18" fill="#064e3b" stroke="#10b981" strokeWidth="2.5" />
                    <text x="440" y="124" textAnchor="middle" fill="#fff" fontSize="9" fontWeight="bold">Outflow</text>

                    <text x="250" y="170" fill="#627EEA" fontSize="10" fontFamily="monospace" textAnchor="middle">
                      Median Holding Time: 142 seconds (&lt; 300s)
                    </text>
                    <text x="250" y="188" fill="#71717a" fontSize="8" textAnchor="middle">
                      Wallet retains zero liquidity; acts as automated forwarder
                    </text>
                  </g>
                )}
              </svg>
            </div>

            <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#18181b] dark:border-[#262626] p-3 flex items-center justify-between text-xs font-mono">
              <span className="text-[#71717a] dark:text-[#888888]">Detector State:</span>
              <span className="text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Active in Tracing Engine
              </span>
            </div>
          </div>

          {/* Forensic Specification Details (6 cols) */}
          <div className="lg:col-span-6 bg-[#ffffff] dark:bg-[#111111] border-2 border-[#18181b] dark:border-[#262626] p-6 sm:p-8 flex flex-col justify-between space-y-6 shadow-[4px_4px_0px_#18181b] dark:shadow-[4px_4px_0px_#000]">
            <div className="space-y-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#f4f4f5] dark:bg-[#1a1a1a] border border-[#18181b] dark:border-[#627EEA]/40 flex items-center justify-center text-[#627EEA]">
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-xs font-mono text-[#627EEA] uppercase font-semibold">
                    {active.tag}
                  </span>
                  <h3 className="text-xl font-bold text-[#09090b] dark:text-[#f5f5f5]">
                    {active.name} Pattern
                  </h3>
                </div>
              </div>

              <p className="text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3] leading-relaxed">
                {active.summary}
              </p>

              {/* Formula & Rule box */}
              <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#18181b] dark:border-[#262626] p-4 space-y-2">
                <span className="text-xs font-mono text-[#627EEA] font-semibold uppercase">
                  Mathematical Detection Rule
                </span>
                <p className="text-xs font-mono text-[#09090b] dark:text-[#a3a3a3] bg-[#ffffff] dark:bg-[#111111] p-2.5 border border-[#18181b] dark:border-[#262626]">
                  {active.algorithm}
                </p>
              </div>

              {/* False Positive Guard */}
              <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#18181b] dark:border-[#262626] p-4 space-y-1.5">
                <span className="text-xs font-semibold text-[#09090b] dark:text-[#f5f5f5] flex items-center gap-1.5 font-mono">
                  <AlertOctagon className="w-3.5 h-3.5 text-amber-500" />
                  False-Positive Suppression Guard
                </span>
                <p className="text-xs text-[#52525b] dark:text-[#a3a3a3] leading-relaxed">
                  {active.exemption}
                </p>
              </div>
            </div>

            <div className="pt-4 border-t border-[#18181b] dark:border-[#262626] flex items-center justify-between text-xs text-[#71717a] dark:text-[#888888] font-mono">
              <span>Standard: Indian Cybercrime Coordination Centre (I4C) Guidelines</span>
              <span className="text-[#627EEA] font-semibold">SIH26182 Core</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
