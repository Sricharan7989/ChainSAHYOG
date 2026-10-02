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

  const targetExchange = data.summary?.exchange || 'VASP Compliance Officer';
  const targetWallet = data.summary?.address;
  const startWallet = data.start_address;
  const caseId = `I4C-SAHYOG-2026-${startWallet.slice(2, 8).toUpperCase()}`;
  const amountStr = formatAssets(data.summary?.tainted_value_received || data.summary?.value_received);

  const noticeText = `GOVERNMENT OF INDIA
MINISTRY OF HOME AFFAIRS — INDIAN CYBER CRIME COORDINATION CENTRE (I4C)
NOTICE UNDER CYBERCRIME PROVISIONS & THE INDIAN PENAL CODE (IPC)
PORTAL REFERENCE: ${caseId}

TO: Compliance & Legal Enquiries Division, ${targetExchange}
SUBJECT: URGENT PRESERVATION & DISCLOSURE OF KYC RECORDS (CYBER INCIDENT INVESTIGATION)

1. During the ongoing investigation of cyber fraud/theft involving suspect wallet address [${startWallet}], forensic blockchain intelligence established that illicit funds totaling approximately [${amountStr}] were deposited into your institution at address:
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
                <span>SAHYOG Lawful Notice Generator</span>
                <span className="text-[10px] font-mono px-2 py-0.5 bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/40 uppercase">
                  Ready to File
                </span>
              </h3>
              <p className="text-xs text-[#71717a] dark:text-[#888888] font-mono">
                Case ID: {caseId} · Routed to {targetExchange}
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
            <span>Framework: Indian Cybercrime Law & IPC</span>
            <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
              <Lock className="w-3.5 h-3.5" />
              <span>LEA Verified Notice</span>
            </span>
          </div>

          <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] p-4 border border-[#18181b] dark:border-[#262626] font-mono text-xs text-[#09090b] dark:text-[#d4d4d4] whitespace-pre-wrap leading-relaxed select-all">
            {noticeText}
          </div>
        </div>

        {/* Modal Footer Controls */}
        <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border-t border-[#18181b] dark:border-[#262626] p-4 flex flex-wrap items-center justify-between gap-3 font-mono">
          <div className="text-[11px] text-[#71717a] dark:text-[#666666]">
            Simulated workflow for demonstration · No external notice sent.
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCopy}
              className="px-3.5 py-2 bg-[#ffffff] dark:bg-[#1a1a1a] hover:bg-[#f4f4f5] dark:hover:bg-[#262626] text-[#09090b] dark:text-[#f5f5f5] text-xs font-semibold flex items-center gap-1.5 border border-[#18181b] dark:border-[#262626] hover:border-[#627EEA] transition-colors cursor-pointer brutal-press"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
              <span>{copied ? 'Copied' : 'Copy Notice'}</span>
            </button>

            <button
              type="button"
              disabled={submitted}
              onClick={handleSimulateSubmit}
              className="px-4 py-2 bg-[#18181b] dark:bg-[#627EEA] hover:bg-[#627EEA] dark:hover:bg-[#748ef5] text-white text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer brutal-press shadow-[3px_3px_0px_#000]"
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
