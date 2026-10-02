import { useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import {
  Search,
  Network,
  Cpu,
  Building2,
  FileCheck,
  ArrowRight,
} from 'lucide-react';

gsap.registerPlugin(ScrollTrigger, useGSAP);

const STEPS = [
  {
    step: '01',
    icon: Search,
    title: 'Complaint Intake',
    desc: 'Investigator inputs the suspect EVM address from a 1930 Cybercrime Helpline or FIR report.',
  },
  {
    step: '02',
    icon: Network,
    title: 'Forward Multi-Asset BFS',
    desc: 'Engine follows native coins and pinned ERC-20 tokens forward up to 6 hops with dust floor filtering.',
  },
  {
    step: '03',
    icon: Cpu,
    title: 'FIFO Taint & Typologies',
    desc: 'Applies FIFO ledger accounting and detects laundering patterns (peel chains, smurfing, conduits).',
  },
  {
    step: '04',
    icon: Building2,
    title: 'VASP Chokepoint Identified',
    desc: 'Sweep consolidation heuristic pinpoints the regulated exchange holding the criminal’s deposit account.',
  },
  {
    step: '05',
    icon: FileCheck,
    title: 'Statutory Requisition',
    desc: 'Generates statutory requisitions under Indian cybercrime law & IPC and court-ready dossiers.',
  },
];

export default function WorkflowSection() {
  const containerRef = useRef(null);

  useGSAP(() => {
    gsap.fromTo(
      '.workflow-step-card',
      { y: 25, opacity: 0 },
      {
        y: 0,
        opacity: 1,
        duration: 0.5,
        stagger: 0.12,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: containerRef.current,
          start: 'top 85%',
        },
      }
    );
  }, { scope: containerRef });

  return (
    <section id="workflow" ref={containerRef} className="py-16 px-4 lg:px-6 relative scroll-mt-20 bg-transparent">
      <div className="max-w-6xl mx-auto space-y-12">
        {/* Title */}
        <div className="text-center space-y-3 max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-[#ffffff] dark:bg-[#111111] border border-[#627EEA]/40 text-[#627EEA] text-xs font-mono shadow-[2px_2px_0px_#627EEA]">
            <span>Investigative Lifecycle</span>
            <span className="text-[#a1a1aa] dark:text-[#555555]">•</span>
            <span>From Alert to Freezing</span>
          </div>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-[#09090b] dark:text-[#f5f5f5]">
            How Law Enforcement Operates ChainSAHYOG
          </h2>
          <p className="text-xs sm:text-sm text-[#71717a] dark:text-[#a3a3a3] leading-relaxed">
            Designed for swift execution by investigating officers, transforming raw cryptographic
            transactions into actionable legal requisitions within 60 seconds.
          </p>
        </div>

        {/* 5-Step Pipeline Cards */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {STEPS.map((s, idx) => {
            const Icon = s.icon;
            return (
              <div
                key={idx}
                className="workflow-step-card bg-[#ffffff]/90 dark:bg-[#111111]/90 border border-[#d4d4d8] dark:border-[#262626] p-5 flex flex-col justify-between space-y-4 hover:border-[#627EEA] transition-all relative shadow-[4px_4px_0px_#18181b] dark:shadow-[4px_4px_0px_#000000] hover:shadow-[4px_4px_0px_#627EEA]"
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-[#627EEA]">
                      STEP {s.step}
                    </span>
                    <div className="w-8 h-8 bg-[#f4f4f5] dark:bg-[#1a1a1a] border border-[#d4d4d8] dark:border-[#262626] flex items-center justify-center text-[#71717a] dark:text-[#888888]">
                      <Icon className="w-4 h-4" />
                    </div>
                  </div>

                  <h3 className="font-bold text-[#09090b] dark:text-[#f5f5f5] text-sm">
                    {s.title}
                  </h3>

                  <p className="text-xs text-[#71717a] dark:text-[#a3a3a3] leading-relaxed">
                    {s.desc}
                  </p>
                </div>

                {idx < STEPS.length - 1 && (
                  <div className="hidden md:block absolute -right-3 top-1/2 -translate-y-1/2 z-10 text-[#a1a1aa] dark:text-[#444444]">
                    <ArrowRight className="w-4 h-4" />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
