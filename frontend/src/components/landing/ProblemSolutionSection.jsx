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
          <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-[#ffffff] dark:bg-[#111111] border border-red-500/30 text-red-600 dark:text-red-400 text-xs font-mono shadow-[2px_2px_0px_rgba(239,68,68,0.4)]">
            <span>The Investigative Dilemma</span>
            <span className="text-[#a1a1aa] dark:text-[#555555]">•</span>
            <span>Why Chokepoint Tracing Works</span>
          </div>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-[#09090b] dark:text-[#f5f5f5]">
            Why We Target Exchanges, Not Burner Wallets
          </h2>
          <p className="text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3] leading-relaxed">
            Unhosted wallets have no identity records. Regulated exchanges hold KYC records and bank accounts.
            Here is the technical reasoning behind our chokepoint approach.
          </p>
        </div>

        {/* Comparison Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 lg:gap-8 items-stretch">
          {/* Card 1: The Conventional Trap */}
          <div className="paradigm-card bg-[#ffffff] dark:bg-[#111111] border-2 border-[#18181b] dark:border-[#262626] border-l-4 border-l-red-500 p-6 sm:p-8 flex flex-col justify-between space-y-6 relative overflow-hidden group hover:border-red-500 transition-all shadow-[4px_4px_0px_#18181b] dark:shadow-[4px_4px_0px_#000]">
            <div className="space-y-4">
              <div className="w-12 h-12 bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-600 dark:text-red-400">
                <Flame className="w-6 h-6" />
              </div>

              <div className="space-y-1">
                <span className="text-xs font-mono uppercase tracking-wider text-red-600 dark:text-red-400 font-semibold">
                  The Conventional Dead End
                </span>
                <h3 className="text-xl sm:text-2xl font-bold text-[#09090b] dark:text-[#f5f5f5]">
                  Chasing Disposable Burner Wallets
                </h3>
              </div>

              <p className="text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3] leading-relaxed">
                Investigators often treat every intermediate wallet as an individual suspect,
                trying to identify who owns each address along the path.
              </p>

              <div className="space-y-3 pt-3">
                <div className="flex items-start gap-3 text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3]">
                  <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  <span>
                    <strong className="text-[#09090b] dark:text-[#f5f5f5]">Zero Identity Records:</strong> Anyone can generate thousands of unhosted EVM addresses on a computer in seconds. No KYC, no name, and no registration exists.
                  </span>
                </div>

                <div className="flex items-start gap-3 text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3]">
                  <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  <span>
                    <strong className="text-[#09090b] dark:text-[#f5f5f5]">Disposable Hops:</strong> Criminals use automated scripts to peel and split funds through wallets that are abandoned immediately after a single transfer.
                  </span>
                </div>

                <div className="flex items-start gap-3 text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3]">
                  <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  <span>
                    <strong className="text-[#09090b] dark:text-[#f5f5f5]">Uncertain Taint:</strong> Standard block explorers do not distinguish between stolen funds and existing wallet balances, leading to flawed attribution in court.
                  </span>
                </div>

                <div className="flex items-start gap-3 text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3]">
                  <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  <span>
                    <strong className="text-[#09090b] dark:text-[#f5f5f5]">No Legal Entity:</strong> Police cannot serve a court order to a private key or demand customer records from an anonymous software wallet.
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-red-500/20 p-3 text-xs text-red-600 dark:text-red-300 font-mono">
              Result: Weeks spent chasing dead ends while funds cash out into fiat currency unrecovered.
            </div>
          </div>

          {/* Card 2: The ChainSAHYOG Breakthrough */}
          <div className="paradigm-card bg-[#ffffff] dark:bg-[#111111] border-2 border-[#18181b] dark:border-[#262626] border-l-4 border-l-emerald-500 p-6 sm:p-8 flex flex-col justify-between space-y-6 relative overflow-hidden group hover:border-emerald-500 transition-all shadow-[4px_4px_0px_#18181b] dark:shadow-[4px_4px_0px_#000]">
            <div className="space-y-4">
              <div className="w-12 h-12 bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
                <ShieldCheck className="w-6 h-6" />
              </div>

              <div className="space-y-1">
                <span className="text-xs font-mono uppercase tracking-wider text-emerald-600 dark:text-emerald-400 font-semibold">
                  The ChainSAHYOG Approach
                </span>
                <h3 className="text-xl sm:text-2xl font-bold text-[#09090b] dark:text-[#f5f5f5]">
                  Targeting the Regulated Exchange
                </h3>
              </div>

              <p className="text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3] leading-relaxed">
                Crypto cannot be spent in the real economy without conversion. To cash out into Indian Rupees (INR)
                via domestic or international banking channels, funds must eventually deposit into a Centralized Exchange.
              </p>

              <div className="space-y-3 pt-3">
                <div className="flex items-start gap-3 text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3]">
                  <CheckCircle className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                  <span>
                    <strong className="text-[#09090b] dark:text-[#f5f5f5]">Mandatory Identity Verification:</strong> Regulated exchanges (Binance, WazirX, CoinDCX) hold verified identity documents (PAN, Aadhaar, Passport) and linked bank accounts.
                  </span>
                </div>

                <div className="flex items-start gap-3 text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3]">
                  <CheckCircle className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                  <span>
                    <strong className="text-[#09090b] dark:text-[#f5f5f5]">Recognizable On-Chain Fingerprint:</strong> Exchanges manage massive multi-million dollar deposit sweep architectures that cannot hide on the public blockchain.
                  </span>
                </div>

                <div className="flex items-start gap-3 text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3]">
                  <CheckCircle className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                  <span>
                    <strong className="text-[#09090b] dark:text-[#f5f5f5]">FIFO Accounting Math:</strong> Applying First-In-First-Out ledger replay isolates the exact portion of stolen funds reaching the exchange from pre-existing balances.
                  </span>
                </div>

                <div className="flex items-start gap-3 text-xs sm:text-sm text-[#52525b] dark:text-[#a3a3a3]">
                  <CheckCircle className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                  <span>
                    <strong className="text-[#09090b] dark:text-[#f5f5f5]">Enforceable Legal Notice:</strong> Police serve statutory requisitions under cybercrime procedure and the IPC via SAHYOG to freeze accounts before withdrawal.
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-emerald-500/20 p-3 text-xs text-emerald-700 dark:text-emerald-300 font-mono">
              Result: Real customer identity unmasked, bank accounts frozen, and court-tested evidence prepared.
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
