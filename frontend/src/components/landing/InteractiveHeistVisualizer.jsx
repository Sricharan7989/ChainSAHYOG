import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import {
  Play,
  Pause,
  RotateCcw,
  ShieldAlert,
  Shuffle,
  Building2,
  FileCheck2,
  ArrowRight,
  HelpCircle,
} from 'lucide-react';

gsap.registerPlugin(useGSAP);

const STAGES = [
  {
    id: 1,
    title: 'Suspect Inflow: Anonymous Unhosted Wallet',
    tag: 'Step 01 • Origin',
    icon: ShieldAlert,
    color: 'red',
    badge: 'Suspect Origin',
    address: '0x62425cd6bdcb6bfe51558ea465b063486b70dc9f',
    desc: 'An unhosted private key executes an unauthorized transfer of 500 ETH (~$1.6M). Unhosted wallets are generated locally without KYC, central ownership, or user identity records.',
    lawEnforcementDilemma:
      'Investigators cannot subpoena a private key. There is no intermediary to freeze funds or produce identity files at this stage.',
    actionLabel: 'Trace Obfuscation Hops →',
  },
  {
    id: 2,
    title: 'Intermediate Routing: Peel Chains & Smurfing',
    tag: 'Step 02 • Layering',
    icon: Shuffle,
    color: 'amber',
    badge: 'Burner Addresses',
    address: '12 Disposable Burner Wallets (0xe463..., 0x9f3f..., 0x7a11...)',
    desc: 'The balance is fragmented across disposable addresses using peel chains and quick conduits to complicate transaction trails on public explorers.',
    lawEnforcementDilemma:
      'Pursuing individual disposable wallets manually is inefficient because burner keys are discarded immediately after a transfer.',
    actionLabel: 'Locate VASP Chokepoint →',
  },
  {
    id: 3,
    title: 'Exchange Deposit: Regulated VASP Chokepoint',
    tag: 'Step 03 • Attribution',
    icon: Building2,
    color: 'emerald',
    badge: 'Binance Deposit (2 Hops)',
    address: '0x28c6c06298d514db089934071355e5743bf21d60',
    desc: 'To liquidate crypto into fiat currency, funds are deposited into a centralized exchange. ChainSAHYOG tracks the path directly to Binance with 88% confidence and FIFO taint accounting.',
    lawEnforcementDilemma:
      'Centralized exchanges are regulated financial entities. They cluster deposit addresses and maintain mandatory KYC identity records.',
    actionLabel: 'Generate Lawful Requisition →',
  },
  {
    id: 4,
    title: 'Enforcement Action: Sec 91 CrPC / 94 BNSS Notice',
    tag: 'Step 04 • Actionable Output',
    icon: FileCheck2,
    color: 'cyan',
    badge: 'SAHYOG Dossier',
    address: 'Binance Compliance Desk • Requisition #I4C-2026-CRPC91-8842',
    desc: 'ChainSAHYOG generates a court-ready forensic PDF and statutory requisition. Police serve the notice to the exchange compliance desk to freeze accounts and obtain verified KYC (PAN, Aadhaar, bank accounts, IP logs).',
    lawEnforcementDilemma:
      'The perpetrator is unmasked through regulated KYC records using public blockchain data, without breaking cryptography.',
    actionLabel: 'Replay Simulation ↺',
  },
];

export default function InteractiveHeistVisualizer() {
  const containerRef = useRef(null);
  const navigate = useNavigate();
  const [currentStage, setCurrentStage] = useState(1);
  const [isPlaying, setIsPlaying] = useState(true);

  // Auto-advance loop when playing
  useEffect(() => {
    if (!isPlaying) return;
    const timer = setInterval(() => {
      setCurrentStage((prev) => (prev % 4) + 1);
    }, 5500);
    return () => clearInterval(timer);
  }, [isPlaying]);

  useGSAP(() => {
    // Pulse active node in the SVG diagram
    gsap.to('.visualizer-active-node', {
      scale: 1.15,
      transformOrigin: 'center center',
      repeat: -1,
      yoyo: true,
      duration: 1,
      ease: 'power1.inOut',
    });

    // Animate stage info card transition
    gsap.fromTo(
      '.stage-info-content',
      { opacity: 0, y: 12 },
      { opacity: 1, y: 0, duration: 0.45, ease: 'power2.out' }
    );
  }, { scope: containerRef, dependencies: [currentStage] });

  const active = STAGES[currentStage - 1];

  const handleNext = () => {
    setIsPlaying(false);
    setCurrentStage((prev) => (prev % 4) + 1);
  };

  const handleSelectStage = (idx) => {
    setIsPlaying(false);
    setCurrentStage(idx);
  };

  const handleLaunchCaseStudy = () => {
    navigate(
      `/dashboard?address=0x62425cd6bdcb6bfe51558ea465b063486b70dc9f&chain=1`
    );
  };

  return (
    <section
      id="interactive-simulation"
      ref={containerRef}
      className="py-16 px-4 lg:px-6 relative scroll-mt-20"
    >
      <div className="max-w-6xl mx-auto space-y-10">
        {/* Section Header */}
        <div className="text-center space-y-3 max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-cyan-100 dark:bg-cyan-950/40 border border-cyan-300 dark:border-cyan-500/30 text-cyan-700 dark:text-cyan-400 text-xs font-mono">
            <span>Visual Demonstration</span>
            <span className="text-slate-400 dark:text-zinc-500">•</span>
            <span>The Core Insight in Action</span>
          </div>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 dark:text-zinc-100">
            How ChainSAHYOG Solves the Blockchain Money Trail
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-zinc-400 leading-relaxed">
            Follow a real 500 ETH cyber-fraud incident through unhosted burner wallets to the
            centralized exchange chokepoint that unmasks the human behind the heist.
          </p>
        </div>

        {/* Stepper Navigation Bar */}
        <div className="flex flex-wrap items-center justify-between gap-2 p-2 rounded-2xl bg-slate-100 dark:bg-zinc-900/80 border border-slate-200 dark:border-zinc-800">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 w-full md:w-auto flex-1">
            {STAGES.map((s) => {
              const Icon = s.icon;
              const isSelected = s.id === currentStage;
              return (
                <button
                  key={s.id}
                  onClick={() => handleSelectStage(s.id)}
                  className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all text-left cursor-pointer ${
                    isSelected
                      ? 'bg-white dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 border border-cyan-500/40 shadow-sm dark:shadow-cyan-950/40'
                      : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200 hover:bg-slate-200/50 dark:hover:bg-zinc-800/40 border border-transparent'
                  }`}
                >
                  <span
                    className={`w-6 h-6 rounded-lg flex items-center justify-center shrink-0 ${
                      isSelected
                        ? 'bg-cyan-500/20 text-cyan-600 dark:text-cyan-400'
                        : 'bg-slate-200 dark:bg-zinc-800 text-slate-500 dark:text-zinc-500'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                  </span>
                  <div className="truncate">
                    <span className="text-[10px] block font-mono text-slate-500 dark:text-zinc-500 uppercase">
                      Step 0{s.id}
                    </span>
                    <span className="truncate block font-semibold text-slate-800 dark:text-zinc-200">
                      {s.badge}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Play/Pause & Reset Controls */}
          <div className="flex items-center gap-2 mx-auto md:mx-0 pt-2 md:pt-0 border-t md:border-t-0 border-slate-200 dark:border-zinc-800 w-full md:w-auto justify-end">
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              className="p-2 rounded-lg bg-white dark:bg-zinc-800 hover:bg-slate-100 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300 hover:text-slate-900 dark:hover:text-white border border-slate-200 dark:border-transparent transition-colors cursor-pointer"
              title={isPlaying ? 'Pause Auto-Play' : 'Start Auto-Play'}
            >
              {isPlaying ? <Pause className="w-4 h-4 text-cyan-500" /> : <Play className="w-4 h-4 text-slate-500 dark:text-zinc-400" />}
            </button>
            <button
              onClick={() => {
                setCurrentStage(1);
                setIsPlaying(false);
              }}
              className="p-2 rounded-lg bg-white dark:bg-zinc-800 hover:bg-slate-100 dark:hover:bg-zinc-700 text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white border border-slate-200 dark:border-transparent transition-colors cursor-pointer"
              title="Reset Simulation"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Visualizer Display Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
          {/* Left Column: Interactive Animated SVG Schematic (7 cols) */}
          <div className="lg:col-span-7 bg-white dark:bg-zinc-950/80 border border-slate-200 dark:border-zinc-800/90 rounded-2xl p-6 flex flex-col justify-between relative overflow-hidden shadow-sm dark:shadow-2xl">
            {/* Visual Header */}
            <div className="flex items-center justify-between z-10">
              <span className="text-xs font-mono text-slate-600 dark:text-zinc-400 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-cyan-500" />
                Live Heist Flow Graph
              </span>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-slate-600 dark:text-zinc-400">
                Ethereum Mainnet (Chain 1)
              </span>
            </div>

            {/* SVG Diagram Canvas */}
            <div className="my-6 flex items-center justify-center">
              <svg
                viewBox="0 0 600 320"
                className="w-full max-w-lg h-auto overflow-visible select-none"
              >
                <defs>
                  {/* Glowing filters */}
                  <filter id="glow-red" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="0" dy="0" stdDeviation="6" floodColor="#ef4444" floodOpacity="0.8" />
                  </filter>
                  <filter id="glow-amber" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="0" dy="0" stdDeviation="6" floodColor="#f59e0b" floodOpacity="0.8" />
                  </filter>
                  <filter id="glow-emerald" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="0" dy="0" stdDeviation="8" floodColor="#10b981" floodOpacity="0.9" />
                  </filter>
                  <filter id="glow-cyan" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="0" dy="0" stdDeviation="8" floodColor="#06b6d4" floodOpacity="0.9" />
                  </filter>
                </defs>

                {/* Connecting Edges */}
                {/* Edge 1: Suspect -> Burner 1 */}
                <path
                  d="M 100 160 L 250 80"
                  stroke={currentStage >= 2 ? '#f59e0b' : '#3f3f46'}
                  strokeWidth={currentStage >= 2 ? '3' : '1.5'}
                  strokeDasharray={currentStage >= 2 ? '6 4' : 'none'}
                  className={currentStage >= 2 ? 'animate-pulse' : ''}
                />
                {/* Edge 2: Suspect -> Burner 2 */}
                <path
                  d="M 100 160 L 250 160"
                  stroke={currentStage >= 2 ? '#f59e0b' : '#3f3f46'}
                  strokeWidth={currentStage >= 2 ? '3' : '1.5'}
                  strokeDasharray={currentStage >= 2 ? '6 4' : 'none'}
                />
                {/* Edge 3: Suspect -> Burner 3 */}
                <path
                  d="M 100 160 L 250 240"
                  stroke={currentStage >= 2 ? '#f59e0b' : '#3f3f46'}
                  strokeWidth={currentStage >= 2 ? '3' : '1.5'}
                  strokeDasharray={currentStage >= 2 ? '6 4' : 'none'}
                />

                {/* Edge 4: Burners -> Binance Hub */}
                <path
                  d="M 250 80 L 480 160"
                  stroke={currentStage >= 3 ? '#10b981' : '#3f3f46'}
                  strokeWidth={currentStage >= 3 ? '3.5' : '1.5'}
                  className={currentStage >= 3 ? 'animate-pulse' : ''}
                />
                <path
                  d="M 250 160 L 480 160"
                  stroke={currentStage >= 3 ? '#10b981' : '#3f3f46'}
                  strokeWidth={currentStage >= 3 ? '3.5' : '1.5'}
                />
                <path
                  d="M 250 240 L 480 160"
                  stroke={currentStage >= 3 ? '#10b981' : '#3f3f46'}
                  strokeWidth={currentStage >= 3 ? '3.5' : '1.5'}
                />

                {/* Freezing Order Edge from SAHYOG */}
                {currentStage === 4 && (
                  <path
                    d="M 480 40 L 480 130"
                    stroke="#06b6d4"
                    strokeWidth="3"
                    strokeDasharray="4 3"
                    markerEnd="url(#arrow)"
                  />
                )}

                {/* NODE 1: Suspect Wallet */}
                <g transform="translate(100, 160)">
                  <circle
                    r={currentStage === 1 ? '26' : '20'}
                    fill={currentStage >= 1 ? '#7f1d1d' : '#27272a'}
                    stroke={currentStage >= 1 ? '#ef4444' : '#52525b'}
                    strokeWidth="3"
                    filter={currentStage === 1 ? 'url(#glow-red)' : undefined}
                    className={currentStage === 1 ? 'visualizer-active-node' : ''}
                  />
                  <text y="5" textAnchor="middle" fill="#fff" fontSize="12" fontWeight="bold">
                    SUSPECT
                  </text>
                  <text y="42" textAnchor="middle" fill="#f87171" fontSize="10" fontFamily="monospace">
                    0x6242...dc9f
                  </text>
                  <text y="56" textAnchor="middle" fill="#a1a1aa" fontSize="9">
                    -500 ETH Loot
                  </text>
                </g>

                {/* NODE CLUSTER: Burner Wallets (The Fog) */}
                <g transform="translate(250, 80)">
                  <circle
                    r={currentStage === 2 ? '22' : '16'}
                    fill={currentStage >= 2 ? '#78350f' : '#27272a'}
                    stroke={currentStage >= 2 ? '#f59e0b' : '#52525b'}
                    strokeWidth="2.5"
                    filter={currentStage === 2 ? 'url(#glow-amber)' : undefined}
                    className={currentStage === 2 ? 'visualizer-active-node' : ''}
                  />
                  <text y="4" textAnchor="middle" fill="#fef3c7" fontSize="10" fontWeight="bold">
                    Peel 1
                  </text>
                  <text y="30" textAnchor="middle" fill="#fbbf24" fontSize="8" fontFamily="monospace">
                    0xe463...
                  </text>
                </g>

                <g transform="translate(250, 160)">
                  <circle
                    r={currentStage === 2 ? '22' : '16'}
                    fill={currentStage >= 2 ? '#78350f' : '#27272a'}
                    stroke={currentStage >= 2 ? '#f59e0b' : '#52525b'}
                    strokeWidth="2.5"
                    filter={currentStage === 2 ? 'url(#glow-amber)' : undefined}
                    className={currentStage === 2 ? 'visualizer-active-node' : ''}
                  />
                  <text y="4" textAnchor="middle" fill="#fef3c7" fontSize="10" fontWeight="bold">
                    Layer 2
                  </text>
                  <text y="30" textAnchor="middle" fill="#fbbf24" fontSize="8" fontFamily="monospace">
                    0x9f3f...
                  </text>
                </g>

                <g transform="translate(250, 240)">
                  <circle
                    r={currentStage === 2 ? '22' : '16'}
                    fill={currentStage >= 2 ? '#78350f' : '#27272a'}
                    stroke={currentStage >= 2 ? '#f59e0b' : '#52525b'}
                    strokeWidth="2.5"
                    filter={currentStage === 2 ? 'url(#glow-amber)' : undefined}
                    className={currentStage === 2 ? 'visualizer-active-node' : ''}
                  />
                  <text y="4" textAnchor="middle" fill="#fef3c7" fontSize="10" fontWeight="bold">
                    Smurf 3
                  </text>
                  <text y="30" textAnchor="middle" fill="#fbbf24" fontSize="8" fontFamily="monospace">
                    0x7a11...
                  </text>
                </g>

                {/* NODE 3: Regulated VASP Endpoint */}
                <g transform="translate(480, 160)">
                  <circle
                    r={currentStage >= 3 ? '32' : '22'}
                    fill={currentStage >= 3 ? '#064e3b' : '#27272a'}
                    stroke={currentStage >= 3 ? '#10b981' : '#52525b'}
                    strokeWidth={currentStage >= 3 ? '3.5' : '2'}
                    filter={currentStage >= 3 ? 'url(#glow-emerald)' : undefined}
                    className={currentStage === 3 ? 'visualizer-active-node' : ''}
                  />
                  <text y="-2" textAnchor="middle" fill="#fff" fontSize="11" fontWeight="extrabold">
                    BINANCE
                  </text>
                  <text y="12" textAnchor="middle" fill="#6ee7b7" fontSize="9" fontWeight="medium">
                    Deposit Hub
                  </text>
                  <text y="46" textAnchor="middle" fill="#34d399" fontSize="10" fontFamily="monospace">
                    0x28c6...1d60
                  </text>
                  <text y="60" textAnchor="middle" fill="#a1a1aa" fontSize="9">
                    Attributed: 100.96 ETH
                  </text>
                </g>

                {/* STAGE 4 OVERLAY: SAHYOG Lawful Interception Notice */}
                {currentStage === 4 && (
                  <g transform="translate(480, 40)">
                    <rect
                      x="-85"
                      y="-25"
                      width="170"
                      height="38"
                      rx="8"
                      fill="#083344"
                      stroke="#06b6d4"
                      strokeWidth="2"
                      filter="url(#glow-cyan)"
                    />
                    <text y="-7" textAnchor="middle" fill="#67e8f9" fontSize="10" fontWeight="bold">
                      ⚖️ SEC 91 CrPC NOTICE
                    </text>
                    <text y="7" textAnchor="middle" fill="#e0f2fe" fontSize="9">
                      Account Freeze Order
                    </text>
                  </g>
                )}
              </svg>
            </div>

            {/* Bottom Insight Pill */}
            <div className="bg-slate-100 dark:bg-zinc-900/90 border border-slate-200 dark:border-zinc-800 p-3 rounded-xl flex items-center justify-between text-xs">
              <span className="text-slate-500 dark:text-zinc-400 font-mono">
                Attribution Status:
              </span>
              <span
                className={`font-semibold ${
                  currentStage === 1
                    ? 'text-red-600 dark:text-red-400'
                    : currentStage === 2
                    ? 'text-amber-600 dark:text-amber-400'
                    : currentStage === 3
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : 'text-cyan-600 dark:text-cyan-400'
                }`}
              >
                {currentStage === 1 && '🚨 Unhosted Wallet Identified (Zero KYC)'}
                {currentStage === 2 && '⚠️ Obfuscation Active: 12 Burner Hops'}
                {currentStage === 3 && '🎯 VASP Reached: Binance (88% Confidence)'}
                {currentStage === 4 && '🔒 Funds Frozen & KYC Unmasked'}
              </span>
            </div>
          </div>

          {/* Right Column: Detailed Narrative & Dilemma Breakdown (5 cols) */}
          <div className="lg:col-span-5 flex flex-col justify-between bg-white dark:bg-zinc-900/60 border border-slate-200 dark:border-zinc-800/80 rounded-2xl p-6 space-y-6 shadow-sm dark:shadow-none">
            <div className="stage-info-content space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono px-2.5 py-1 rounded-md bg-slate-100 dark:bg-zinc-800 text-cyan-700 dark:text-cyan-400 font-semibold uppercase">
                  {active.tag}
                </span>
                <span className="text-xs text-slate-400 dark:text-zinc-500 font-mono">
                  {currentStage} of 4
                </span>
              </div>

              <h3 className="text-xl font-bold text-slate-900 dark:text-zinc-100 leading-snug">
                {active.title}
              </h3>

              <div className="space-y-1">
                <span className="text-[11px] font-mono text-slate-500 dark:text-zinc-500 block">
                  Observed Address:
                </span>
                <p className="font-mono text-xs text-slate-800 dark:text-zinc-300 bg-slate-50 dark:bg-zinc-950 p-2.5 rounded-lg border border-slate-200 dark:border-zinc-800 break-all select-all">
                  {active.address}
                </p>
              </div>

              <p className="text-xs sm:text-sm text-slate-600 dark:text-zinc-300 leading-relaxed">
                {active.desc}
              </p>

              <div className="bg-slate-50 dark:bg-zinc-950/80 border border-slate-200 dark:border-zinc-800/90 rounded-xl p-3.5 space-y-1.5">
                <span className="text-xs font-semibold text-slate-800 dark:text-zinc-200 flex items-center gap-1.5">
                  <HelpCircle className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
                  Investigative Significance
                </span>
                <p className="text-xs text-slate-600 dark:text-zinc-400 leading-relaxed">
                  {active.lawEnforcementDilemma}
                </p>
              </div>
            </div>

            {/* Action Bar */}
            <div className="space-y-3 pt-4 border-t border-slate-200 dark:border-zinc-800">
              <button
                onClick={handleNext}
                className="w-full flex items-center justify-center gap-2 bg-slate-100 dark:bg-zinc-800 hover:bg-slate-200 dark:hover:bg-zinc-700 text-slate-800 dark:text-zinc-100 font-semibold text-xs sm:text-sm py-2.5 px-4 rounded-xl border border-slate-300 dark:border-zinc-700 transition-colors cursor-pointer"
              >
                <span>{active.actionLabel}</span>
              </button>

              <button
                onClick={handleLaunchCaseStudy}
                className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold text-xs py-2.5 px-4 rounded-xl shadow-lg shadow-emerald-950/30 transition-all cursor-pointer"
              >
                <span>Launch Live Forensic Trace of this Case</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
