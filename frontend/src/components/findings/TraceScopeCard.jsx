import { useState } from 'react';
import { Flag, Scissors, ChevronDown, ChevronUp, ShieldAlert } from 'lucide-react';

/**
 * HOW THE TRACE ENDED, AND WHAT IT LEFT OUT.
 *
 * WHY THIS CARD EXISTS. The backend explains every trace in three ways that the
 * panel used to drop on the floor:
 *
 *   termination - why the walk stopped. Each reason implies a different next step
 *                 (lower the dust threshold, raise the depth, accept a mixer as a
 *                 hard stop, expand the labels), so it is the actionable part of
 *                 a trace that found nothing.
 *   truncated   - a cap cut the walk short, so the graph is PARTIAL. A partial
 *                 graph that looks complete invites "there was no exchange" when
 *                 the honest statement is "we did not follow every branch".
 *   notes       - specific things the engine skipped or could not do, e.g. a
 *                 wallet it could not fetch, or a chain whose typologies were not
 *                 analysed.
 *
 * All three are statements about what we did NOT look at, which is exactly the
 * kind of statement this project must never lose.
 */
export default function TraceScopeCard({ termination, truncated, notes, labelCoverage }) {
  const [expanded, setExpanded] = useState(false);
  // Chains this trace read where we hold too few labels to name an exchange.
  // Shown on EVERY trace, single-chain included: a trace started on a chain with
  // no labels has the same blind spot as one that crossed onto it.
  const uncovered = Object.entries(labelCoverage || {}).filter(
    ([, info]) => info && !info.identification_possible
  );
  const noteList = Array.isArray(notes) ? notes : [];
  const shown = expanded ? noteList : noteList.slice(0, 3);

  return (
    <div className="bg-white dark:bg-[#111111] border border-[#d4d4d8] dark:border-[#262626] p-4 space-y-3 shadow-[2px_2px_0px_#18181b] dark:shadow-[2px_2px_0px_#000000]">
      <div className="flex items-start gap-2">
        <Flag className="w-4 h-4 text-[#627EEA] shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <h4 className="font-bold text-xs uppercase tracking-wider font-mono text-[#09090b] dark:text-[#f5f5f5]">
            How this trace ended
          </h4>
          {termination && (termination.label || termination.detail) ? (
            <>
              <p className="text-xs font-semibold text-[#09090b] dark:text-[#f5f5f5]">
                {termination.label}
              </p>
              {termination.detail && (
                <p className="text-[11px] text-[#52525b] dark:text-[#a3a3a3] leading-snug">
                  {termination.detail}
                </p>
              )}
            </>
          ) : (
            <p className="text-[11px] text-[#52525b] dark:text-[#a3a3a3] leading-snug">
              This result does not record why the walk stopped (the recording predates
              that field).
            </p>
          )}
        </div>
      </div>

      {truncated && (
        <div className="flex items-start gap-2 bg-amber-500/10 border border-amber-500/40 p-2.5">
          <Scissors className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <p className="text-[11px] text-amber-800 dark:text-amber-300 leading-snug">
            <strong>The graph is partial.</strong> A size cap stopped the walk from
            following every branch, so only the largest transfers were expanded. An
            exchange could lie down a branch that was not taken.
          </p>
        </div>
      )}

      {uncovered.length > 0 && (
        <div className="flex items-start gap-2 bg-amber-500/10 border border-amber-500/40 p-2.5">
          <ShieldAlert className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div className="text-[11px] text-amber-800 dark:text-amber-300 leading-snug space-y-1">
            <strong className="block">Label coverage limit</strong>
            {uncovered.map(([slug, info]) => (
              <span key={slug} className="block">
                {info.note || `Too few labels are held for ${slug} to recognise an exchange there.`}
              </span>
            ))}
          </div>
        </div>
      )}

      {noteList.length > 0 && (
        <div className="space-y-1.5 pt-2 border-t border-[#d4d4d8] dark:border-[#262626]">
          <span className="text-[10px] font-mono font-semibold uppercase tracking-wider text-[#71717a] dark:text-[#888888] block">
            Engine notes ({noteList.length})
          </span>
          <ul className="space-y-1 text-[11px] text-[#52525b] dark:text-[#a3a3a3] leading-snug list-disc pl-4">
            {shown.map((note, i) => (
              <li key={i} className="break-words">{note}</li>
            ))}
          </ul>
          {noteList.length > 3 && (
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              className="text-[10px] font-mono text-[#627EEA] hover:underline flex items-center gap-1 cursor-pointer"
            >
              {expanded ? 'Show fewer' : `Show all ${noteList.length}`}
              {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
