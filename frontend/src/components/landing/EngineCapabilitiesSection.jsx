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
      'Perpetrators jump across EVM chains to break single-network traces. The engine queries public nodes with serial throttling to follow cross-chain hops without hitting rate limits.',
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
      'Fraudsters mint fake tokens with spoofed names or malicious transfer hooks. Pinning to verified smart contract addresses and per-chain decimals prevents fake balances from contaminating the trace.',
    bullets: [
      'Verified contract allowlist',
      'Per-chain decimal scaling',
      'Scam airdrop rejection',
    ],
  },
  {
    icon: Scale,
    title: 'FIFO Taint Accounting',
    tag: 'Ledger Accounting Math',
    desc: 'Calculates the exact stolen tokens that reached an exchange versus pre-existing wallet funds.',
    reasoning:
      'When stolen crypto mixes with clean funds, we apply the First-In-First-Out rule. The earliest tokens in are treated as the earliest tokens out, delivering auditable forensic evidence for investigation.',
    bullets: [
      'First-In-First-Out chronological replay',
      'Deterministic tie-breaking',
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
    desc: 'Flags addresses listed on law-enforcement blacklists, high-risk mixers, and cross-chain bridges.',
    reasoning:
      'Mixers like Tornado Cash attempt to break chronological linkability. Flagging obfuscators on the trail adjusts the confidence score and alerts investigators that the trail passed through an anonymity contract.',
    bullets: [
      'Law Enforcement Blacklist Matching',
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
      'Neo4j provides persistent graph storage for deep queries, while NetworkX ensures zero-downtime execution. The report generator outputs court-admissible dossiers under Indian cybercrime procedure.',
    bullets: [
      'Neo4j with NetworkX fallback',
      'Statutory Requisitions under Cyber Law & IPC',
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
          <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-[#ffffff] dark:bg-[#111111] border border-[#18181b] dark:border-[#627EEA]/40 text-[#627EEA] text-xs font-mono shadow-[2px_2px_0px_#627EEA]">
            <span>Core Architecture</span>
            <span className="text-[#a1a1aa] dark:text-[#555555]">•</span>
            <span>Technical Capabilities</span>
          </div>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-[#09090b] dark:text-[#f5f5f5]">
            Forensic Intelligence Capabilities
          </h2>
          <p className="text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3] leading-relaxed">
            Engineered specifically for the Indian Cybercrime Coordination Centre (I4C) SAHYOG workflow,
            combining graph theory, forensic accounting, and statutory compliance under Indian law.
          </p>
        </div>

        {/* 6 Capabilities Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {CAPABILITIES.map((cap, i) => {
            const Icon = cap.icon;
            return (
              <div
                key={i}
                className="capability-card bg-[#ffffff] dark:bg-[#111111] border-2 border-[#18181b] dark:border-[#262626] p-6 flex flex-col justify-between space-y-5 hover:border-[#627EEA] dark:hover:border-[#627EEA] transition-all group shadow-[4px_4px_0px_#18181b] dark:shadow-[4px_4px_0px_#000] hover:shadow-[4px_4px_0px_#627EEA]"
              >
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="w-10 h-10 bg-[#f4f4f5] dark:bg-[#1a1a1a] border border-[#18181b] dark:border-[#262626] group-hover:border-[#627EEA] flex items-center justify-center text-[#627EEA] transition-colors">
                      <Icon className="w-5 h-5" />
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 bg-[#f4f4f5] dark:bg-[#1a1a1a] text-[#71717a] dark:text-[#888888] border border-[#18181b] dark:border-[#262626] uppercase font-semibold">
                      {cap.tag}
                    </span>
                  </div>

                  <div className="space-y-2">
                    <h3 className="text-lg font-bold text-[#09090b] dark:text-[#f5f5f5] group-hover:text-[#627EEA] transition-colors">
                      {cap.title}
                    </h3>
                    <p className="text-xs text-[#52525b] dark:text-[#a3a3a3] leading-relaxed font-medium">
                      {cap.desc}
                    </p>
                    <p className="text-[11px] text-[#71717a] dark:text-[#777777] leading-relaxed pt-1">
                      {cap.reasoning}
                    </p>
                  </div>
                </div>

                <div className="space-y-2 pt-3 border-t border-[#18181b] dark:border-[#262626]">
                  {cap.bullets.map((b, bIdx) => (
                    <div key={bIdx} className="flex items-center gap-2 text-[11px] text-[#52525b] dark:text-[#a3a3a3] font-mono">
                      <CheckCircle2 className="w-3.5 h-3.5 text-[#627EEA] shrink-0" />
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
