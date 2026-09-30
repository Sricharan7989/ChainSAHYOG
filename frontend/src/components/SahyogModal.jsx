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
        { opacity: 1, duration: 0.3 }
      );
      gsap.fromTo(
        modalRef.current,
        { scale: 0.9, opacity: 0, y: 20 },
        { scale: 1, opacity: 1, y: 0, duration: 0.4, ease: 'back.out(1.5)' }
      );
    }
  }, { dependencies: [isOpen] });

  if (!isOpen || !data) return null;

  const targetExchange = data.summary?.exchange || 'VASP Compliance Officer';
  const targetWallet = data.summary?.address;
  const startWallet = data.start_address;
  const caseId = `I4C-SAHYOG-2026-${startWallet.slice(2, 8).toUpperCase()}`;
  const amountStr = formatAssets(data.summary?.tainted_value_received || data.summary?.value_received);

  const noticeText = `GOVERNMENT OF INDIA
MINISTRY OF HOME AFFAIRS — INDIAN CYBER CRIME COORDINATION CENTRE (I4C)
NOTICE UNDER SECTION 91 Cr.P.C. / SECTION 94 BNSS, 2023
PORTAL REFERENCE: ${caseId}

TO: Compliance & Legal Enquiries Division, ${targetExchange}
SUBJECT: URGENT PRESERVATION & DISCLOSURE OF KYC RECORDS (CYBER INCIDENT INVESTIGATION)

1. During the investigation of cyber fraud/theft involving suspect wallet address [${startWallet}], forensic blockchain intelligence established that illicit funds totaling approximately [${amountStr}] were deposited into your institution at address:
   Target Deposit Wallet: ${targetWallet}
   Hops Traversed: ${data.summary?.hop_distance} hops
   Attribution Confidence: ${data.summary?.confidence_score}%

2. Under statutory powers vested under law, you are hereby directed to:
   a. Immediately PRESERVE all account records, activity logs, and balances linked to wallet address [${targetWallet}].
   b. Disclose certified copies of full KYC documentation:
      - Full Legal Name & Verified Identity Proof (Passport / Aadhaar / National ID)
      - Registered Email Address, Telephone Number, and Residential Address
      - Associated Fiat Bank Account details and withdrawal records
      - IP Access Logs (with timestamps and port numbers) for account creation and deposit sessions.

3. This request is transmitted electronically through the SAHYOG Law Enforcement Coordination Platform.

Authorized Signatory / Cybercrime Investigation Officer
National Cybercrime Reporting Portal (NCRP), I4C`;

  const handleCopy = () => {
    navigator.clipboard.writeText(noticeText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    onShowToast('SAHYOG Notice copied to clipboard');
  };

  const handleSimulateSubmit = () => {
    setSubmitted(true);
    onShowToast(`Simulated request successfully filed with ${targetExchange} via SAHYOG`);
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
        className="fixed inset-0 bg-black/80 backdrop-blur-sm"
      />

      {/* Modal Dialog */}
      <div
        ref={modalRef}
        className="relative z-10 w-full max-w-2xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
      >
        {/* Modal Header */}
        <div className="bg-linear-to-r from-cyan-50/60 via-white to-white dark:from-cyan-950 dark:via-zinc-900 dark:to-zinc-900 border-b border-slate-200 dark:border-zinc-800 p-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 dark:bg-cyan-500/20 border border-cyan-500/30 dark:border-cyan-500/40 flex items-center justify-center text-cyan-600 dark:text-cyan-400">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-base text-slate-900 dark:text-zinc-100 flex items-center gap-2">
                <span>SAHYOG Lawful Notice Generator</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30">
                  Ready to File
                </span>
              </h3>
              <p className="text-xs text-slate-500 dark:text-zinc-400 font-mono">
                Case ID: {caseId} · Routed to {targetExchange}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-slate-400 dark:text-zinc-400 hover:text-slate-700 dark:hover:text-zinc-200 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-lg transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Notice Preview Content */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          <div className="flex items-center justify-between text-xs text-slate-600 dark:text-zinc-400 bg-slate-50 dark:bg-zinc-950 px-3 py-2 rounded-lg border border-slate-200 dark:border-zinc-800 font-mono">
            <span>Standard: Section 91 CrPC / Section 94 BNSS</span>
            <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
              <Lock className="w-3.5 h-3.5" />
              <span>LEA Verified Standard</span>
            </span>
          </div>

          <div className="bg-slate-50 dark:bg-zinc-950 p-4 rounded-xl border border-slate-200 dark:border-zinc-800 font-mono text-xs text-slate-800 dark:text-zinc-300 whitespace-pre-wrap leading-relaxed select-all">
            {noticeText}
          </div>
        </div>

        {/* Modal Footer Controls */}
        <div className="bg-slate-50 dark:bg-zinc-950 border-t border-slate-200 dark:border-zinc-800 p-4 flex flex-wrap items-center justify-between gap-3">
          <div className="text-[11px] text-slate-500 dark:text-zinc-500">
            Simulated workflow for demonstration · No actual notice is sent outside this local instance.
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCopy}
              className="px-3.5 py-2 rounded-lg bg-white dark:bg-zinc-800 hover:bg-slate-100 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-200 text-xs font-semibold flex items-center gap-1.5 border border-slate-200 dark:border-zinc-700 transition-colors cursor-pointer"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
              <span>{copied ? 'Copied' : 'Copy Notice'}</span>
            </button>

            <button
              type="button"
              disabled={submitted}
              onClick={handleSimulateSubmit}
              className="px-4 py-2 rounded-lg bg-linear-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-semibold shadow-lg shadow-emerald-500/20 flex items-center gap-1.5 active:scale-95 transition-all cursor-pointer"
            >
              <Send className="w-4 h-4" />
              <span>{submitted ? 'Routing to SAHYOG…' : 'Transmit to SAHYOG'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
