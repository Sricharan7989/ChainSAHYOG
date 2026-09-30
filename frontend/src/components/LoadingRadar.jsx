import { useState, useEffect, useRef } from 'react';
import { Radar, Cpu } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(useGSAP);

const PHASES = [
  'Querying public blockchain transactions via Etherscan V2…',
  'Following unhosted intermediary wallets forward…',
  'Executing chronological FIFO value taint tracking…',
  'Evaluating laundering typologies (peel chains, layering, structuring)…',
  'Resolving VASP entity clusters & confidence scoring…',
];

export default function LoadingRadar({ address }) {
  const [phaseIndex, setPhaseIndex] = useState(0);
  const containerRef = useRef(null);

  useEffect(() => {
    const timer = setInterval(() => {
      setPhaseIndex((prev) => (prev < PHASES.length - 1 ? prev + 1 : prev));
    }, 1800);
    return () => clearInterval(timer);
  }, []);

  useGSAP(() => {
    // Pulse animation
    gsap.to('.radar-ring', {
      scale: 1.5,
      opacity: 0,
      duration: 2,
      repeat: -1,
      stagger: 0.6,
      ease: 'power1.out',
    });
  }, { scope: containerRef });

  return (
    <div
      ref={containerRef}
      className="h-130 w-full flex flex-col items-center justify-center bg-slate-50/70 dark:bg-zinc-950/60 border border-slate-200 dark:border-zinc-800/80 rounded-2xl p-8 backdrop-blur-sm relative overflow-hidden"
    >
      {/* Background glowing sweep */}
      <div className="absolute inset-0 flex items-center justify-center opacity-30 pointer-events-none">
        <div className="radar-ring absolute w-48 h-48 rounded-full border border-cyan-500/40 dark:border-cyan-500/50"></div>
        <div className="radar-ring absolute w-48 h-48 rounded-full border border-cyan-500/40 dark:border-cyan-500/50"></div>
        <div className="radar-ring absolute w-48 h-48 rounded-full border border-cyan-500/40 dark:border-cyan-500/50"></div>
      </div>

      {/* Center Radar Scanner */}
      <div className="relative z-10 w-24 h-24 rounded-full bg-white dark:bg-zinc-900 border border-cyan-400/50 dark:border-cyan-500/40 flex items-center justify-center shadow-xl shadow-cyan-500/10 dark:shadow-2xl dark:shadow-cyan-500/20 mb-6">
        <div className="w-16 h-16 rounded-full bg-cyan-50 dark:bg-cyan-950/40 flex items-center justify-center border border-cyan-200 dark:border-cyan-400/30">
          <Radar className="w-8 h-8 text-cyan-600 dark:text-cyan-400 animate-spin [animation-duration:4s]" />
        </div>
      </div>

      {/* Target Address Under Investigation */}
      <div className="relative z-10 text-center mb-6">
        <span className="text-xs uppercase tracking-widest text-slate-500 dark:text-zinc-500 font-semibold block mb-1">
          Forensic Trail In Progress
        </span>
        <code className="text-xs sm:text-sm font-mono text-cyan-700 dark:text-cyan-300 bg-white dark:bg-zinc-900/90 px-3 py-1 rounded-md border border-slate-200 dark:border-zinc-800 shadow-xs">
          {address}
        </code>
      </div>

      {/* Phase status indicator */}
      <div className="relative z-10 w-full max-w-md bg-white dark:bg-zinc-900/80 border border-slate-200 dark:border-zinc-800 rounded-xl p-4 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 rounded-full bg-cyan-500/10 dark:bg-cyan-500/20 text-cyan-600 dark:text-cyan-400 flex items-center justify-center shrink-0 animate-pulse">
            <Cpu className="w-3.5 h-3.5" />
          </div>
          <p className="text-xs sm:text-sm font-medium text-slate-800 dark:text-zinc-200 transition-all duration-300">
            {PHASES[phaseIndex]}
          </p>
        </div>

        {/* Progress bar */}
        <div className="w-full bg-slate-200 dark:bg-zinc-800 h-1.5 rounded-full mt-3 overflow-hidden">
          <div
            className="bg-linear-to-r from-cyan-500 to-blue-500 h-full rounded-full transition-all duration-500 ease-out"
            style={{ width: `${((phaseIndex + 1) / PHASES.length) * 100}%` }}
          />
        </div>
      </div>

      <p className="relative z-10 text-[11px] text-slate-500 dark:text-zinc-500 mt-4 text-center max-w-sm">
        Following public on-chain transfers forward to recognizable KYC-regulated VASP endpoints.
      </p>
    </div>
  );
}
