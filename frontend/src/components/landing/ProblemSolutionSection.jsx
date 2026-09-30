import { useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { XCircle, CheckCircle, ShieldCheck, Flame } from 'lucide-react';

gsap.registerPlugin(useGSAP, ScrollTrigger);

export default function ProblemSolutionSection() {
  const containerRef = useRef(null);

  useGSAP(() => {
    gsap.fromTo(
      '.paradigm-card',
      { y: 30, opacity: 0 },
      {
        y: 0,
        opacity: 1,
        duration: 0.6,
        stagger: 0.15,
        ease: 'power2.out',
        scrollTrigger: {
          trigger: containerRef.current,
          start: 'top 85%',
          toggleActions: 'play none none none',
        },
      }
    );
  }, { scope: containerRef });

  return (
    <section ref={containerRef} className="py-16 px-4 lg:px-8 relative">
      <div className="max-w-6xl mx-auto space-y-12">
        {/* Title */}
        <div className="text-center space-y-3 max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-500/30 text-red-700 dark:text-red-400 text-xs font-mono">
            <span>The Investigative Dilemma</span>
            <span className="text-slate-400 dark:text-zinc-500">•</span>
            <span>Why Chokepoint Tracing Works</span>
          </div>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 dark:text-zinc-100">
            Why We Target Exchanges, Not Burner Wallets
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-zinc-400 leading-relaxed">
            Unhosted wallets have no identity records. Regulated exchanges hold KYC records and bank accounts.
            Here is the technical reasoning behind our chokepoint approach.
          </p>
        </div>

        {/* Comparison Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 lg:gap-8 items-stretch">
          {/* Card 1: The Conventional Trap */}
          <div className="paradigm-card bg-white dark:bg-zinc-950/80 border border-red-200 dark:border-red-900/40 rounded-2xl p-6 sm:p-8 flex flex-col justify-between space-y-6 relative overflow-hidden group hover:border-red-400 dark:hover:border-red-500/50 transition-colors shadow-sm">
            <div className="space-y-4">
              <div className="w-12 h-12 rounded-xl bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 flex items-center justify-center text-red-600 dark:text-red-400">
                <Flame className="w-6 h-6" />
              </div>

              <div className="space-y-1">
                <span className="text-xs font-mono uppercase tracking-wider text-red-600 dark:text-red-400 font-semibold">
                  The Conventional Dead End
                </span>
                <h3 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-zinc-100">
                  Chasing Disposable Burner Wallets
                </h3>
              </div>

              <p className="text-xs sm:text-sm text-slate-600 dark:text-zinc-400 leading-relaxed">
                Investigators often treat every intermediate wallet as an individual suspect,
                trying to identify who owns each address along the path.
              </p>

              <div className="space-y-3 pt-3">
                <div className="flex items-start gap-3 text-xs sm:text-sm text-slate-700 dark:text-zinc-300">
                  <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  <span>
                    <strong>Zero Identity Records:</strong> Anyone can generate thousands of unhosted EVM addresses on a computer in seconds. No KYC, no name, and no registration exists.
                  </span>
                </div>

                <div className="flex items-start gap-3 text-xs sm:text-sm text-slate-700 dark:text-zinc-300">
                  <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  <span>
                    <strong>Disposable Hops:</strong> Criminals use automated scripts to peel and split funds through wallets that are abandoned immediately after a single transfer.
                  </span>
                </div>

                <div className="flex items-start gap-3 text-xs sm:text-sm text-slate-700 dark:text-zinc-300">
                  <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  <span>
                    <strong>Uncertain Taint:</strong> Standard block explorers do not distinguish between stolen funds and existing wallet balances, leading to flawed attribution in court.
                  </span>
                </div>

                <div className="flex items-start gap-3 text-xs sm:text-sm text-slate-700 dark:text-zinc-300">
                  <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  <span>
                    <strong>No Legal Entity:</strong> Police cannot serve a court order to a private key or demand customer records from an anonymous software wallet.
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/30 rounded-xl p-3 text-xs text-red-700 dark:text-red-300/90 font-mono">
              Result: Weeks spent chasing dead ends while funds cash out into fiat currency unrecovered.
            </div>
          </div>

          {/* Card 2: The ChainSAHYOG Breakthrough */}
          <div className="paradigm-card bg-white dark:bg-zinc-950/80 border border-emerald-200 dark:border-emerald-900/40 rounded-2xl p-6 sm:p-8 flex flex-col justify-between space-y-6 relative overflow-hidden group hover:border-emerald-400 dark:hover:border-emerald-500/50 transition-colors shadow-sm">
            <div className="space-y-4">
              <div className="w-12 h-12 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
                <ShieldCheck className="w-6 h-6" />
              </div>

              <div className="space-y-1">
                <span className="text-xs font-mono uppercase tracking-wider text-emerald-600 dark:text-emerald-400 font-semibold">
                  The ChainSAHYOG Approach
                </span>
                <h3 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-zinc-100">
                  Targeting the Regulated Exchange
                </h3>
              </div>

              <p className="text-xs sm:text-sm text-slate-600 dark:text-zinc-400 leading-relaxed">
                Crypto cannot be spent in the real economy without conversion. To cash out to rupees or dollars,
                funds must eventually deposit into a Centralized Exchange.
              </p>

              <div className="space-y-3 pt-3">
                <div className="flex items-start gap-3 text-xs sm:text-sm text-slate-700 dark:text-zinc-300">
                  <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  <span>
                    <strong>Mandatory Identity Verification:</strong> Regulated exchanges (Binance, WazirX, CoinDCX) hold verified identity documents (PAN, Aadhaar, Passport) and linked bank accounts.
                  </span>
                </div>

                <div className="flex items-start gap-3 text-xs sm:text-sm text-slate-700 dark:text-zinc-300">
                  <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  <span>
                    <strong>Recognizable On-Chain Fingerprint:</strong> Exchanges manage massive multi-million dollar deposit sweep architectures that cannot hide on the public blockchain.
                  </span>
                </div>

                <div className="flex items-start gap-3 text-xs sm:text-sm text-slate-700 dark:text-zinc-300">
                  <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  <span>
                    <strong>FIFO Accounting Math:</strong> Applying the First-In-First-Out rule isolates the exact portion of stolen funds reaching the exchange from pre-existing balances.
                  </span>
                </div>

                <div className="flex items-start gap-3 text-xs sm:text-sm text-slate-700 dark:text-zinc-300">
                  <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  <span>
                    <strong>Enforceable Legal Notice:</strong> Police serve statutory notices under Section 91 CrPC (Section 94 BNSS) via SAHYOG to freeze accounts before withdrawal.
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/30 rounded-xl p-3 text-xs text-emerald-800 dark:text-emerald-300/90 font-mono">
              Result: Real customer identity unmasked, bank accounts frozen, and court-tested evidence prepared.
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
