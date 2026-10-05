import { useRef, useState } from 'react';
import { X, Copy, Check, Send, FileText, Lock } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { formatAssets } from '../utils/formatters';

gsap.registerPlugin(useGSAP);

export default function SahyogModal({ isOpen, onClose, data, onShowToast }) {
  const modalRef = useRef(null);
  const backdropRef = useRef(null);
  const [copied, setCopied] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useGSAP(() => {
    if (isOpen) {
      gsap.fromTo(
        backdropRef.current,
        { opacity: 0 },
        { opacity: 1, duration: 0.25 }
      );
      gsap.fromTo(
        modalRef.current,
        { scale: 0.95, opacity: 0, y: 15 },
        { scale: 1, opacity: 1, y: 0, duration: 0.35, ease: 'power3.out' }
      );
    }
  }, { dependencies: [isOpen] });

  if (!isOpen || !data) return null;

  const summary = data.summary || {};
  // WHO THE REQUEST GOES TO. The nearest exchange unless it is not actionable
  // (insolvent, sanctioned, seized), in which case the backend names the nearest
  // actionable VASP reached. Older payloads carry no recommended_vasp and fall
  // back to the nearest exchange.
  const rec = summary.recommended_vasp || null;
  const sameAsNearest = !rec || rec.entity === summary.exchange;
  const targetExchange = rec?.entity || summary.exchange || 'the VASP';
  const targetWallet = rec?.address || summary.address;
  const hops = rec?.hop_distance ?? summary.hop_distance;
  const confidence = rec?.confidence_score ?? summary.confidence_score;
  const jurisdiction = rec?.jurisdiction || summary.jurisdiction || 'unknown';
  const startWallet = data.start_address;
  // Six characters of the wallet, after any 0x prefix - not every chain has one.
  const caseId = `CS-${startWallet.replace(/^0x/i, '').slice(0, 6).toUpperCase()}`;

  // WHAT THE REQUEST MAY CLAIM ABOUT THE MONEY. Only what the trace established:
  // the FIFO-attributed amount where there is one, never the gross value.
  const tainted = summary.tainted_value_received;
  const hasTaint = tainted && Object.values(tainted).some((v) => v > 0);
  const amount = sameAsNearest
    ? (summary.taint_computed && hasTaint ? formatAssets(tainted) : null)
    : rec?.tainted_value_display || null;
  let fundsSentence;
  if (summary.taint_computed && amount) {
    fundsSentence = `funds attributable to the suspect under FIFO accounting, approximately [${amount}], reached ${targetExchange} at the address below.`;
  } else if (summary.taint_computed) {
    fundsSentence = `a transaction path connects that wallet to ${targetExchange} at the address below. Under FIFO accounting no value attributable to the suspect was established as arriving there; the records are sought to determine the connection.`;
  } else {
    fundsSentence = `a transaction path connects that wallet to ${targetExchange} at the address below. The amount attributable to the suspect was not calculated for this trace.`;
  }
  // WHAT LETS A COMPLIANCE TEAM FIND THE ACCOUNT. An address alone does not: an
  // exchange reuses one address on several chains, and the account is located from
  // the deposit transaction. So each deposit is named by hash, time (UTC and IST),
  // chain with its id, asset with its contract, and amount as transferred.
  const deposits = (rec ? rec.deposits : summary.deposits) || [];
  const depositsTotal = (rec ? rec.deposits_total : summary.deposits_total) || deposits.length;
  const chainName = rec?.chain_name || deposits[0]?.chain_name || data.chain?.name || 'Ethereum';
  const chainId = rec?.chain_id ?? deposits[0]?.chain_id ?? data.chain?.chain_id;
  const fmtAmt = (n) => Number(n).toLocaleString('en-US', { maximumFractionDigits: 8 });
  const assetLine = (d) =>
    d.contract
      ? `${d.asset}, ${d.token_standard} token, contract ${d.contract}`
      : `${d.asset}, the native coin of ${d.chain_name}`;
  const depositLines = deposits
    .map((d, i) => {
      const lines = [
        `   (${i + 1}) Transaction hash: ${d.tx_hash}`,
        `       Date and time: ${d.time_utc} (${d.time_ist})`,
        `       Chain: ${d.chain_name} (chain ID ${d.chain_id})`,
        `       Asset: ${assetLine(d)}`,
        `       Amount transferred: ${fmtAmt(d.amount)} ${d.asset}`,
      ];
      if (d.via === 'bridge_credit') {
        lines.push(`       Credited by a bridge contract (${d.from}), not by a direct transfer`);
      }
      if (d.suspect_amount !== null && d.suspect_amount !== undefined) {
        lines.push(`       Of which attributable to the suspect under FIFO accounting: ${fmtAmt(d.suspect_amount)} ${d.asset}`);
      }
      return lines.join('\n');
    })
    .join('\n');
  const unlisted = depositsTotal - deposits.length;
  const depositBlock = deposits.length
    ? `   Deposits into that address identified by the trace (${deposits.length}):\n${depositLines}` +
      (unlisted > 0
        ? `\n   (${unlisted} further deposit${unlisted === 1 ? '' : 's'} into this address on the traced route ${unlisted === 1 ? 'is' : 'are'} not listed: ${deposits.some((d) => d.suspect_amount > 0) ? 'they carried no value attributable to the suspect, or fall outside the 25 largest' : 'the 25 largest are listed'}.)`
        : '')
    : '   (The individual deposit transactions were not recorded for this trace; re-run the trace to list them.)';

  // PRESERVATION PERIOD. A preservation request with no duration is unenforceable.
  // 180 days follows the preservation period Indian rules already set for
  // intermediaries (IT Intermediary Rules 2021, rule 3(1)(g)); extendable, and in
  // any case running until the records are produced.
  const PRESERVATION =
    'for 180 days from receipt of this request, extendable on further written request, and in any event until the records at (b) have been produced';

  // THE ANNEXURE. The score, how it is built, and the FIFO assumption live here,
  // not in the request body: a bare percentage in a document that may reach a
  // court invites "so you accept you may be wrong?", and it can only be answered
  // with the explanation beside it. The body states the method and the hops.
  const methodText =
    rec?.method_text || summary.method_text || 'see the attached technical annexure';
  const route = rec?.path || [];
  const components = (rec ? rec.confidence_components : summary.confidence_components) || [];
  const fullyAccounted = rec ? rec.path_fully_accounted : summary.path_fully_accounted;
  const assumedOnRoute = rec ? rec.path_assumed_pre_existing_display : summary.path_assumed_pre_existing_display;
  const crossChain = rec ? rec.cross_chain_inferred : summary.cross_chain_inferred;
  const handoffScores = (rec ? rec.handoff_scores : summary.handoff_scores) || [];
  // The provenance chain and evidence tier of the label behind the attribution.
  const labelSource = rec?.citation || rec?.label_source || null;
  const tierText = rec?.evidence_tier_text || null;
  const annexureText = `ANNEXURE A - TECHNICAL BASIS OF THE ATTRIBUTION
(Attached to draft VASP request ${caseId}. Explains how paragraph 1 was reached.)

A1. How the deposit address was attributed to ${targetExchange}
   Method: ${methodText}.${tierText ? `\n   Evidence tier: ${tierText}.` : ''}${labelSource ? `\n   Source of the label: ${labelSource}.` : ''}

A2. Route traced (${hops} hop${hops === 1 ? '' : 's'}, public blockchain records only)
${route.length ? route.map((n, i) => `   ${i === 0 ? 'Suspect wallet' : `Hop ${i}`}: ${n}`).join('\n') : '   (route not recorded in this result)'}${crossChain ? `\n   Part of this route is a bridge crossing between chains that is INFERRED from matching amounts and timing, not observed as one transaction (match score${handoffScores.length === 1 ? '' : 's'}: ${handoffScores.join(', ')} out of 100).` : ''}

A3. Accounting rule for the amounts in paragraph 1
   Amounts are attributed under FIFO (first in, first out): each wallet on the route is treated as spending the oldest funds it holds first. FIFO is a convention for following value through wallets that also hold other funds; it does not identify particular coins, and a different convention (for example proportional attribution) can attribute a different amount to the same deposits.
   ${fullyAccounted === false ? `On this route, ${assumedOnRoute} could only be accounted for by assuming the wallets held funds before the period the trace observed; that part of the figure rests on the assumption.` : fullyAccounted === true ? 'On this route every amount was accounted for from transfers the trace observed; no assumed prior balance was needed.' : 'Whether the route was fully accounted for was not computed for this result.'}

A4. Analytical confidence score: ${confidence} out of 100
   This is the tool's internal measure of how strongly the available evidence supports the attribution in A1, built from the components below. It is not a probability that the attribution is correct, and it does not measure anything about the account holder.
${components.length ? components.map((c) => `   ${c.points >= 0 ? '+' : ''}${c.points}  ${c.label}`).join('\n') : '   (components not recorded in this result)'}

A5. Point in time
   ${data.as_of?.statement || 'The block height this trace describes was not recorded.'}${summary.walk_cap_note ? `\n   ${summary.walk_cap_note}` : ''}${summary.history_truncation_note ? `\n   ${summary.history_truncation_note}` : ''}

A6. Limits
   - Only public blockchain records were used. No private or exchange data was accessed.
   - Exchange attributions come from published address labels, which can be incomplete or wrong; the records sought in the request are what confirm or refute it.
   - The trace stops at the first exchange on each branch; it does not follow funds inside an exchange.`;

  // A FALLBACK IS DIFFERENT MONEY. An exchange ends a branch of the trace, so a
  // VASP reached past a barred one sits on another branch: the funds that reached
  // it are not the funds that reached the barred exchange. The request says so,
  // and every figure in it is the fallback's own (built server-side from that
  // VASP's attribution alone).
  const branch = rec?.branch || null;
  const splitText = !branch
    ? 'the routes to the two exchanges are separate branches of the trace'
    : branch.diverges_at_suspect
      ? 'the routes to the two exchanges separate at the suspect wallet itself'
      : (branch.diverges_after_hops === 1 ? "the routes to the two exchanges share their first hop" : `the routes to the two exchanges share their first ${branch.diverges_after_hops} hops`) + ` and separate at wallet ${branch.diverges_at}`;
  const nonActionableNote =
    summary.actionable === false && !sameAsNearest
      ? `\n   (The nearest exchange on the trail, ${summary.exchange}, is not actionable (${summary.actionable_reason}). It is recorded as evidence and is not the subject of this request. The funds described here are a different part of the traced money from those that reached ${summary.exchange}: ${splitText}. Every amount, deposit and hop count in this request is ${targetExchange}'s own.)`
      : '';

  // THE INSTRUMENT AND THE CHANNEL, by jurisdiction. Named, not drafted: the
  // section-level wording is the investigating officer's, not this tool's.
  const fiu = rec?.fiu_ind_registration || null;
  const routeParagraph = {
    foreign_fiu_registered:
      `3. Channel: ${targetExchange} is a foreign VASP registered with the Financial Intelligence Unit - India (FIU-IND) as a reporting entity under the Prevention of Money Laundering Act, 2002${fiu ? ` (registered ${fiu.registered})` : ''}. As a reporting entity it is obliged to maintain the customer and transaction records sought here, and has a Principal Officer responsible for its compliance in India. This request is addressed to that Principal Officer, through ${targetExchange}'s law-enforcement request channel. Whether production can be compelled by a notice under Section 94 of the Bharatiya Nagarik Suraksha Sanhita, 2023, or a formal request through the Mutual Legal Assistance Treaty (MLAT) route is needed for records held outside India, is for the investigating officer to decide; registration alone does not settle it.`,
    india:
      `3. Instrument: production of these customer records is sought by a notice under Section 94 of the Bharatiya Nagarik Suraksha Sanhita, 2023, to be issued by the investigating officer.`,
    foreign:
      `3. Channel: ${targetExchange} is a foreign VASP. This request is made through ${targetExchange}'s own law-enforcement request channel. Records intended as evidence in court are to be sought by a formal request through the Mutual Legal Assistance Treaty (MLAT) route. A domestic BNSS 94 notice is not the instrument for a foreign entity.`,
  }[jurisdiction] ||
    `3. Jurisdiction not established: confirm whether ${targetExchange} is an Indian VASP before issuing. If Indian, the instrument for production of customer records is a notice under Section 94 of the Bharatiya Nagarik Suraksha Sanhita, 2023; if foreign, use ${targetExchange}'s law-enforcement request channel and the MLAT route for court evidence.`;

  const noticeText = `DRAFT VASP REQUEST - PREPARED WITH CHAINSAHYOG FOR THE INVESTIGATING OFFICER (NOT ISSUED)
CASE REFERENCE: ${caseId}

TO: Compliance & Law Enforcement Response, ${targetExchange}
SUBJECT: PRESERVATION AND PRODUCTION OF CUSTOMER (KYC) RECORDS - CYBER FRAUD INVESTIGATION

1. During the investigation of cyber fraud/theft involving suspect wallet address [${startWallet}], analysis of public blockchain transaction records indicates that ${fundsSentence}${nonActionableNote}
   Deposit address: ${targetWallet} (on ${chainName}${chainId ? `, chain ID ${chainId}` : ''})
${depositBlock}
   Hops from the suspect wallet: ${hops}
   Method of attribution: ${methodText}. The technical basis, including the accounting rule and the analytical score, is set out in Annexure A attached.

2. You are requested to:
   a. Preserve, ${PRESERVATION}, all account records, activity logs and balances of the account or accounts credited with the deposits listed in paragraph 1.
   b. Produce the customer records for that account or those accounts:
      - Full legal name and verified identity proof
      - Registered email address, telephone number and residential address
      - Linked bank accounts and fiat withdrawal records
      - IP access logs (with timestamps) for account creation and deposit sessions

${routeParagraph}

4. Note on channels: Sahyog's documented scope is notices to intermediaries under Section 79(3)(b) of the Information Technology Act, 2000; industry reports that it also carries BNSS 94 data requests are not confirmed by I4C.

Investigating Officer
(name, rank and police station to be completed before issue)`;

  const handleCopy = () => {
    navigator.clipboard.writeText(`${noticeText}\n\n\n${annexureText}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    onShowToast('Draft VASP request copied to clipboard');
  };

  const handleSimulateSubmit = () => {
    setSubmitted(true);
    onShowToast(`Draft request to ${targetExchange} marked as prepared (simulated; nothing was sent)`);
    setTimeout(() => {
      onClose();
      setSubmitted(false);
    }, 1800);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        ref={backdropRef}
        onClick={onClose}
        className="fixed inset-0 bg-black/80"
      />

      {/* Modal Dialog */}
      <div
        ref={modalRef}
        className="relative z-10 w-full max-w-2xl bg-[#ffffff] dark:bg-[#111111] border-2 border-[#18181b] dark:border-[#262626] border-t-4 border-t-[#627EEA] shadow-[8px_8px_0px_#000] overflow-hidden flex flex-col max-h-[90vh]"
      >
        {/* Modal Header */}
        <div className="border-b border-[#18181b] dark:border-[#262626] p-5 flex items-center justify-between bg-[#f4f4f5] dark:bg-[#141414]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-[#ffffff] dark:bg-[#1a1a1a] border border-[#627EEA] flex items-center justify-center text-[#627EEA]">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-base text-[#09090b] dark:text-[#f5f5f5] flex items-center gap-2">
                <span>Prepare VASP Request</span>
                <span className="text-[10px] font-mono px-2 py-0.5 bg-amber-500/20 text-amber-700 dark:text-amber-400 border border-amber-500/40 uppercase">
                  Draft, not issued
                </span>
              </h3>
              <p className="text-xs text-[#71717a] dark:text-[#888888] font-mono">
                Case reference: {caseId} · Addressed to {targetExchange} · Jurisdiction: {jurisdiction === 'foreign_fiu_registered' ? 'foreign, FIU-IND registered' : jurisdiction}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-[#71717a] dark:text-[#888888] hover:text-[#09090b] dark:hover:text-white hover:bg-[#f4f4f5] dark:hover:bg-[#1a1a1a] transition-colors cursor-pointer border border-[#18181b] dark:border-[#262626]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Notice Preview Content */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          <div className="flex items-center justify-between text-xs text-[#52525b] dark:text-[#a3a3a3] bg-[#f4f4f5] dark:bg-[#0a0a0a] px-3 py-2 border border-[#18181b] dark:border-[#262626] font-mono">
            <span>
              {jurisdiction === 'india'
                ? 'Instrument: BNSS 94 notice'
                : jurisdiction === 'foreign_fiu_registered'
                  ? 'Channel: Principal Officer in India; BNSS 94 or MLAT per IO'
                  : jurisdiction === 'foreign'
                    ? 'Channel: VASP LE channel; MLAT for court evidence'
                    : 'Jurisdiction not established'}
            </span>
            <span className="flex items-center gap-1 text-amber-700 dark:text-amber-400">
              <Lock className="w-3.5 h-3.5" />
              <span>Draft for the investigating officer</span>
            </span>
          </div>

          <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] p-4 border border-[#18181b] dark:border-[#262626] font-mono text-xs text-[#09090b] dark:text-[#d4d4d4] whitespace-pre-wrap leading-relaxed select-all">
            {noticeText}
          </div>

          {/* Annexure: attached to the request, kept out of its body. */}
          <div className="text-[10px] font-mono font-bold uppercase text-[#71717a] dark:text-[#888888]">
            Attached: Annexure A
          </div>
          <div className="bg-[#fafafa] dark:bg-[#0d0d0d] p-4 border border-dashed border-[#a1a1aa] dark:border-[#3f3f46] font-mono text-xs text-[#09090b] dark:text-[#d4d4d4] whitespace-pre-wrap leading-relaxed select-all">
            {annexureText}
          </div>
        </div>

        {/* Modal Footer Controls */}
        <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border-t border-[#18181b] dark:border-[#262626] p-4 flex flex-wrap items-center justify-between gap-3 font-mono">
          <div className="text-[11px] text-[#71717a] dark:text-[#666666]">
            Simulated: this tool prepares the draft only. Nothing is sent to any portal or VASP.
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCopy}
              className="px-3.5 py-2 bg-[#ffffff] dark:bg-[#1a1a1a] hover:bg-[#f4f4f5] dark:hover:bg-[#262626] text-[#09090b] dark:text-[#f5f5f5] text-xs font-semibold flex items-center gap-1.5 border border-[#18181b] dark:border-[#262626] hover:border-[#627EEA] transition-colors cursor-pointer brutal-press"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
              <span>{copied ? 'Copied' : 'Copy Notice + Annexure'}</span>
            </button>

            <button
              type="button"
              disabled={submitted}
              onClick={handleSimulateSubmit}
              className="px-4 py-2 bg-[#18181b] dark:bg-[#627EEA] hover:bg-[#627EEA] dark:hover:bg-[#748ef5] text-white text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer brutal-press shadow-[3px_3px_0px_#000]"
            >
              <Send className="w-4 h-4" />
              <span>{submitted ? 'Marked as prepared' : 'Mark as prepared'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
