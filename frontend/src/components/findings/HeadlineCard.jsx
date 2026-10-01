import { useRef } from 'react';
import { ShieldCheck, AlertTriangle, AlertOctagon, HelpCircle, ArrowRight, ExternalLink } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { shortAddress, getExplorerUrl } from '../../utils/formatters';

gsap.registerPlugin(useGSAP);

export default function HeadlineCard({ summary, params, onOpenSahyog, onDownloadReport }) {
  const cardRef = useRef(null);

  useGSAP(() => {
    gsap.from(cardRef.current, {
      y: 20,
      opacity: 0,
      duration: 0.6,
      ease: 'power3.out',
    });
  }, { dependencies: [summary], scope: cardRef });

  if (!summary) return null;

  const isConfirmed = summary.found;
  const isLead = !summary.found && summary.lead;
  const isTerminatedMixer = summary.termination?.reason === 'terminated_at_mixer';
  const isTerminatedBridge = summary.termination?.reason === 'terminated_at_bridge';

  return (
    <div
      ref={cardRef}
      className={`rounded-2xl border p-5 shadow-sm dark:shadow-xl transition-all relative overflow-hidden ${
        isConfirmed
          ? 'bg-gradient-to-br from-emerald-50/70 via-white to-white dark:from-emerald-950/40 dark:via-zinc-900 dark:to-zinc-900 border-emerald-300 dark:border-emerald-500/40 ring-1 ring-emerald-500/20'
          : isLead
          ? 'bg-gradient-to-br from-amber-50/70 via-white to-white dark:from-amber-950/40 dark:via-zinc-900 dark:to-zinc-900 border-amber-300 dark:border-amber-500/40 ring-1 ring-amber-500/20'
          : isTerminatedMixer
          ? 'bg-gradient-to-br from-orange-50/70 via-white to-white dark:from-orange-950/40 dark:via-zinc-900 dark:to-zinc-900 border-orange-300 dark:border-orange-500/40'
          : isTerminatedBridge
          ? 'bg-gradient-to-br from-purple-50/70 via-white to-white dark:from-purple-950/40 dark:via-zinc-900 dark:to-zinc-900 border-purple-300 dark:border-purple-500/40'
          : 'bg-white dark:bg-zinc-900/90 border-slate-200 dark:border-zinc-800'
      }`}
    >
      {/* Top Header Badge */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {isConfirmed ? (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-100 dark:bg-emerald-500/20 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-500/40 text-xs font-bold uppercase tracking-wider">
              <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <span>Confirmed VASP Endpoint</span>
            </span>
          ) : isLead ? (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-100 dark:bg-amber-500/20 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-500/40 text-xs font-bold uppercase tracking-wider">
              <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400" />
              <span>Unconfirmed Lead (Collection Hub)</span>
            </span>
          ) : isTerminatedMixer ? (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-orange-100 dark:bg-orange-500/20 text-orange-800 dark:text-orange-300 border border-orange-300 dark:border-orange-500/40 text-xs font-bold uppercase tracking-wider">
              <AlertOctagon className="w-4 h-4 text-orange-600 dark:text-orange-400" />
              <span>Trail Severed by Mixer</span>
            </span>
          ) : isTerminatedBridge ? (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-purple-100 dark:bg-purple-500/20 text-purple-800 dark:text-purple-300 border border-purple-300 dark:border-purple-500/40 text-xs font-bold uppercase tracking-wider">
              <ArrowRight className="w-4 h-4 text-purple-600 dark:text-purple-400" />
              <span>Funds Exited via Bridge</span>
            </span>
          ) : (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 border border-slate-300 dark:border-zinc-700 text-xs font-semibold uppercase tracking-wider">
              <HelpCircle className="w-4 h-4 text-slate-500 dark:text-zinc-400" />
              <span>No VASP Reached</span>
            </span>
          )}
        </div>

        {summary.hop_distance !== undefined && (
          <span className="font-mono text-xs font-semibold px-2.5 py-0.5 rounded bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 border border-slate-200 dark:border-zinc-700">
            {summary.hop_distance} {summary.hop_distance === 1 ? 'Hop' : 'Hops'} Out
          </span>
        )}
      </div>

      {/* Main Headline */}
      <h2 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-zinc-100 leading-snug mb-2">
        {summary.headline}
      </h2>

      {/* Target Address if present */}
      {summary.address && (
        <div className="flex items-center gap-2 mb-3 text-xs font-mono text-slate-600 dark:text-zinc-400">
          <span>Target VASP Wallet:</span>
          <a
            href={getExplorerUrl(params?.explorer, summary.address)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-cyan-600 dark:text-cyan-400 hover:underline flex items-center gap-1 font-semibold"
          >
            <span>{shortAddress(summary.address, 8, 6)}</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      )}

      {/* Recommended Action & Action Buttons */}
      <div className="pt-3 border-t border-slate-200 dark:border-zinc-800/80 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="flex-1">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-zinc-500 block mb-0.5">
            Recommended Lawful Action:
          </span>
          <p className="text-xs text-slate-800 dark:text-zinc-300 font-medium">
            {summary.recommended_action}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {isConfirmed && (
            <button
              type="button"
              onClick={onOpenSahyog}
              className="px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-600/20 active:scale-95 transition-all flex items-center gap-1.5 cursor-pointer"
            >
              <span>Route to SAHYOG</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}

          <button
            type="button"
            onClick={onDownloadReport}
            className="px-3.5 py-2 rounded-lg bg-slate-100 dark:bg-zinc-800 hover:bg-slate-200 dark:hover:bg-zinc-700 border border-slate-300 dark:border-zinc-700 text-slate-800 dark:text-zinc-200 text-xs font-semibold active:scale-95 transition-all cursor-pointer"
          >
            Download PDF
          </button>
        </div>
      </div>
    </div>
  );
}
