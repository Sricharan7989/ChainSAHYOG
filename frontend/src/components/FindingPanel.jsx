import { useRef, useState } from 'react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import HeadlineCard from './findings/HeadlineCard';
import ConfidenceMeter from './findings/ConfidenceMeter';
import TaintCard from './findings/TaintCard';
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
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'forensics' | 'trail'

  useGSAP(() => {
    if (data) {
      gsap.from(panelRef.current, {
        x: 30,
        opacity: 0,
        duration: 0.6,
        ease: 'power3.out',
      });
    }
  }, { dependencies: [data], scope: panelRef });

  if (!data) return null;

  const targetAddress = data.summary?.address;
  const startAddress = data.start_address;
  const pathEdges = findPath(data.edges, startAddress, targetAddress);

  return (
    <div
      ref={panelRef}
      className="flex flex-col gap-4 w-full h-full overflow-y-auto pr-1"
    >
      {/* Category Tabs Navigation */}
      <div className="flex items-center gap-1.5 p-1 bg-slate-100 dark:bg-zinc-900/90 border border-slate-200 dark:border-zinc-800 rounded-xl">
        <button
          type="button"
          onClick={() => setActiveTab('overview')}
          className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
            activeTab === 'overview'
              ? 'bg-white dark:bg-zinc-800 text-cyan-700 dark:text-cyan-300 border border-slate-200 dark:border-transparent shadow-xs'
              : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200'
          }`}
        >
          Attribution Overview
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('forensics')}
          className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
            activeTab === 'forensics'
              ? 'bg-white dark:bg-zinc-800 text-cyan-700 dark:text-cyan-300 border border-slate-200 dark:border-transparent shadow-xs'
              : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200'
          }`}
        >
          Laundering Forensics
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('trail')}
          className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
            activeTab === 'trail'
              ? 'bg-white dark:bg-zinc-800 text-cyan-700 dark:text-cyan-300 border border-slate-200 dark:border-transparent shadow-xs'
              : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200'
          }`}
        >
          Trail Steps ({pathEdges.length})
        </button>
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div className="space-y-4 animate-in fade-in duration-200">
          <HeadlineCard
            summary={data.summary}
            params={data.params}
            onOpenSahyog={onOpenSahyog}
            onDownloadReport={onDownloadReport}
          />

          <ConfidenceMeter
            score={data.summary?.confidence_score}
            breakdown={data.summary?.confidence_breakdown}
            components={data.summary?.confidence_components}
            method={data.summary?.method}
          />

          <TaintCard summary={data.summary} accounting={data.accounting} />

          <RiskFlagsCard
            riskFlags={data.risk_flags}
            explorerBase={data.params?.explorer}
          />
        </div>
      )}

      {/* TAB 2: FORENSICS */}
      {activeTab === 'forensics' && (
        <div className="space-y-4 animate-in fade-in duration-200">
          <TypologiesCard
            typologies={data.typologies}
            summary={data.typology_summary}
          />

          <ClustersCard clusters={data.clusters} />

          <TokenWarningsCard tokenWarnings={data.token_warnings} />
        </div>
      )}

      {/* TAB 3: TRAIL STEPS */}
      {activeTab === 'trail' && (
        <div className="space-y-4 animate-in fade-in duration-200">
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
    </div>
  );
}
