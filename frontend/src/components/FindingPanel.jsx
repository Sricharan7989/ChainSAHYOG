import { useRef, useState } from 'react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { FileText, Route, ShieldAlert, CheckCircle2 } from 'lucide-react';
import HeadlineCard from './findings/HeadlineCard';
import ConfidenceMeter from './findings/ConfidenceMeter';
import TaintCard from './findings/TaintCard';
import CrossChainCard from './findings/CrossChainCard';
import TypologiesCard from './findings/TypologiesCard';
import ClustersCard from './findings/ClustersCard';
import RiskFlagsCard from './findings/RiskFlagsCard';
import PathTimeline from './findings/PathTimeline';
import TokenWarningsCard from './findings/TokenWarningsCard';
import { findPath } from '../utils/pathfinder';

gsap.registerPlugin(useGSAP);

export default function FindingPanel({
  data,
  onOpenSahyog,
  onDownloadReport,
  onSelectAddress,
}) {
  const panelRef = useRef(null);
  // 'summary' | 'trail' | 'evidence'
  const [activeTab, setActiveTab] = useState('summary');

  useGSAP(() => {
    if (data) {
      gsap.from(panelRef.current, {
        x: 20,
        opacity: 0,
        duration: 0.5,
        ease: 'power3.out',
      });
    }
  }, { dependencies: [data], scope: panelRef });

  if (!data) return null;

  // The ENDPOINT as a graph node id. Once a trace crosses a chain, the summary's
  // `address` is the bare wallet address while the node carrying it is qualified
  // ("arbitrum:0x..."). Matching on the bare address would find no route at all,
  // and the money trail would silently vanish from a cross-chain trace - so prefer
  // the node id the backend already resolved.
  const targetAddress = data.summary?.node_id || data.summary?.address;
  const startAddress = data.start_address;
  const pathEdges = findPath(data.edges, startAddress, targetAddress);

  return (
    <div
      ref={panelRef}
      className="flex flex-col gap-3.5 w-full h-full overflow-y-auto pr-0.5"
    >
      {/* 3 Intuitive Tabs: Plain-English & High-Contrast */}
      <div className="flex items-center gap-1.5 p-1 bg-white dark:bg-[#111111] border-2 border-[#18181b] dark:border-[#262626] shadow-[2px_2px_0px_#18181b] dark:shadow-[2px_2px_0px_#000000]">
        <button
          type="button"
          onClick={() => setActiveTab('summary')}
          className={`flex-1 py-1.5 px-2.5 text-xs font-mono transition-all cursor-pointer brutal-press flex items-center justify-center gap-1.5 ${
            activeTab === 'summary'
              ? 'bg-[#627EEA]/15 text-[#627EEA] border border-[#627EEA] shadow-[2px_2px_0px_#627EEA] font-bold'
              : 'text-[#52525b] dark:text-[#a3a3a3] hover:text-[#09090b] dark:hover:text-[#f5f5f5] hover:bg-[#f4f4f5] dark:hover:bg-[#1a1a1a] border border-transparent font-medium'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>Case Summary</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('trail')}
          className={`flex-1 py-1.5 px-2.5 text-xs font-mono transition-all cursor-pointer brutal-press flex items-center justify-center gap-1.5 ${
            activeTab === 'trail'
              ? 'bg-[#627EEA]/15 text-[#627EEA] border border-[#627EEA] shadow-[2px_2px_0px_#627EEA] font-bold'
              : 'text-[#52525b] dark:text-[#a3a3a3] hover:text-[#09090b] dark:hover:text-[#f5f5f5] hover:bg-[#f4f4f5] dark:hover:bg-[#1a1a1a] border border-transparent font-medium'
          }`}
        >
          <Route className="w-3.5 h-3.5" />
          <span>Money Trail ({pathEdges.length} {pathEdges.length === 1 ? 'hop' : 'hops'})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('evidence')}
          className={`flex-1 py-1.5 px-2.5 text-xs font-mono transition-all cursor-pointer brutal-press flex items-center justify-center gap-1.5 ${
            activeTab === 'evidence'
              ? 'bg-[#627EEA]/15 text-[#627EEA] border border-[#627EEA] shadow-[2px_2px_0px_#627EEA] font-bold'
              : 'text-[#52525b] dark:text-[#a3a3a3] hover:text-[#09090b] dark:hover:text-[#f5f5f5] hover:bg-[#f4f4f5] dark:hover:bg-[#1a1a1a] border border-transparent font-medium'
          }`}
        >
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>Forensic Evidence</span>
        </button>
      </div>

      {/* TAB 1: CASE SUMMARY & ACTION (Executive Verdict for Naive User) */}
      {activeTab === 'summary' && (
        <div className="space-y-3.5 animate-in fade-in duration-150">
          <HeadlineCard
            summary={data.summary}
            params={data.params}
            onOpenSahyog={onOpenSahyog}
            onDownloadReport={onDownloadReport}
          />

          <RiskFlagsCard
            riskFlags={data.risk_flags}
            explorerBase={data.params?.explorer}
          />

          {/* Quick Legal Guidance Box */}
          <div className="bg-white dark:bg-[#111111] border border-[#d4d4d8] dark:border-[#262626] p-4 space-y-2 shadow-[2px_2px_0px_#18181b] dark:shadow-[2px_2px_0px_#000000]">
            <h4 className="font-bold text-xs uppercase tracking-wider text-[#09090b] dark:text-[#f5f5f5] flex items-center gap-1.5 font-mono">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              Investigator Action Checklist
            </h4>
            <ol className="text-xs text-[#52525b] dark:text-[#a3a3a3] space-y-1.5 list-decimal pl-4 leading-relaxed font-sans">
              <li>
                Click <strong className="text-[#09090b] dark:text-[#f5f5f5]">Route to SAHYOG</strong> to generate an official freeze notice under Indian cybercrime laws.
              </li>
              <li>
                Export and print the <strong className="text-[#09090b] dark:text-[#f5f5f5]">PDF Dossier</strong> to attach with the formal FIR / Case Diary.
              </li>
              <li>
                Inspect the <strong className="text-[#09090b] dark:text-[#f5f5f5]">Money Trail</strong> tab if you need individual transaction hashes for court submission.
              </li>
            </ol>
          </div>
        </div>
      )}

      {/* TAB 2: MONEY TRAIL (Chronological Hop Story) */}
      {activeTab === 'trail' && (
        <div className="space-y-3.5 animate-in fade-in duration-150">
          <PathTimeline
            pathEdges={pathEdges}
            startAddress={startAddress}
            targetAddress={targetAddress}
            summary={data.summary}
            explorerBase={data.params?.explorer}
            onSelectAddress={onSelectAddress}
          />
        </div>
      )}

      {/* TAB 3: FORENSIC EVIDENCE (Deep Auditable Telemetry) */}
      {activeTab === 'evidence' && (
        <div className="space-y-3.5 animate-in fade-in duration-150">
          <ConfidenceMeter
            score={data.summary?.confidence_score}
            breakdown={data.summary?.confidence_breakdown}
            components={data.summary?.confidence_components}
            method={data.summary?.method}
          />

          <TaintCard summary={data.summary} accounting={data.accounting} />

          <TypologiesCard
            typologies={data.typologies}
            summary={data.typology_summary}
          />

          <CrossChainCard cross={data.cross_chain} />

          <ClustersCard clusters={data.clusters} />

          <TokenWarningsCard tokenWarnings={data.token_warnings} />
        </div>
      )}
    </div>
  );
}
