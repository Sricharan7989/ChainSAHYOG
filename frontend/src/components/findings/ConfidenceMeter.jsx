import { useState, useRef } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(useGSAP);

export default function ConfidenceMeter({ score, breakdown, components, method }) {
  const [expanded, setExpanded] = useState(false);
  const [displayScore, setDisplayScore] = useState(0);
  const containerRef = useRef(null);
  const circleRef = useRef(null);

  const hasScore = typeof score === 'number';
  const targetScore = hasScore ? score : 0;
  // What the number rests on. A fan-in pattern is a behavioural resemblance,
  // not a match against published exchange infrastructure, and a trace that
  // recognised nothing has no score at all - not a score of zero.
  const basis = !hasScore
    ? 'No endpoint was attributed, so there is no confidence score.'
    : method === 'known_label'
      ? 'Exact match against published exchange labels, adjusted for hop distance and path.'
      : method === 'inferred_label'
        ? 'Name inferred from the same address on Ethereum; no label on this chain. Capped at 80%.'
        : method === 'consolidation'
        ? 'Fan-in (consolidation) pattern only; no published label. Capped at 67%.'
        : `Identified by ${method || 'an unrecorded method'}, adjusted for hop distance and path.`;

  useGSAP(() => {
    const counterObj = { val: 0 };

    gsap.to(counterObj, {
      val: targetScore,
      duration: 1.0,
      ease: 'power3.out',
      onUpdate: () => {
        setDisplayScore(Math.round(counterObj.val));
      },
    });

    if (circleRef.current) {
      const radius = 34;
      const circumference = 2 * Math.PI * radius;
      const strokeDashoffset = circumference - (targetScore / 100) * circumference;

      gsap.fromTo(
        circleRef.current,
        { strokeDashoffset: circumference },
        { strokeDashoffset, duration: 1.0, ease: 'power3.out' }
      );
    }
  }, { dependencies: [targetScore], scope: containerRef });

  const getScoreColor = (val) => {
    if (val >= 80) return 'text-emerald-500 stroke-emerald-500';
    if (val >= 60) return 'text-amber-500 stroke-amber-500';
    return 'text-[#71717a] stroke-[#71717a]';
  };

  const radius = 34;
  const circumference = 2 * Math.PI * radius;

  return (
    <div
      ref={containerRef}
      className="bg-white dark:bg-[#111111] border border-[#d4d4d8] dark:border-[#262626] p-4 sm:p-5 transition-all shadow-[3px_3px_0px_#18181b] dark:shadow-[3px_3px_0px_#000000]"
    >
      <div className="flex items-center justify-between">
        {/* Left: Gauge and Metric */}
        <div className="flex items-center gap-3.5">
          <div className="relative w-16 h-16 flex items-center justify-center shrink-0">
            <svg className="w-16 h-16 -rotate-90 transform" viewBox="0 0 80 80">
              <circle
                cx="40"
                cy="40"
                r={radius}
                className="stroke-[#e4e4e7] dark:stroke-[#262626]"
                strokeWidth="6"
                fill="transparent"
              />
              <circle
                ref={circleRef}
                cx="40"
                cy="40"
                r={radius}
                className={`transition-all duration-300 ${getScoreColor(targetScore)}`}
                strokeWidth="6"
                strokeDasharray={circumference}
                strokeDashoffset={circumference}
                fill="transparent"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="font-mono text-base sm:text-lg font-extrabold tracking-tight text-[#09090b] dark:text-[#f5f5f5]">
                {hasScore ? `${displayScore}%` : '—'}
              </span>
            </div>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5]">Attribution Certainty</h3>
              <span className="text-[10px] font-mono px-1.5 py-0.5 bg-[#f4f4f5] dark:bg-[#1a1a1a] text-emerald-700 dark:text-emerald-400 border border-[#d4d4d8] dark:border-[#262626] font-semibold uppercase">
                {!hasScore ? 'None' : targetScore >= 80 ? 'High' : targetScore >= 60 ? 'Moderate' : 'Tentative'}
              </span>
            </div>
            <p className="text-[11px] text-[#52525b] dark:text-[#a3a3a3] mt-0.5 leading-snug">
              {basis}
            </p>
          </div>
        </div>

        {/* Right: Expand Toggle */}
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-[11px] font-mono font-semibold text-[#627EEA] hover:text-[#5068cf] bg-[#f4f4f5] dark:bg-[#1a1a1a] hover:bg-[#e4e4e7] dark:hover:bg-[#262626] px-2.5 py-1.5 border border-[#d4d4d8] dark:border-[#262626] transition-all cursor-pointer brutal-press shrink-0"
        >
          <span>{expanded ? 'Hide Factors' : 'Audit Factors'}</span>
          {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Expandable Breakdown Drawer */}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-[#d4d4d8] dark:border-[#262626] space-y-2.5 animate-in fade-in duration-150">
          <div className="text-xs text-[#52525b] dark:text-[#a3a3a3] font-mono bg-[#f4f4f5] dark:bg-[#0a0a0a] p-2.5 border border-[#d4d4d8] dark:border-[#262626]">
            {breakdown || (hasScore ? 'No score breakdown was supplied with this result.' : 'Nothing was scored.')}
          </div>

          {components && components.length > 0 && (
            <div className="space-y-1 font-mono">
              <span className="text-[10px] font-semibold text-[#71717a] dark:text-[#666666] uppercase tracking-wider block">
                Rule-Based Scoring Breakdown:
              </span>
              <div className="space-y-1">
                {components.map((c, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] text-xs"
                  >
                    <div>
                      <span className="font-semibold text-[#09090b] dark:text-[#f5f5f5] block">{c.name || c.label}</span>
                      {c.reason && <span className="text-[10px] text-[#71717a] dark:text-[#666666]">{c.reason}</span>}
                    </div>
                    <span
                      className={`font-mono font-bold ${
                        c.points > 0 ? 'text-emerald-600 dark:text-emerald-400' : c.points < 0 ? 'text-red-500' : 'text-[#71717a]'
                      }`}
                    >
                      {c.points > 0 ? `+${c.points}` : c.points}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
