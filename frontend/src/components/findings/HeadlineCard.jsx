import { useRef } from 'react';
import { ShieldCheck, AlertTriangle, AlertOctagon, HelpCircle, ArrowRight, ExternalLink, Building2, Coins, Milestone, CheckCircle2 } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { explorerUrlForNode, splitNodeId } from '../../utils/formatters';

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
  // Which chain the deposit landed on. Absent on single-chain traces, so the
  // badge only appears once the money has actually left the starting chain.
  const targetChain = splitNodeId(summary.node_id || summary.address).chain;

  // WHAT THE TRACE ESTABLISHED ABOUT THE MONEY, in the backend's own terms.
  // A connected path is not value arrival: the headline sentence comes from the
  // backend, which already distinguishes "X of the suspect's funds reached Y"
  // from "a path connects to Y, but no attributable value arrived" and from
  // "taint was not computed". Writing our own "stolen funds deposited" over the
  // top of that would erase exactly the distinction the backend exists to make.
  const tainted = summary.tainted_value_received;
  const hasTaint = Boolean(tainted) && Object.values(tainted).some((v) => v > 0);
  const taintState = summary.taint_computed !== true
    ? 'not_computed'
    : hasTaint
      ? 'attributed'
      : 'none_attributed';
  const intermediaries = Math.max(0, (summary.hop_distance || 1) - 1);
  const routeText = `${intermediaries} intermediate step${intermediaries === 1 ? '' : 's'}`;
  const confirmedDetail = {
    attributed: `Under FIFO accounting, ${summary.tainted_value_display || 'value'} of the suspect's funds arrived at ${summary.exchange} via ${routeText}.`,
    none_attributed: `A transaction path connects the suspect to ${summary.exchange} via ${routeText}, but under FIFO accounting none of the value arriving there traces back to the suspect's funds. The connection may still justify a records request.`,
    not_computed: `A transaction path connects the suspect to ${summary.exchange} via ${routeText}. Value-level attribution was not computed for this trace, so the path does not by itself show that the suspect's funds arrived.`,
  }[taintState];

  // WHAT KIND OF ENDPOINT THIS IS, and how it was recognised. A suspected
  // collection point is not a personal wallet, a mixer is not "unhosted", and a
  // fan-in pattern is not a "verified registry" match. Each tile below says what
  // the backend actually established, or that there was nothing to establish.
  const hasEndpoint = typeof summary.hop_distance === 'number';
  const obfuscator = (summary.mixers_or_bridges_crossed || [])[0];
  let targetName;
  let targetKind;
  if (isConfirmed) {
    targetName = summary.exchange;
    targetKind = 'Named exchange (VASP)';
  } else if (isLead) {
    targetName = 'Unnamed collection point';
    targetKind = 'Suspected exchange, unconfirmed';
  } else if (isTerminatedMixer) {
    targetName = obfuscator || 'Mixer';
    targetKind = 'Mixer: trail broken here';
  } else if (isTerminatedBridge) {
    targetName = obfuscator || 'Bridge';
    targetKind = 'Bridge: funds left this chain';
  } else {
    targetName = 'None identified';
    targetKind = 'No recognised endpoint';
  }
  const METHOD_LABEL = {
    known_label: 'Published label match',
    inferred_label: 'Label inferred from Ethereum (max 80%)',
    consolidation: 'Fan-in pattern only (capped at 67%)',
  };
  const hasScore = typeof summary.confidence_score === 'number';
  const scoreBasis = hasScore
    ? METHOD_LABEL[summary.method] || `Method: ${summary.method || 'unknown'}`
    : 'No attribution made';
  // The backend's stop reason, in its own words. "Reached the maximum depth"
  // was printed for every outcome, including a mixer and a wallet that never
  // sent anything, which told the investigator the wrong next step.
  const stopDetail = summary.termination?.detail || summary.termination?.label;

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
              <span>No Exchange Reached</span>
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
          {summary.headline}
        </h2>
        <p className="text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3] leading-relaxed">
          {isConfirmed
            ? `${confirmedDetail} Centralized exchanges hold KYC records, which makes this the actionable point for a lawful request.`
            : stopDetail || ''}
        </p>
        {/* An INFERRED route is badged where the claim is made. Part of the money's
            path is a bridge crossing matched by amount and timing, not an observed
            transfer, and the score is already held at or below that match. */}
        {summary.label_inferred && (
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="px-2 py-0.5 text-[10px] font-mono font-bold uppercase border border-amber-500/60 bg-amber-500/10 text-amber-700 dark:text-amber-300">
              Exchange name inferred
            </span>
            <span className="text-[11px] text-[#52525b] dark:text-[#a3a3a3] leading-snug">
              This address is labelled {summary.exchange} on Ethereum and is an active
              ordinary account on this chain. No label on this chain names it, so the
              name is an inference: check it on the chain&apos;s own explorer before
              relying on it.
            </span>
          </div>
        )}
        {summary.cross_chain_inferred && (
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="px-2 py-0.5 text-[10px] font-mono font-bold uppercase border border-cyan-500/60 bg-cyan-500/10 text-cyan-700 dark:text-cyan-300">
              Inferred cross-chain route
            </span>
            <span className="text-[11px] text-[#52525b] dark:text-[#a3a3a3] leading-snug">
              Part of this route is a bridge crossing matched at{' '}
              {(summary.handoff_scores || []).map((s) => `${s}/100`).join(', ')} on
              amount and timing, an inference rather than an observed transfer. The
              confidence above is held at or below that match.
            </span>
          </div>
        )}
        {/* The qualification travels with the claim, not in a footnote. */}
        {summary.caveat && (
          <p className="text-[11px] text-[#71717a] dark:text-[#888888] leading-snug italic">
            {summary.caveat}
          </p>
        )}
      </div>

      {/* 4 Instant Key Metric Tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1">
        <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] p-2.5">
          <span className="text-[10px] font-mono text-[#71717a] dark:text-[#888888] uppercase block flex items-center gap-1">
            <Building2 className="w-3 h-3 text-[#627EEA]" />
            Target
          </span>
          <p className="font-bold text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5] truncate">
            {targetName}
          </p>
          <span
            className={`text-[10px] font-mono font-semibold ${
              isConfirmed
                ? 'text-emerald-600 dark:text-emerald-400'
                : 'text-[#71717a] dark:text-[#888888]'
            }`}
          >
            {targetKind}
          </span>
        </div>

        <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] p-2.5">
          <span className="text-[10px] font-mono text-[#71717a] dark:text-[#888888] uppercase block flex items-center gap-1">
            <Coins className="w-3 h-3 text-red-500" />
            Stolen Funds
          </span>
          <p className="font-bold text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5] truncate">
            {!hasEndpoint
              ? '—'
              : taintState === 'attributed'
                ? summary.tainted_value_display
                : taintState === 'none_attributed'
                  ? 'None attributed'
                  : 'Not calculated'}
          </p>
          <span className="text-[10px] font-mono text-[#71717a] dark:text-[#888888]">
            {!hasEndpoint
              ? 'No endpoint to measure'
              : taintState === 'attributed'
                ? 'FIFO-attributable amount'
                : taintState === 'none_attributed'
                  ? 'FIFO found none arriving'
                  : 'Taint replay did not run'}
          </span>
        </div>

        <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] p-2.5">
          <span className="text-[10px] font-mono text-[#71717a] dark:text-[#888888] uppercase block flex items-center gap-1">
            <Milestone className="w-3 h-3 text-[#627EEA]" />
            Distance
          </span>
          <p className="font-bold text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5]">
            {hasEndpoint
              ? `${summary.hop_distance} ${summary.hop_distance === 1 ? 'Hop' : 'Hops'}`
              : '—'}
          </p>
          <span className="text-[10px] font-mono text-[#71717a] dark:text-[#888888]">
            {hasEndpoint ? 'Shortest path' : 'No endpoint reached'}
          </span>
        </div>

        <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] p-2.5">
          <span className="text-[10px] font-mono text-[#71717a] dark:text-[#888888] uppercase block flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-emerald-500" />
            Reliability
          </span>
          <p
            className={`font-bold text-xs sm:text-sm ${
              summary.method === 'known_label'
                ? 'text-emerald-700 dark:text-emerald-400'
                : 'text-amber-700 dark:text-amber-400'
            }`}
          >
            {hasScore ? `${summary.confidence_score}%` : '—'}
          </p>
          <span className="text-[10px] font-mono text-[#71717a] dark:text-[#888888]">
            {scoreBasis}
          </span>
        </div>
      </div>

      {/* THE POINT IN TIME. Which block this finding describes, and that a re-run
          at that height reproduces it - or that it is not pinned. */}
      {summary.as_of && (
        <div className="text-[11px] font-mono text-[#52525b] dark:text-[#a3a3a3] border border-[#d4d4d8] dark:border-[#262626] p-2 space-y-1">
          <div>
            <span className="uppercase text-[10px] font-bold mr-2">As of</span>
            {summary.as_of.pinned
              ? `block ${summary.as_of.block} on ${summary.as_of.chain_name}${summary.as_of.time_utc ? ` (${summary.as_of.time_utc})` : ''}`
              : 'not pinned to a block height'}
          </div>
          <p className="leading-snug font-sans">{summary.as_of.statement}</p>
          {summary.walk_cap_note && (
            <p className="leading-snug font-sans font-semibold text-red-700 dark:text-red-400">
              Graph partial: {summary.walk_cap_note}
            </p>
          )}
          {summary.history_truncation_note && (
            <p className="leading-snug font-sans text-amber-700 dark:text-amber-400">
              {summary.history_truncation_note}
            </p>
          )}
        </div>
      )}

      {/* A fan-in lead says what the calibration showed: a weak signal. */}
      {summary.fan_in_caveat && (
        <p className="text-[11px] leading-snug border border-amber-500/40 p-2 text-amber-800 dark:text-amber-300">
          {summary.fan_in_caveat}
        </p>
      )}

      {/* WHAT THE NAME RESTS ON. The evidence tier at a glance - the entity's own
          signed statement, a government list, a third-party pack, or our own
          inference - and the full provenance chain beneath it. */}
      {summary.evidence_tier && (
        <div className="text-xs border border-[#d4d4d8] dark:border-[#262626] p-2.5 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="uppercase text-[10px] font-mono font-bold text-[#71717a] dark:text-[#888888]">
              Evidence tier
            </span>
            <span
              className={`px-1.5 py-0.5 text-[10px] font-mono uppercase border ${
                ['self_published_signed', 'self_published', 'court_record', 'government_list'].includes(summary.evidence_tier)
                  ? 'border-emerald-500/50 text-emerald-700 dark:text-emerald-400'
                  : 'border-amber-500/50 text-amber-700 dark:text-amber-400'
              }`}
              title={summary.evidence_tier_text || ''}
            >
              {summary.evidence_tier_label || summary.evidence_tier}
            </span>
          </div>
          {summary.citation && (
            <p className="text-[11px] text-[#52525b] dark:text-[#a3a3a3] leading-snug break-words">
              Source: {summary.citation}
            </p>
          )}
        </div>
      )}

      {/* Target Address if present */}
      {summary.address && (
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono text-[#52525b] dark:text-[#a3a3a3] bg-[#f4f4f5] dark:bg-[#0a0a0a] p-2 border border-[#d4d4d8] dark:border-[#262626]">
          <span className="font-semibold text-[#09090b] dark:text-[#f5f5f5]">Target Deposit Wallet:</span>
          {/* The chain the deposit landed on. A requisition that names the wrong
              chain is a requisition the exchange cannot act on. */}
          {targetChain && (
            <span className="px-1.5 py-0.5 text-[10px] font-bold uppercase text-cyan-700 dark:text-cyan-300 bg-cyan-500/10 border border-cyan-500/50">
              {targetChain}
            </span>
          )}
          <a
            href={explorerUrlForNode(params?.explorer, summary.node_id || summary.address)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#627EEA] hover:underline flex items-center gap-1 font-bold break-all"
          >
            <span>{summary.address}</span>
            <ExternalLink className="w-3 h-3 shrink-0" />
          </a>
        </div>
      )}

      {/* WHO CAN ACTUALLY BE SERVED. The nearest exchange is the finding; if it is
          insolvent, sanctioned or seized it is kept as evidence and the request moves
          to the nearest actionable VASP reached - or the card says none was. */}
      {isConfirmed && summary.actionable === false && (
        <div className="text-xs bg-red-500/10 border border-red-500/40 p-2.5 space-y-1">
          <span className="font-bold uppercase font-mono text-[10px] text-red-700 dark:text-red-400 block">
            Not actionable: {summary.exchange}
          </span>
          <p className="text-[#52525b] dark:text-[#a3a3a3] leading-snug">
            {summary.exchange} is {summary.actionable_reason}. It stays on record as the
            nearest endpoint.{' '}
            {summary.recommended_vasp
              ? `The request goes to the nearest actionable VASP reached: ${summary.recommended_vasp.entity} (${summary.recommended_vasp.hop_distance} hops${summary.recommended_vasp.tainted_value_display ? `, ${summary.recommended_vasp.tainted_value_display} attributable` : ''}).`
              : 'No other actionable VASP was reached in this trace.'}
          </p>
        </div>
      )}
      {isConfirmed && (summary.recommended_vasp || summary.jurisdiction) && (
        <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono text-[#52525b] dark:text-[#a3a3a3]">
          <span className="uppercase text-[10px] font-bold">Jurisdiction</span>
          <span className="px-1.5 py-0.5 border border-[#d4d4d8] dark:border-[#262626] uppercase">
            {(summary.recommended_vasp?.jurisdiction || summary.jurisdiction || 'unknown').replace('foreign_fiu_registered', 'foreign · FIU-IND registered')}
          </span>
          <span>
            {{
              india: 'Indian VASP: BNSS 94 notice for customer records',
              foreign_fiu_registered:
                'Foreign VASP, FIU-IND registered: request to its Principal Officer in India; BNSS 94 or MLAT is the IO\'s call',
              foreign: 'Foreign VASP: its law-enforcement channel; MLAT for court evidence',
            }[summary.recommended_vasp?.jurisdiction || summary.jurisdiction] ||
              'Not established: confirm before choosing the route'}
          </span>
        </div>
      )}

      {/* Recommended Action & Action Buttons */}
      <div className="pt-3 border-t border-[#d4d4d8] dark:border-[#262626] flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="flex-1 space-y-0.5">
          <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#71717a] dark:text-[#888888] block">
            Recommended Lawful Action:
          </span>
          <p className="text-xs text-[#09090b] dark:text-[#d4d4d4] font-medium leading-relaxed">
            {/* The backend's wording, which differs by outcome: a named exchange,
                an unconfirmed lead that must NOT be served yet, or no endpoint. */}
            {summary.recommended_action}
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0 pt-1 sm:pt-0">
          {/* Only when there is a VASP a request can actually go to. Older payloads
              carry no recommended_vasp, so they keep the button as before. */}
          {isConfirmed && (summary.recommended_vasp || summary.actionable === undefined) && (
            <button
              type="button"
              onClick={onOpenSahyog}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold uppercase brutal-press shadow-[2px_2px_0px_#18181b] dark:shadow-[2px_2px_0px_#000000] border border-emerald-400 transition-all flex items-center gap-1.5 cursor-pointer"
            >
              <span>Prepare VASP Request</span>
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
