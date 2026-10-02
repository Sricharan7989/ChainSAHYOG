import { useRef } from 'react';
import { ShieldCheck, AlertTriangle, AlertOctagon, HelpCircle, ArrowRight, ExternalLink, Building2, Coins, Milestone, CheckCircle2 } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { shortAddress, getExplorerUrl } from '../../utils/formatters';

gsap.registerPlugin(useGSAP);

export default function HeadlineCard({ summary, params, onOpenSahyog, onDownloadReport }) {
  const cardRef = useRef(null);

  useGSAP(() => {
    gsap.from(cardRef.current, {
      y: 16,
      opacity: 0,
      duration: 0.5,
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
      className={`border-2 p-5 bg-white dark:bg-[#111111] transition-all relative shadow-[4px_4px_0px_#18181b] dark:shadow-[4px_4px_0px_#000000] space-y-4 ${
        isConfirmed
          ? 'border-emerald-600 dark:border-emerald-500/70 border-l-[6px] border-l-emerald-600 dark:border-l-emerald-500'
          : isLead
          ? 'border-amber-500 dark:border-amber-500/70 border-l-[6px] border-l-amber-500'
          : isTerminatedMixer
          ? 'border-red-500 dark:border-red-500/70 border-l-[6px] border-l-red-500'
          : isTerminatedBridge
          ? 'border-[#627EEA] dark:border-[#627EEA]/70 border-l-[6px] border-l-[#627EEA]'
          : 'border-[#18181b] dark:border-[#262626] border-l-[6px] border-l-[#71717a]'
      }`}
    >
      {/* Top Banner Status */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {isConfirmed ? (
            <span className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/40 text-xs font-mono font-bold uppercase tracking-wider">
              <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <span>Funds Reached Regulated Exchange</span>
            </span>
          ) : isLead ? (
            <span className="flex items-center gap-1.5 px-2.5 py-1 bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/40 text-xs font-mono font-bold uppercase tracking-wider">
              <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400" />
              <span>Collection Point Detected</span>
            </span>
          ) : isTerminatedMixer ? (
            <span className="flex items-center gap-1.5 px-2.5 py-1 bg-red-500/15 text-red-700 dark:text-red-400 border border-red-500/40 text-xs font-mono font-bold uppercase tracking-wider">
              <AlertOctagon className="w-4 h-4 text-red-600 dark:text-red-400" />
              <span>Trail Obfuscated by Privacy Mixer</span>
            </span>
          ) : isTerminatedBridge ? (
            <span className="flex items-center gap-1.5 px-2.5 py-1 bg-[#627EEA]/15 text-[#627EEA] border border-[#627EEA]/40 text-xs font-mono font-bold uppercase tracking-wider">
              <ArrowRight className="w-4 h-4 text-[#627EEA]" />
              <span>Funds Exited via Cross-Chain Bridge</span>
            </span>
          ) : (
            <span className="flex items-center gap-1.5 px-2.5 py-1 bg-[#f4f4f5] dark:bg-[#1a1a1a] text-[#52525b] dark:text-[#a3a3a3] border border-[#d4d4d8] dark:border-[#262626] text-xs font-mono font-bold uppercase tracking-wider">
              <HelpCircle className="w-4 h-4 text-[#71717a]" />
              <span>Funds in Unhosted Wallets</span>
            </span>
          )}
        </div>

        {summary.hop_distance !== undefined && (
          <span className="font-mono text-xs font-bold px-2.5 py-1 bg-[#f4f4f5] dark:bg-[#1a1a1a] text-[#09090b] dark:text-[#f5f5f5] border border-[#d4d4d8] dark:border-[#262626]">
            {summary.hop_distance} {summary.hop_distance === 1 ? 'Hop' : 'Hops'} Away
          </span>
        )}
      </div>

      {/* Main Plain-English Verdict */}
      <div className="space-y-1">
        <h2 className="text-lg sm:text-xl font-extrabold text-[#09090b] dark:text-[#f5f5f5] leading-snug">
          {isConfirmed
            ? `Stolen funds deposited into ${summary.exchange || 'Centralized Exchange'}`
            : summary.headline}
        </h2>
        <p className="text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3] leading-relaxed">
          {isConfirmed
            ? `The suspect moved funds through ${Math.max(0, (summary.hop_distance || 1) - 1)} intermediary wallet(s) before depositing into ${summary.exchange}. Centralized exchanges maintain mandatory KYC records, making this the primary actionable chokepoint to freeze funds and identify the person.`
            : 'Tracing completed across public blockchain transactions to the maximum depth threshold.'}
        </p>
      </div>

      {/* 4 Instant Key Metric Tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1">
        <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] p-2.5">
          <span className="text-[10px] font-mono text-[#71717a] dark:text-[#888888] uppercase block flex items-center gap-1">
            <Building2 className="w-3 h-3 text-[#627EEA]" />
            Target
          </span>
          <p className="font-bold text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5] truncate">
            {summary.exchange || 'Unhosted'}
          </p>
          <span className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 font-semibold">
            {isConfirmed ? 'Regulated VASP' : 'Personal Wallet'}
          </span>
        </div>

        <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] p-2.5">
          <span className="text-[10px] font-mono text-[#71717a] dark:text-[#888888] uppercase block flex items-center gap-1">
            <Coins className="w-3 h-3 text-red-500" />
            Stolen Funds
          </span>
          <p className="font-bold text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5] truncate">
            {summary.tainted_value_display || 'Observed Value'}
          </p>
          <span className="text-[10px] font-mono text-[#71717a] dark:text-[#888888]">
            Attributable amount
          </span>
        </div>

        <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] p-2.5">
          <span className="text-[10px] font-mono text-[#71717a] dark:text-[#888888] uppercase block flex items-center gap-1">
            <Milestone className="w-3 h-3 text-[#627EEA]" />
            Distance
          </span>
          <p className="font-bold text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5]">
            {summary.hop_distance || 0} Hops
          </p>
          <span className="text-[10px] font-mono text-[#71717a] dark:text-[#888888]">
            Shortest path
          </span>
        </div>

        <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] p-2.5">
          <span className="text-[10px] font-mono text-[#71717a] dark:text-[#888888] uppercase block flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-emerald-500" />
            Reliability
          </span>
          <p className="font-bold text-xs sm:text-sm text-emerald-700 dark:text-emerald-400">
            {summary.confidence_score || 0}%
          </p>
          <span className="text-[10px] font-mono text-[#71717a] dark:text-[#888888]">
            Verified registry
          </span>
        </div>
      </div>

      {/* Target Address if present */}
      {summary.address && (
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono text-[#52525b] dark:text-[#a3a3a3] bg-[#f4f4f5] dark:bg-[#0a0a0a] p-2 border border-[#d4d4d8] dark:border-[#262626]">
          <span className="font-semibold text-[#09090b] dark:text-[#f5f5f5]">Target Deposit Wallet:</span>
          <a
            href={getExplorerUrl(params?.explorer, summary.address)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#627EEA] hover:underline flex items-center gap-1 font-bold break-all"
          >
            <span>{summary.address}</span>
            <ExternalLink className="w-3 h-3 shrink-0" />
          </a>
        </div>
      )}

      {/* Recommended Action & Action Buttons */}
      <div className="pt-3 border-t border-[#d4d4d8] dark:border-[#262626] flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="flex-1 space-y-0.5">
          <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#71717a] dark:text-[#888888] block">
            Recommended Lawful Action:
          </span>
          <p className="text-xs text-[#09090b] dark:text-[#d4d4d4] font-medium leading-relaxed">
            {isConfirmed
              ? `Serve a statutory requisition to ${summary.exchange} via SAHYOG to freeze deposits on address ${shortAddress(summary.address, 6, 4)} and requisition full KYC records.`
              : summary.recommended_action}
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0 pt-1 sm:pt-0">
          {isConfirmed && (
            <button
              type="button"
              onClick={onOpenSahyog}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold uppercase brutal-press shadow-[2px_2px_0px_#18181b] dark:shadow-[2px_2px_0px_#000000] border border-emerald-400 transition-all flex items-center gap-1.5 cursor-pointer"
            >
              <span>Route to SAHYOG</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}

          <button
            type="button"
            onClick={onDownloadReport}
            className="px-3.5 py-2 bg-white dark:bg-[#1a1a1a] hover:bg-[#f4f4f5] dark:hover:bg-[#262626] border-2 border-[#18181b] dark:border-[#262626] text-[#09090b] dark:text-[#f5f5f5] text-xs font-mono font-bold uppercase brutal-press shadow-[2px_2px_0px_#18181b] dark:shadow-[2px_2px_0px_#000000] transition-all cursor-pointer"
          >
            Download PDF
          </button>
        </div>
      </div>
    </div>
  );
}
