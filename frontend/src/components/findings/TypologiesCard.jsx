import { useRef } from 'react';
import { Activity } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(useGSAP);

export default function TypologiesCard({ typologies, summary }) {
  const cardRef = useRef(null);

  useGSAP(() => {
    if (typologies && typologies.length > 0) {
      gsap.from('.typo-card', {
        y: 12,
        opacity: 0,
        stagger: 0.06,
        duration: 0.4,
        ease: 'power2.out',
      });
    }
  }, { dependencies: [typologies], scope: cardRef });

  const found = Array.isArray(typologies) ? typologies : [];

  // DID THE DETECTORS RUN? This is the whole point of the empty state.
  //
  // An empty list is ambiguous: it means either "we ran five detectors and
  // found nothing" or "this recording was made before the detectors existed".
  // The old card could not tell them apart, so it printed "no laundering
  // patterns were detected" over a payload where NO ANALYSIS HAD RUN - a
  // false clean bill of health for a trail nobody examined.
  //
  // `summary` is the discriminator. The backend emits it whenever the
  // detector pass executed, so its presence means the detectors ran. A payload
  // without it predates them, and the card has to say the analysis was not
  // performed rather than claiming the trail was clean.
  const detectorsRan = Boolean(summary);

  if (found.length === 0) {
    return (
      <div className="bg-white dark:bg-[#111111] border border-[#d4d4d8] dark:border-[#262626] p-4 sm:p-5 shadow-[2px_2px_0px_#18181b] dark:shadow-[2px_2px_0px_#000000]">
        <div className="flex items-center gap-2 mb-1.5">
          <Activity className="w-4 h-4 text-[#627EEA]" />
          <h3 className="font-bold text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5]">
            Laundering Patterns (Typologies)
          </h3>
        </div>
        {detectorsRan ? (
          <>
            <p className="text-xs text-[#52525b] dark:text-[#a3a3a3]">
              The five laundering detectors ran over this trail and matched nothing above
              threshold. That is a result, not an absence of one.
            </p>
            {Number(summary?.suppressed) > 0 && (
              <p className="text-[11px] text-[#71717a] dark:text-[#888888] mt-1.5">
                {summary.suppressed} weaker match
                {summary.suppressed === 1 ? '' : 'es'} suppressed by the reporting
                cap.
              </p>
            )}
          </>
        ) : (
          <p className="text-xs text-[#71717a] dark:text-[#888888]">
            <strong className="text-[#52525b] dark:text-[#a3a3a3]">
              No typology analysis was performed on this result.
            </strong>{' '}
            This recording predates the laundering detectors, so nothing here says the
            trail was clean — only that this tool has not yet looked. Re-run the trace
            live to have the detectors applied.
          </p>
        )}
      </div>
    );
  }

  const getStrengthBadge = (strength) => {
    if (strength >= 80) return 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/30';
    if (strength >= 60) return 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30';
    return 'bg-[#627EEA]/15 text-[#627EEA] border-[#627EEA]/40';
  };

  return (
    <div
      ref={cardRef}
      className="bg-white dark:bg-[#111111] border border-[#d4d4d8] dark:border-[#262626] p-4 sm:p-5 transition-all space-y-3.5 shadow-[3px_3px_0px_#18181b] dark:shadow-[3px_3px_0px_#000000]"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-[#627EEA]" />
          <h3 className="font-bold text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5]">
            Laundering Patterns ({found.length})
          </h3>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 bg-[#f4f4f5] dark:bg-[#1a1a1a] text-[#52525b] dark:text-[#a3a3a3] border border-[#d4d4d8] dark:border-[#262626] font-semibold">
          Algorithmic Detection
        </span>
      </div>

      {/* Typology Cards List */}
      <div className="space-y-2.5">
        {found.map((t, idx) => (
          <div
            key={idx}
            className="typo-card bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] p-3 space-y-2 hover:border-[#627EEA] transition-colors"
          >
            {/* Top: Name + Strength */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-bold text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5]">
                  {t.name}
                </span>
                {t.asset && (
                  <span className="text-[10px] font-mono px-1.5 py-0.5 bg-white dark:bg-[#1a1a1a] text-[#52525b] dark:text-[#a3a3a3] border border-[#d4d4d8] dark:border-[#262626]">
                    {t.asset}
                  </span>
                )}
              </div>

              <span
                className={`text-[10px] font-mono font-bold px-2 py-0.5 border ${getStrengthBadge(
                  t.strength
                )}`}
              >
                Match {t.strength}%
              </span>
            </div>

            {/* Explanation Sentence */}
            <p className="text-xs text-[#52525b] dark:text-[#a3a3a3] leading-relaxed">
              {t.explanation}
            </p>

            {/* Measurements vs Thresholds */}
            {t.measurements && Object.keys(t.measurements).length > 0 && (
              <div className="bg-white dark:bg-[#111111] p-2.5 border border-[#d4d4d8] dark:border-[#262626] text-[11px] font-mono grid grid-cols-2 gap-2 text-[#52525b] dark:text-[#a3a3a3]">
                <div>
                  <span className="text-[#71717a] dark:text-[#666666] block text-[10px] uppercase font-semibold">Measured</span>
                  {Object.entries(t.measurements).map(([k, v]) => (
                    <span key={k} className="text-[#09090b] dark:text-[#f5f5f5] block">
                      {k}: {typeof v === 'number' ? v.toFixed(3) : v}
                    </span>
                  ))}
                </div>
                <div>
                  <span className="text-[#71717a] dark:text-[#666666] block text-[10px] uppercase font-semibold">Rule Threshold</span>
                  {Object.entries(t.thresholds || {}).map(([k, v]) => (
                    <span key={k} className="text-[#71717a] dark:text-[#a3a3a3] block">
                      {k}: {typeof v === 'number' ? v.toFixed(3) : v}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Involved Wallets Count */}
            {t.wallets && t.wallets.length > 0 && (
              <div className="text-[10px] text-[#71717a] dark:text-[#666666] font-mono">
                Spanned {t.wallets.length} addresses in sequence
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
