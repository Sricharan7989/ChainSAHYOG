import { Radio, Archive } from 'lucide-react';

/**
 * LIVE OR REPLAYED — and when.
 *
 * WHY THIS EXISTS. Replay mode exists so a demo cannot fail on a rate limit or
 * a slow network mid-pitch, and it works: the bytes served are the real output
 * of a real trace, just not fetched again. But a reader who cannot tell the
 * difference has no way to know whether a figure on screen reflects the chain
 * as it stands now or as it stood when the trace was recorded. That confusion
 * has come up repeatedly during testing, most often after a feature was added
 * and an old recording was still being replayed - the new field simply was not
 * in the cached payload.
 *
 * So the provenance of every result is stated, not inferred:
 *   - live:    fetched from the chain for this request.
 *   - cache:   replayed from a recording, with the capture time shown, because
 *              a cached trace is a snapshot of the chain at a moment and funds
 *              may have moved since.
 *
 * A recording that predates a feature is not a bug in the trace; it is exactly
 * what this badge exists to make visible.
 */
export default function SourceBadge({ data }) {
  if (!data) return null;

  const isReplay = data.source === 'cache';

  let when = '';
  if (isReplay) {
    if (data.recorded_at) {
      // Rendered in the viewer's own locale; the raw value is UTC ISO.
      const parsed = new Date(data.recorded_at);
      when = Number.isNaN(parsed.getTime())
        ? String(data.recorded_at)
        : parsed.toLocaleString();
    } else if (data.recorded_epoch) {
      when = new Date(data.recorded_epoch * 1000).toLocaleString();
    }
  }

  return (
    <div
      className={`flex flex-wrap items-center gap-2 px-3 py-2 border text-[11px] font-mono ${
        isReplay
          ? 'bg-amber-500/10 border-amber-500/50 text-amber-700 dark:text-amber-400'
          : 'bg-emerald-500/10 border-emerald-500/50 text-emerald-700 dark:text-emerald-400'
      }`}
    >
      <span className="flex items-center gap-1.5 font-bold uppercase">
        {isReplay ? (
          <Archive className="w-3 h-3" />
        ) : (
          <Radio className="w-3 h-3" />
        )}
        {isReplay ? 'Replayed from recorded trace' : 'Live trace'}
      </span>
      {isReplay && when && (
        <span className="opacity-80">captured {when}</span>
      )}
      <span className="opacity-70">
        {isReplay
          ? 'the chain may have moved on since; tick “force live” to refetch'
          : 'fetched from the chain for this request'}
      </span>
    </div>
  );
}