import { useRef } from 'react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(useGSAP);

/**
 * MarqueeTicker — Infinite horizontal scrolling text bar
 * 
 * Neo-brutalist design element: a raw, monospace ticker strip
 * with Ethereum purple square separators. Scrolls infinitely
 * using GSAP's repeat: -1 for buttery smooth performance.
 * Content is duplicated for seamless looping.
 */
const TICKER_ITEMS = [
  'Forward BFS Trace',
  'FIFO Taint Accounting',
  'Exchange Attribution',
  'Cybercrime Law & IPC',
  'Multi-Chain EVM',
  'Peel Chain Detection',
  'Deposit Consolidation',
  'VASP Identification',
  'Confidence Scoring',
  'SAHYOG / I4C Workflow',
  'KYC Chokepoint Analysis',
  'Crypto Forensics',
];

export default function MarqueeTicker() {
  const tickerRef = useRef(null);
  const trackRef = useRef(null);

  useGSAP(() => {
    const track = trackRef.current;
    if (!track) return;

    gsap.to(track, {
      xPercent: -50,
      duration: 40,
      ease: 'none',
      repeat: -1,
    });
  }, { scope: tickerRef });

  const renderItems = () =>
    TICKER_ITEMS.map((item, i) => (
      <span key={i} className="flex items-center gap-6 shrink-0">
        <span className="text-xs font-mono uppercase tracking-[0.15em] text-[#71717a] dark:text-[#a3a3a3] whitespace-nowrap">
          {item}
        </span>
        <span className="w-2 h-2 bg-[#627EEA] shrink-0" aria-hidden="true" />
      </span>
    ));

  return (
    <div
      ref={tickerRef}
      className="w-full border-y border-[#d4d4d8] dark:border-[#2a2a2a] bg-[#ffffff]/80 dark:bg-[#0a0a0a]/80 py-4 overflow-hidden relative z-20"
    >
      <div
        ref={trackRef}
        className="flex items-center gap-6 will-change-transform"
        style={{ width: 'max-content' }}
      >
        {/* Duplicate content for seamless loop */}
        {renderItems()}
        {renderItems()}
      </div>
    </div>
  );
}
