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
    desc: 'An unhosted private key executes an unauthorized transfer of 500 ETH (~₹13.5 Cr). Unhosted wallets are generated locally without KYC, central ownership, or user identity records.',
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
    desc: 'To convert crypto into Indian Rupees (INR) via bank accounts, funds are deposited into a centralized exchange. ChainSAHYOG tracks the path directly to Binance with 88% confidence and FIFO taint accounting.',
    lawEnforcementDilemma:
      'Centralized exchanges are regulated financial entities. They cluster deposit addresses and maintain mandatory KYC identity records.',
    actionLabel: 'Generate Lawful Requisition →',
  },
  {
    id: 4,
    title: 'Enforcement Action: Lawful Account Freezing Notice',
    tag: 'Step 04 • Actionable Output',
    icon: FileCheck2,
    color: 'cyan',
    badge: 'Case Dossier',
    address: 'Exchange Compliance Desk • Request #I4C-CYBER-8842',
    desc: 'ChainSAHYOG generates a court-ready forensic PDF and statutory notice. Police serve the notice to the exchange compliance desk to freeze accounts and obtain verified KYC (PAN, Aadhaar, bank accounts, IP logs) as a lawful request under the applicable provisions of the Bharatiya Nagarik Suraksha Sanhita, 2023 and the Information Technology Act, 2000.',
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
          <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-[#ffffff] dark:bg-[#111111] border border-[#18181b] dark:border-[#627EEA]/40 text-[#627EEA] text-xs font-mono shadow-[2px_2px_0px_#627EEA]">
            <span>Visual Demonstration</span>
            <span className="text-[#a1a1aa] dark:text-[#555555]">•</span>
            <span>The Core Insight in Action</span>
          </div>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-[#09090b] dark:text-[#f5f5f5]">
            How ChainSAHYOG Solves the Blockchain Money Trail
          </h2>
          <p className="text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3] leading-relaxed">
            Follow a real 500 ETH (~₹13.5 Cr) cyber-fraud incident through unhosted burner wallets to the
            centralized exchange chokepoint that unmasks the human behind the heist.
          </p>
        </div>

        {/* Stepper Navigation Bar */}
        <div className="flex flex-wrap items-center justify-between gap-2 p-2 bg-[#ffffff] dark:bg-[#111111] border-2 border-[#18181b] dark:border-[#262626] shadow-[3px_3px_0px_#18181b] dark:shadow-[3px_3px_0px_#000]">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 w-full md:w-auto flex-1">
            {STAGES.map((s) => {
              const Icon = s.icon;
              const isSelected = s.id === currentStage;
              return (
                <button
                  key={s.id}
                  onClick={() => handleSelectStage(s.id)}
                  className={`flex items-center gap-2.5 px-3.5 py-2.5 text-xs font-medium transition-all text-left cursor-pointer brutal-press ${
                    isSelected
                      ? 'bg-[#f4f4f5] dark:bg-[#1a1a1a] text-[#09090b] dark:text-[#f5f5f5] border border-[#627EEA] shadow-[2px_2px_0px_#627EEA]'
                      : 'text-[#71717a] dark:text-[#a3a3a3] hover:text-[#09090b] dark:hover:text-[#f5f5f5] hover:bg-[#f4f4f5] dark:hover:bg-[#161616] border border-transparent'
                  }`}
                >
                  <span
                    className={`w-6 h-6 flex items-center justify-center shrink-0 border ${
                      isSelected
                        ? 'bg-[#627EEA] text-white border-[#627EEA]'
                        : 'bg-[#ffffff] dark:bg-[#111111] text-[#71717a] dark:text-[#666666] border-[#18181b] dark:border-[#262626]'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                  </span>
                  <div className="truncate">
                    <span className="text-[10px] block font-mono text-[#71717a] dark:text-[#666666] uppercase">
                      Step 0{s.id}
                    </span>
                    <span className="truncate block font-semibold text-[#09090b] dark:text-[#f5f5f5]">
                      {s.badge}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Play/Pause & Reset Controls */}
          <div className="flex items-center gap-2 mx-auto md:mx-0 pt-2 md:pt-0 border-t md:border-t-0 border-[#18181b] dark:border-[#262626] w-full md:w-auto justify-end">
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              className="p-2 bg-[#ffffff] dark:bg-[#111111] hover:bg-[#f4f4f5] dark:hover:bg-[#1a1a1a] text-[#09090b] dark:text-[#a3a3a3] hover:text-[#627EEA] border border-[#18181b] dark:border-[#262626] hover:border-[#627EEA] transition-colors cursor-pointer brutal-press"
              title={isPlaying ? 'Pause Auto-Play' : 'Start Auto-Play'}
            >
              {isPlaying ? <Pause className="w-4 h-4 text-[#627EEA]" /> : <Play className="w-4 h-4 text-[#71717a] dark:text-[#a3a3a3]" />}
            </button>
            <button
              onClick={() => {
                setCurrentStage(1);
                setIsPlaying(false);
              }}
              className="p-2 bg-[#ffffff] dark:bg-[#111111] hover:bg-[#f4f4f5] dark:hover:bg-[#1a1a1a] text-[#09090b] dark:text-[#a3a3a3] hover:text-[#627EEA] border border-[#18181b] dark:border-[#262626] hover:border-[#627EEA] transition-colors cursor-pointer brutal-press"
              title="Reset Simulation"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Visualizer Display Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
          {/* Left Column: Interactive Animated SVG Schematic (7 cols) */}
          <div className="lg:col-span-7 bg-[#ffffff] dark:bg-[#111111] border-2 border-[#18181b] dark:border-[#262626] p-6 flex flex-col justify-between relative overflow-hidden shadow-[4px_4px_0px_#18181b] dark:shadow-[4px_4px_0px_#000]">
            {/* Visual Header */}
            <div className="flex items-center justify-between z-10">
              <span className="text-xs font-mono text-[#52525b] dark:text-[#a3a3a3] flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#627EEA]" />
                Live Flow Graph
              </span>
              <span className="text-[11px] font-mono px-2 py-0.5 bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#18181b] dark:border-[#262626] text-[#09090b] dark:text-[#a3a3a3]">
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
                  <filter id="glow-purple" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="0" dy="0" stdDeviation="8" floodColor="#627EEA" floodOpacity="0.9" />
                  </filter>
                </defs>

                {/* Connecting Edges */}
                <path
                  d="M 100 160 L 250 80"
                  stroke={currentStage >= 2 ? '#f59e0b' : '#71717a'}
                  strokeWidth={currentStage >= 2 ? '3' : '1.5'}
                  strokeDasharray={currentStage >= 2 ? '6 4' : 'none'}
                  className={currentStage >= 2 ? 'animate-pulse' : ''}
                />
                <path
                  d="M 100 160 L 250 160"
                  stroke={currentStage >= 2 ? '#f59e0b' : '#71717a'}
                  strokeWidth={currentStage >= 2 ? '3' : '1.5'}
                  strokeDasharray={currentStage >= 2 ? '6 4' : 'none'}
                />
                <path
                  d="M 100 160 L 250 240"
                  stroke={currentStage >= 2 ? '#f59e0b' : '#71717a'}
                  strokeWidth={currentStage >= 2 ? '3' : '1.5'}
                  strokeDasharray={currentStage >= 2 ? '6 4' : 'none'}
                />

                {/* Edges to Binance Hub */}
                <path
                  d="M 250 80 L 480 160"
                  stroke={currentStage >= 3 ? '#10b981' : '#71717a'}
                  strokeWidth={currentStage >= 3 ? '3.5' : '1.5'}
                  className={currentStage >= 3 ? 'animate-pulse' : ''}
                />
                <path
                  d="M 250 160 L 480 160"
                  stroke={currentStage >= 3 ? '#10b981' : '#71717a'}
                  strokeWidth={currentStage >= 3 ? '3.5' : '1.5'}
                />
                <path
                  d="M 250 240 L 480 160"
                  stroke={currentStage >= 3 ? '#10b981' : '#71717a'}
                  strokeWidth={currentStage >= 3 ? '3.5' : '1.5'}
                />

                {/* Freezing Order Edge from SAHYOG */}
                {currentStage === 4 && (
                  <path
                    d="M 480 40 L 480 130"
                    stroke="#627EEA"
                    strokeWidth="3"
                    strokeDasharray="4 3"
                  />
                )}

                {/* NODE 1: Suspect Wallet */}
                <g transform="translate(100, 160)">
                  <circle
                    r={currentStage === 1 ? '28' : '20'}
                    fill={currentStage >= 1 ? '#7f1d1d' : '#27272a'}
                    stroke={currentStage >= 1 ? '#ef4444' : '#52525b'}
                    strokeWidth="3"
                    filter={currentStage === 1 ? 'url(#glow-red)' : undefined}
                    className={currentStage === 1 ? 'visualizer-active-node' : ''}
                  />
                  <text y="5" textAnchor="middle" fill="#fff" fontSize="10" fontWeight="bold">
                    SUSPECT
                  </text>
                  <text y="42" textAnchor="middle" fill="#f87171" fontSize="10" fontFamily="monospace">
                    0x6242...dc9f
                  </text>
                  <text y="56" textAnchor="middle" fill="#a1a1aa" fontSize="9" fontFamily="monospace">
                    -500 ETH (₹13.5 Cr)
                  </text>
                </g>

                {/* NODE CLUSTER: Burner Wallets */}
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
                    r={currentStage >= 3 ? '32' : '25'}
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
                  <text y="60" textAnchor="middle" fill="#a1a1aa" fontSize="9" fontFamily="monospace">
                    Attributed: 100.96 ETH
                  </text>
                </g>

                {/* STAGE 4 OVERLAY: Account Freezing Order */}
                {currentStage === 4 && (
                  <g transform="translate(480, 40)">
                    <rect
                      x="-95"
                      y="-25"
                      width="190"
                      height="40"
                      rx="0"
                      fill="#181e3a"
                      stroke="#627EEA"
                      strokeWidth="2"
                      filter="url(#glow-purple)"
                    />
                    <text y="-7" textAnchor="middle" fill="#627EEA" fontSize="9.5" fontWeight="bold" fontFamily="monospace">
                      ⚖️ ACCOUNT FREEZE ORDER
                    </text>
                    <text y="7" textAnchor="middle" fill="#e0f2fe" fontSize="8.5">
                      Lawful Request (BNSS / IT Act)
                    </text>
                  </g>
                )}
              </svg>
            </div>

            {/* Bottom Insight Pill */}
            <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#18181b] dark:border-[#262626] p-3 flex items-center justify-between text-xs font-mono">
              <span className="text-[#71717a] dark:text-[#888888]">
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
                    : 'text-[#627EEA]'
                }`}
              >
                {currentStage === 1 && '🚨 Unhosted Wallet Identified (Zero KYC)'}
                {currentStage === 2 && '⚠️ Obfuscation Active: 12 Burner Hops'}
                {currentStage === 3 && '🎯 VASP Reached: Binance (88% Confidence)'}
                {currentStage === 4 && '🔒 Funds Frozen & KYC Unmasked'}
              </span>
            </div>
          </div>

          {/* Right Column: Detailed Narrative Breakdown (5 cols) */}
          <div className="lg:col-span-5 flex flex-col justify-between bg-[#ffffff] dark:bg-[#111111] border-2 border-[#18181b] dark:border-[#262626] p-6 space-y-6 shadow-[4px_4px_0px_#18181b] dark:shadow-[4px_4px_0px_#000]">
            <div className="stage-info-content space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono px-2.5 py-1 bg-[#f4f4f5] dark:bg-[#1a1a1a] text-[#627EEA] border border-[#627EEA]/40 font-semibold uppercase">
                  {active.tag}
                </span>
                <span className="text-xs text-[#71717a] dark:text-[#888888] font-mono">
                  {currentStage} of 4
                </span>
              </div>

              <h3 className="text-xl font-bold text-[#09090b] dark:text-[#f5f5f5] leading-snug">
                {active.title}
              </h3>

              <div className="space-y-1">
                <span className="text-[11px] font-mono text-[#71717a] dark:text-[#888888] block">
                  Observed Address:
                </span>
                <p className="font-mono text-xs text-[#09090b] dark:text-[#f5f5f5] bg-[#f4f4f5] dark:bg-[#0a0a0a] p-2.5 border border-[#18181b] dark:border-[#262626] break-all select-all">
                  {active.address}
                </p>
              </div>

              <p className="text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3] leading-relaxed">
                {active.desc}
              </p>

              <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#18181b] dark:border-[#262626] p-3.5 space-y-1.5">
                <span className="text-xs font-semibold text-[#09090b] dark:text-[#f5f5f5] flex items-center gap-1.5 font-mono">
                  <HelpCircle className="w-3.5 h-3.5 text-[#627EEA]" />
                  Investigative Significance
                </span>
                <p className="text-xs text-[#52525b] dark:text-[#a3a3a3] leading-relaxed">
                  {active.lawEnforcementDilemma}
                </p>
              </div>
            </div>

            {/* Action Bar */}
            <div className="space-y-3 pt-4 border-t border-[#18181b] dark:border-[#262626]">
              <button
                onClick={handleNext}
                className="w-full flex items-center justify-center gap-2 bg-[#ffffff] dark:bg-[#1a1a1a] hover:bg-[#f4f4f5] dark:hover:bg-[#262626] text-[#09090b] dark:text-[#f5f5f5] font-semibold text-xs sm:text-sm py-2.5 px-4 border border-[#18181b] dark:border-[#262626] hover:border-[#627EEA] transition-colors cursor-pointer brutal-press"
              >
                <span>{active.actionLabel}</span>
              </button>

              <button
                onClick={handleLaunchCaseStudy}
                className="w-full flex items-center justify-center gap-2 bg-[#18181b] dark:bg-[#627EEA] hover:bg-[#627EEA] dark:hover:bg-[#748ef5] text-white font-semibold text-xs py-2.5 px-4 transition-all cursor-pointer brutal-press shadow-[3px_3px_0px_#000]"
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
