import { useRef } from 'react';
import { Activity } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(useGSAP);

export default function TypologiesCard({ typologies }) {
  const cardRef = useRef(null);

  useGSAP(() => {
    if (typologies && typologies.length > 0) {
      gsap.from('.typo-card', {
        y: 15,
        opacity: 0,
        stagger: 0.08,
        duration: 0.5,
        ease: 'power2.out',
      });
    }
  }, { dependencies: [typologies], scope: cardRef });

  if (!typologies || typologies.length === 0) {
    return (
      <div className="bg-white dark:bg-zinc-900/90 border border-slate-200 dark:border-zinc-800 rounded-2xl p-5 shadow-sm dark:shadow-xl">
        <div className="flex items-center gap-2 mb-2">
          <Activity className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
          <h3 className="font-bold text-sm text-slate-900 dark:text-zinc-100">Laundering Typologies</h3>
        </div>
        <p className="text-xs text-slate-500 dark:text-zinc-500">
          No distinct structural laundering patterns (peel chains, rapid layering, or smurfing structuring) were detected along this money trail.
        </p>
      </div>
    );
  }

  const getStrengthBadge = (strength) => {
    if (strength >= 80) return 'bg-red-500/10 text-red-500 border-red-500/30';
    if (strength >= 60) return 'bg-amber-500/10 text-amber-500 border-amber-500/30';
    return 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/30';
  };

  return (
    <div
      ref={cardRef}
      className="bg-white dark:bg-zinc-900/90 border border-slate-200 dark:border-zinc-800 rounded-2xl p-5 shadow-sm dark:shadow-xl transition-all space-y-4"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
          <h3 className="font-bold text-sm text-slate-900 dark:text-zinc-100">
            Laundering Typologies ({typologies.length})
          </h3>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 border border-slate-200 dark:border-zinc-700 font-semibold">
          Algorithmic Detection
        </span>
      </div>

      {/* Typology Cards List */}
      <div className="space-y-3">
        {typologies.map((t, idx) => (
          <div
            key={idx}
            className="typo-card bg-slate-50 dark:bg-zinc-950/80 border border-slate-200 dark:border-zinc-800/80 rounded-xl p-3.5 space-y-2 hover:border-slate-300 dark:hover:border-zinc-700 transition-colors"
          >
            {/* Top: Name + Strength */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-xs sm:text-sm text-slate-900 dark:text-zinc-200">
                  {t.name}
                </span>
                {t.asset && (
                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-200 dark:bg-zinc-800 text-slate-700 dark:text-zinc-400">
                    {t.asset}
                  </span>
                )}
              </div>

              <span
                className={`text-[11px] font-mono font-bold px-2 py-0.5 rounded border ${getStrengthBadge(
                  t.strength
                )}`}
              >
                Strength {t.strength}%
              </span>
            </div>

            {/* Explanation Sentence */}
            <p className="text-xs text-slate-700 dark:text-zinc-300 leading-relaxed font-sans">
              {t.explanation}
            </p>

            {/* Measurements vs Thresholds */}
            {t.measurements && Object.keys(t.measurements).length > 0 && (
              <div className="bg-white dark:bg-zinc-900/90 p-2.5 rounded-lg border border-slate-200 dark:border-zinc-800/80 text-[11px] font-mono grid grid-cols-2 gap-2 text-slate-600 dark:text-zinc-400">
                <div>
                  <span className="text-slate-400 dark:text-zinc-500 block text-[10px] uppercase font-semibold">Measured</span>
                  {Object.entries(t.measurements).map(([k, v]) => (
                    <span key={k} className="text-slate-800 dark:text-zinc-200 block">
                      {k}: {typeof v === 'number' ? v.toFixed(3) : v}
                    </span>
                  ))}
                </div>
                <div>
                  <span className="text-slate-400 dark:text-zinc-500 block text-[10px] uppercase font-semibold">Rule Threshold</span>
                  {Object.entries(t.thresholds || {}).map(([k, v]) => (
                    <span key={k} className="text-slate-600 dark:text-zinc-400 block">
                      {k}: {typeof v === 'number' ? v.toFixed(3) : v}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Involved Wallets Count */}
            {t.wallets && t.wallets.length > 0 && (
              <div className="text-[10px] text-slate-500 dark:text-zinc-500 font-mono">
                Spanned {t.wallets.length} addresses in sequence
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
