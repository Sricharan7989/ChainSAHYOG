import { useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import {
  Layers,
  Coins,
  Scale,
  Building,
  ShieldAlert,
  Database,
  CheckCircle2,
} from 'lucide-react';

gsap.registerPlugin(useGSAP, ScrollTrigger);

const CAPABILITIES = [
  {
    icon: Layers,
    title: 'Multi-Chain EVM Tracing',
    tag: 'Traversal Engine',
    desc: 'Traces funds across Ethereum, Polygon, BNB Chain, and Arbitrum One up to 6 hops deep.',
    reasoning:
      'Criminals jump across EVM chains to break single-network traces. The engine queries Etherscan V2 with 250ms serial throttling to follow cross-chain hops without hitting API rate limits.',
    bullets: [
      '4 EVM chains supported',
      'Configurable depth (1 to 6 hops)',
      'Dust threshold pruning (< 0.001)',
    ],
  },
  {
    icon: Coins,
    title: 'Contract-Pinned Token Tracking',
    tag: 'Asset Security',
    desc: 'Strictly follows allowlisted stablecoins and wrapped assets (USDT, USDC, DAI, WETH, WBTC).',
    reasoning:
      'Scammers mint fake tokens with spoofed names or malicious transfer hooks. Pinning to verified smart contract addresses and per-chain decimals prevents fake balances from contaminating the trace.',
    bullets: [
      'Verified contract allowlist',
      'Per-chain decimal scaling (6 vs 18)',
      'Scam airdrop rejection',
    ],
  },
  {
    icon: Scale,
    title: 'FIFO Taint Accounting',
    tag: 'Clayton’s Case Precedent',
    desc: 'Calculates the exact stolen satoshis and wei that reached an exchange versus pre-existing wallet funds.',
    reasoning:
      'When stolen crypto mixes with clean funds, we apply the First-In-First-Out rule (Clayton’s Case precedent). The earliest tokens in are treated as the earliest tokens out, delivering court-tested evidence.',
    bullets: [
      'First-In-First-Out chronological replay',
      'Deterministic 5-step tie-breaking',
      'Pre-existing balance disclosure',
    ],
  },
  {
    icon: Building,
    title: 'Entity Resolution & Clustering',
    tag: 'Clustering Heuristic',
    desc: 'Unifies thousands of temporary deposit addresses into single exchange entities like Binance or WazirX.',
    reasoning:
      'Exchanges generate a unique deposit address per user, then sweep funds into cold/hot storage. Our sweep heuristic recognizes these consolidation patterns and applies the minimum hop-distance rule.',
    bullets: [
      'Sweep pattern recognition',
      'Minimum hop rule: min(depth)',
      'Eliminates duplicate clusters',
    ],
  },
  {
    icon: ShieldAlert,
    title: 'Sanctions & Mixer Cross-Referencing',
    tag: 'Risk Scoring',
    desc: 'Flags addresses listed on US Treasury OFAC SDN sanctions lists, mixers, and bridges.',
    reasoning:
      'Mixers like Tornado Cash break chronological linkability. Flagging obfuscators on the trail adjusts the confidence score and warns investigators that the trail passed through a privacy contract.',
    bullets: [
      'US Treasury OFAC SDN matching',
      'Tornado Cash & mixer alerts',
      'Cross-chain bridge detection',
    ],
  },
  {
    icon: Database,
    title: 'Dual Graph Engine & Court Reports',
    tag: 'Forensic Storage',
    desc: 'Stores transaction graphs in Neo4j with in-memory NetworkX fallback, generating downloadable PDF dossiers.',
    reasoning:
      'Neo4j provides persistent graph persistence for deep queries, while NetworkX ensures zero-downtime execution without external databases. ReportLab generates court-admissible dossiers.',
    bullets: [
      'Neo4j with NetworkX fallback',
      'Section 91 CrPC statutory drafting',
      'Court-ready multi-page PDF export',
    ],
  },
];

export default function EngineCapabilitiesSection() {
  const containerRef = useRef(null);

  useGSAP(() => {
    gsap.fromTo(
      '.capability-card',
      { y: 30, opacity: 0 },
      {
        y: 0,
        opacity: 1,
        duration: 0.5,
        stagger: 0.1,
        ease: 'power2.out',
        scrollTrigger: {
          trigger: containerRef.current,
          start: 'top 85%',
          toggleActions: 'play none none none',
        },
      }
    );
  }, { scope: containerRef });

  return (
    <section
      id="capabilities"
      ref={containerRef}
      className="py-16 px-4 lg:px-8 relative scroll-mt-20"
    >
      <div className="max-w-6xl mx-auto space-y-12">
        {/* Title */}
        <div className="text-center space-y-3 max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-cyan-50 dark:bg-cyan-950/60 border border-cyan-200 dark:border-cyan-500/30 text-cyan-700 dark:text-cyan-400 text-xs font-mono">
            <span>Core Architecture</span>
            <span className="text-slate-400 dark:text-zinc-500">•</span>
            <span>Technical Capabilities</span>
          </div>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 dark:text-zinc-100">
            Forensic Intelligence Capabilities
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-zinc-400 leading-relaxed">
            Engineered specifically for the Indian Cybercrime Coordination Centre (I4C) SAHYOG workflow,
            combining graph theory, forensic accounting, and statutory compliance.
          </p>
        </div>

        {/* 6 Capabilities Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {CAPABILITIES.map((cap, i) => {
            const Icon = cap.icon;
            return (
              <div
                key={i}
                className="capability-card bg-white dark:bg-zinc-900/90 border border-slate-200 dark:border-zinc-800 rounded-2xl p-6 flex flex-col justify-between space-y-5 hover:border-cyan-500/50 dark:hover:border-cyan-500/40 transition-all hover:shadow-xl hover:shadow-cyan-500/5 group"
              >
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 flex items-center justify-center text-cyan-600 dark:text-cyan-400 group-hover:scale-105 group-hover:border-cyan-500/40 transition-all">
                      <Icon className="w-5 h-5" />
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 uppercase font-semibold">
                      {cap.tag}
                    </span>
                  </div>

                  <div className="space-y-2">
                    <h3 className="text-lg font-bold text-slate-900 dark:text-zinc-100 group-hover:text-cyan-600 dark:group-hover:text-cyan-400 transition-colors">
                      {cap.title}
                    </h3>
                    <p className="text-xs text-slate-600 dark:text-zinc-300 leading-relaxed font-medium">
                      {cap.desc}
                    </p>
                    <p className="text-[11px] text-slate-500 dark:text-zinc-400 leading-relaxed pt-1">
                      {cap.reasoning}
                    </p>
                  </div>
                </div>

                <div className="space-y-2 pt-3 border-t border-slate-100 dark:border-zinc-800/80">
                  {cap.bullets.map((b, bIdx) => (
                    <div key={bIdx} className="flex items-center gap-2 text-[11px] text-slate-700 dark:text-zinc-300 font-mono">
                      <CheckCircle2 className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400 shrink-0" />
                      <span>{b}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
