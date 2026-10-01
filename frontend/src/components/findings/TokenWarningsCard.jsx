import { AlertCircle, ShieldAlert } from 'lucide-react';

export default function TokenWarningsCard({ tokenWarnings }) {
  if (!tokenWarnings || Object.keys(tokenWarnings).length === 0) return null;

  const hasImpersonators =
    tokenWarnings.impersonated_symbols && tokenWarnings.impersonated_symbols.length > 0;

  return (
    <div className="bg-white dark:bg-zinc-900/90 border border-slate-200 dark:border-zinc-800 rounded-2xl p-5 shadow-sm dark:shadow-xl transition-all space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-amber-500" />
          <h3 className="font-bold text-sm text-slate-900 dark:text-zinc-100">
            Token Allowlist & Filtering
          </h3>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 border border-slate-200 dark:border-zinc-700">
          Contract Pinned
        </span>
      </div>

      {/* Impersonator Notice if any */}
      {hasImpersonators && (
        <div className="bg-red-50 dark:bg-red-950/30 border border-red-300 dark:border-red-500/40 rounded-xl p-3 flex items-start gap-2.5">
          <ShieldAlert className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <span className="font-bold text-xs text-red-900 dark:text-red-300 block mb-0.5">
              Fraudulent Token Impersonation Detected
            </span>
            <p className="text-xs text-red-800 dark:text-zinc-300 leading-normal">
              {tokenWarnings.impersonation_note}
            </p>
          </div>
        </div>
      )}

      {/* Top Skipped Tokens */}
      {tokenWarnings.top_skipped && tokenWarnings.top_skipped.length > 0 && (
        <div>
          <span className="text-[11px] font-semibold text-slate-400 dark:text-zinc-500 uppercase tracking-wider block mb-1.5">
            Skipped Non-Allowlisted Assets:
          </span>
          <div className="flex flex-wrap gap-1.5 font-mono text-xs">
            {tokenWarnings.top_skipped.map((token, i) => (
              <span
                key={i}
                className={`px-2 py-0.5 rounded border text-[11px] flex items-center gap-1 ${
                  token.impersonating
                    ? 'bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400 border-red-300 dark:border-red-500/30 font-bold'
                    : 'bg-slate-100 dark:bg-zinc-950 text-slate-700 dark:text-zinc-400 border-slate-200 dark:border-zinc-800'
                }`}
              >
                <span>{token.asset}</span>
                <span className="text-slate-400 dark:text-zinc-600">({token.transfers})</span>
                {token.impersonating && <span className="text-[10px] text-red-600 dark:text-red-400">⚠️ Fake</span>}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
