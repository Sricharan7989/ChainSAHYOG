import { AlertCircle, ShieldAlert } from 'lucide-react';

export default function TokenWarningsCard({ tokenWarnings }) {
  if (!tokenWarnings || Object.keys(tokenWarnings).length === 0) return null;

  const hasImpersonators =
    tokenWarnings.impersonated_symbols && tokenWarnings.impersonated_symbols.length > 0;

  return (
    <div className="bg-white dark:bg-[#111111] border border-[#d4d4d8] dark:border-[#262626] p-4 sm:p-5 transition-all space-y-3 shadow-[3px_3px_0px_#18181b] dark:shadow-[3px_3px_0px_#000000]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-amber-500" />
          <h3 className="font-bold text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5]">
            Token Allowlist & Filtering
          </h3>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 bg-[#f4f4f5] dark:bg-[#1a1a1a] text-[#52525b] dark:text-[#a3a3a3] border border-[#d4d4d8] dark:border-[#262626]">
          Contract Pinned
        </span>
      </div>

      {/* Impersonator Notice if any */}
      {hasImpersonators && (
        <div className="bg-red-500/10 dark:bg-red-950/30 border border-red-500/40 p-3 flex items-start gap-2.5">
          <ShieldAlert className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
          <div>
            <span className="font-bold text-xs text-red-700 dark:text-red-400 block mb-0.5">
              Fraudulent Token Impersonation Detected
            </span>
            <p className="text-xs text-[#52525b] dark:text-[#a3a3a3] leading-normal">
              {tokenWarnings.impersonation_note}
            </p>
          </div>
        </div>
      )}

      {/* Top Skipped Tokens */}
      {tokenWarnings.top_skipped && tokenWarnings.top_skipped.length > 0 && (
        <div>
          <span className="text-[11px] font-semibold text-[#71717a] dark:text-[#666666] uppercase tracking-wider block mb-1.5 font-mono">
            Skipped Non-Allowlisted Assets:
          </span>
          <div className="flex flex-wrap gap-1.5 font-mono text-xs">
            {tokenWarnings.top_skipped.map((token, i) => (
              <span
                key={i}
                className={`px-2 py-0.5 border text-[11px] flex items-center gap-1 ${
                  token.impersonating
                    ? 'bg-red-500/20 text-red-700 dark:text-red-400 border-red-500/30 font-bold'
                    : 'bg-[#f4f4f5] dark:bg-[#0a0a0a] text-[#52525b] dark:text-[#a3a3a3] border-[#d4d4d8] dark:border-[#262626]'
                }`}
              >
                <span>{token.asset}</span>
                <span className="text-[#71717a] dark:text-[#666666]">({token.transfers})</span>
                {token.impersonating && <span className="text-[10px] text-red-600 dark:text-red-400">⚠️ Fake</span>}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
