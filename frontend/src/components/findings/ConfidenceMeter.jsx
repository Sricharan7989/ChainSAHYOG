import { useState, useRef } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(useGSAP);

export default function ConfidenceMeter({ score, breakdown, components }) {
  const [expanded, setExpanded] = useState(false);
  const [displayScore, setDisplayScore] = useState(0);
  const containerRef = useRef(null);
  const circleRef = useRef(null);

  const targetScore = typeof score === 'number' ? score : 0;

  useGSAP(() => {
    const counterObj = { val: 0 };

    // GSAP tween for fluid number counting
    gsap.to(counterObj, {
      val: targetScore,
      duration: 1.2,
      ease: 'power3.out',
      onUpdate: () => {
        setDisplayScore(Math.round(counterObj.val));
      },
    });

    // Animate radial circle stroke
    if (circleRef.current) {
      const radius = 38;
      const circumference = 2 * Math.PI * radius;
      const strokeDashoffset = circumference - (targetScore / 100) * circumference;

      gsap.fromTo(
        circleRef.current,
        { strokeDashoffset: circumference },
        { strokeDashoffset, duration: 1.2, ease: 'power3.out' }
      );
    }
  }, { dependencies: [targetScore], scope: containerRef });

  const getScoreColor = (val) => {
    if (val >= 80) return 'text-emerald-500 stroke-emerald-500';
    if (val >= 60) return 'text-amber-500 stroke-amber-500';
    return 'text-slate-500 stroke-slate-500';
  };

  const radius = 38;
  const circumference = 2 * Math.PI * radius;

  return (
    <div
      ref={containerRef}
      className="bg-white dark:bg-zinc-900/90 border border-slate-200 dark:border-zinc-800 rounded-2xl p-5 shadow-sm dark:shadow-xl transition-all"
    >
      <div className="flex items-center justify-between">
        {/* Left: Gauge and Metric */}
        <div className="flex items-center gap-4">
          <div className="relative w-20 h-20 flex items-center justify-center flex-shrink-0">
            <svg className="w-20 h-20 -rotate-90 transform" viewBox="0 0 90 90">
              <circle
                cx="45"
                cy="45"
                r={radius}
                className="stroke-slate-200 dark:stroke-zinc-800"
                strokeWidth="7"
                fill="transparent"
              />
              <circle
                ref={circleRef}
                cx="45"
                cy="45"
                r={radius}
                className={`transition-all duration-300 ${getScoreColor(targetScore)}`}
                strokeWidth="7"
                strokeDasharray={circumference}
                strokeDashoffset={circumference}
                strokeLinecap="round"
                fill="transparent"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="font-mono text-xl font-bold tracking-tight text-slate-900 dark:text-zinc-100">
                {displayScore}%
              </span>
            </div>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-sm text-slate-900 dark:text-zinc-100">Attribution Confidence</h3>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 border border-slate-200 dark:border-zinc-700 font-semibold">
                Auditable
              </span>
            </div>
            <span className="text-xs font-mono text-cyan-600 dark:text-cyan-400 mt-0.5 block">
              Dynamic rule-based score
            </span>
          </div>
        </div>

        {/* Right: Expand Toggle */}
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs font-semibold text-cyan-700 dark:text-cyan-400 hover:text-cyan-800 dark:hover:text-cyan-300 bg-cyan-50 dark:bg-cyan-500/10 hover:bg-cyan-100 dark:hover:bg-cyan-500/20 px-3 py-1.5 rounded-lg border border-cyan-300 dark:border-cyan-500/30 transition-all cursor-pointer"
        >
          <span>{expanded ? 'Hide Factors' : 'Score Factors'}</span>
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {/* Expandable Breakdown Drawer */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-slate-200 dark:border-zinc-800 space-y-3 animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="text-xs text-slate-800 dark:text-zinc-300 font-mono bg-slate-50 dark:bg-zinc-950 p-2.5 rounded-lg border border-slate-200 dark:border-zinc-800">
            {breakdown || 'Score calculated from verified address match and hop attenuation.'}
          </div>

          {components && components.length > 0 && (
            <div className="space-y-1.5">
              <span className="text-[11px] font-semibold text-slate-500 dark:text-zinc-500 uppercase tracking-wider block">
                Arithmetic Components:
              </span>
              <div className="space-y-1">
                {components.map((c, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 rounded-md bg-slate-50/70 dark:bg-zinc-950/60 border border-slate-200 dark:border-zinc-800/80 text-xs"
                  >
                    <div>
                      <span className="font-medium text-slate-800 dark:text-zinc-200 block">{c.name}</span>
                      <span className="text-[11px] text-slate-500 dark:text-zinc-500">{c.reason}</span>
                    </div>
                    <span
                      className={`font-mono font-bold ${
                        c.points > 0 ? 'text-emerald-600 dark:text-emerald-400' : c.points < 0 ? 'text-red-600 dark:text-red-400' : 'text-slate-600 dark:text-zinc-400'
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
