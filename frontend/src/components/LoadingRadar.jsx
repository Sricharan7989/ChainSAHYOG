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
      className="h-130 w-full flex flex-col items-center justify-center bg-[#0a0a0a] border border-[#2a2a2a] p-8 relative overflow-hidden"
    >
      {/* Background glowing sweep */}
      <div className="absolute inset-0 flex items-center justify-center opacity-30 pointer-events-none">
        <div className="radar-ring absolute w-48 h-48 brutalist-dot border border-[#637DEB]"></div>
        <div className="radar-ring absolute w-48 h-48 brutalist-dot border border-[#637DEB]"></div>
        <div className="radar-ring absolute w-48 h-48 brutalist-dot border border-[#637DEB]"></div>
      </div>

      {/* Center Radar Scanner */}
      <div className="relative z-10 w-24 h-24 brutalist-dot bg-[#111] border border-[#637DEB] flex items-center justify-center mb-6">
        <div className="w-16 h-16 brutalist-dot bg-[#637DEB20] flex items-center justify-center border border-[#637DEB]">
          <Radar className="w-8 h-8 text-[#637DEB] animate-spin [animation-duration:4s]" />
        </div>
      </div>

      {/* Target Address Under Investigation */}
      <div className="relative z-10 text-center mb-6">
        <span className="text-xs uppercase tracking-widest text-[#666] font-semibold block mb-1">
          Forensic Trail In Progress
        </span>
        <code className="text-xs sm:text-sm font-mono text-[#637DEB] bg-[#111] px-3 py-1 border border-[#2a2a2a]">
          {address}
        </code>
      </div>

      {/* Phase status indicator */}
      <div className="relative z-10 w-full max-w-md bg-[#111] border border-[#2a2a2a] p-4">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 brutalist-dot bg-[#637DEB] flex items-center justify-center shrink-0 animate-pulse text-white">
            <Cpu className="w-3.5 h-3.5" />
          </div>
          <p className="text-xs sm:text-sm font-medium text-[#f5f5f5] transition-all duration-300">
            {PHASES[phaseIndex]}
          </p>
        </div>

        {/* Progress bar */}
        <div className="w-full bg-[#1a1a1a] h-1.5 mt-3 overflow-hidden">
          <div
            className="bg-[#637DEB] h-full transition-all duration-500 ease-out"
            style={{ width: `${((phaseIndex + 1) / PHASES.length) * 100}%` }}
          />
        </div>
      </div>

      <p className="relative z-10 text-[11px] text-[#666] mt-4 text-center max-w-sm">
        Following public on-chain transfers forward to recognizable KYC-regulated VASP endpoints.
      </p>
    </div>
  );
}
