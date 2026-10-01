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
    desc: 'Applies Clayton’s Case accounting and detects laundering patterns (peel chains, smurfing, conduits).',
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
    title: 'SAHYOG Freezing Notice',
    desc: 'Generates Section 91 CrPC / Section 94 BNSS statutory requisition and court-ready PDF dossier.',
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
    <section id="workflow" ref={containerRef} className="py-16 px-4 lg:px-6 relative scroll-mt-20">
      <div className="max-w-6xl mx-auto space-y-12">
        {/* Title */}
        <div className="text-center space-y-3 max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-100 dark:bg-blue-950/40 border border-blue-300 dark:border-blue-500/30 text-blue-700 dark:text-blue-400 text-xs font-mono">
            <span>Investigative Lifecycle</span>
            <span className="text-slate-400 dark:text-zinc-500">•</span>
            <span>From Alert to Freezing</span>
          </div>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 dark:text-zinc-100">
            How Law Enforcement Operates ChainSAHYOG
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-zinc-400 leading-relaxed">
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
                className="workflow-step-card bg-white dark:bg-zinc-950/80 border border-slate-200 dark:border-zinc-800 rounded-2xl p-5 flex flex-col justify-between space-y-4 hover:border-cyan-500/40 transition-colors shadow-sm dark:shadow-none relative"
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-cyan-600 dark:text-cyan-400">
                      STEP {s.step}
                    </span>
                    <div className="w-8 h-8 rounded-lg bg-slate-100 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 flex items-center justify-center text-slate-700 dark:text-zinc-300">
                      <Icon className="w-4 h-4" />
                    </div>
                  </div>

                  <h3 className="font-bold text-slate-900 dark:text-zinc-100 text-sm">
                    {s.title}
                  </h3>

                  <p className="text-xs text-slate-600 dark:text-zinc-400 leading-relaxed">
                    {s.desc}
                  </p>
                </div>

                {idx < STEPS.length - 1 && (
                  <div className="hidden md:block absolute -right-3 top-1/2 -translate-y-1/2 z-10 text-slate-400 dark:text-zinc-600">
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
