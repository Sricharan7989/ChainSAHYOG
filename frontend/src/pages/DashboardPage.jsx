import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { Shield, Database, Activity, FileText } from 'lucide-react';
import Navbar from '../components/Navbar';
import SearchBar from '../components/SearchBar';
import DemoChips from '../components/DemoChips';
import LoadingRadar from '../components/LoadingRadar';
import TraceGraph from '../components/TraceGraph';
import NodeDrawer from '../components/NodeDrawer';
import FindingPanel from '../components/FindingPanel';
import SahyogModal from '../components/SahyogModal';
import Toast from '../components/Toast';
import { fetchHealth, fetchDemos, runTrace, getReportUrl } from '../api/client';

gsap.registerPlugin(useGSAP);

export default function DashboardPage() {
  const [searchParams] = useSearchParams();
  const initialAddress = searchParams.get('address') || '';
  const initialChain = searchParams.get('chain') ? Number(searchParams.get('chain')) : 1;

  // Trace Parameters
  const [address, setAddress] = useState(initialAddress);
  const [selectedChainId, setSelectedChainId] = useState(initialChain);
  const [maxDepth, setMaxDepth] = useState(4);
  const [dustThreshold, setDustThreshold] = useState(0.001);
  const [mode, setMode] = useState('auto');
  const [saveDemo, setSaveDemo] = useState(false);

  // Application Data & State
  const [health, setHealth] = useState(null);
  const [demos, setDemos] = useState([]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);

  // Inspector & Modal State
  const [selectedNode, setSelectedNode] = useState(null);
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [isSahyogOpen, setIsSahyogOpen] = useState(false);

  // Animation Refs
  const workspaceRef = useRef(null);

  // 1. Initial Load: Fetch Health and Cached Demos
  useEffect(() => {
    async function init() {
      try {
        const healthData = await fetchHealth();
        setHealth(healthData);
      } catch (err) {
        console.warn('Backend /health unreachable:', err);
      }

      try {
        const demosData = await fetchDemos();
        setDemos(demosData.demos || []);
      } catch (err) {
        console.warn('Could not load demo traces:', err);
      }
    }
    init();
  }, []);

  // 2. Execute Trace
  const handleTrace = useCallback(async (overrideAddress = null, overrideChainId = null) => {
    const targetAddr = (overrideAddress || address).trim();
    if (!targetAddr) return;

    const chain = overrideChainId || selectedChainId;
    setLoading(true);
    setError(null);
    setSelectedNode(null);
    setSelectedEdge(null);

    try {
      const result = await runTrace({
        address: targetAddr,
        chainId: chain,
        maxDepth,
        dustThreshold,
        mode,
        save: saveDemo,
      });
      setData(result);
      setToast({ type: 'success', message: 'Forensic trace completed successfully.' });
    } catch (err) {
      console.error('Trace execution failed:', err);
      setError(err.message || 'Trace could not be executed.');
      setToast({ type: 'error', message: err.message || 'Trace failed.' });
    } finally {
      setLoading(false);
    }
  }, [address, selectedChainId, maxDepth, dustThreshold, mode, saveDemo]);

  // 3. Auto-trigger trace if URL search params provide an initial address
  useEffect(() => {
    if (initialAddress) {
      const timer = setTimeout(() => {
        handleTrace(initialAddress, initialChain);
      }, 0);
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 4. Demo Selection
  const handleSelectDemo = (demo) => {
    setAddress(demo.address);
    if (demo.chain_id) {
      setSelectedChainId(demo.chain_id);
    }
    handleTrace(demo.address, demo.chain_id || 1);
  };

  // 5. Download Forensic PDF Report
  const handleDownloadReport = () => {
    if (!data?.start_address) return;
    const url = getReportUrl({
      address: data.start_address,
      chainId: data.params?.chain_id || selectedChainId,
      maxDepth: data.params?.max_depth || maxDepth,
      dustThreshold: data.params?.dust_threshold_eth || dustThreshold,
      mode,
    });
    window.open(url, '_blank');
    setToast({ type: 'success', message: 'Generating forensic PDF report…' });
  };

  // 6. Select address from timeline / list
  const handleSelectAddress = (addr) => {
    if (!data?.nodes) return;
    const node = data.nodes.find((n) => n.id.toLowerCase() === addr.toLowerCase());
    if (node) {
      setSelectedNode(node);
      setSelectedEdge(null);
    }
  };

  return (
    <div ref={workspaceRef} className="min-h-screen flex flex-col bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 selection:bg-cyan-500/30 selection:text-cyan-200 transition-colors duration-200">
      {/* Top Navbar & System Status */}
      <Navbar
        health={health}
        selectedChainId={selectedChainId}
        onSelectChain={setSelectedChainId}
        chains={health?.chains?.supported || []}
        variant="dashboard"
      />

      {/* Main Forensic Investigation Canvas (100% Screen Width) */}
      <main className="flex-1 w-full max-w-[1920px] mx-auto p-4 sm:px-6 lg:px-8 py-5 flex flex-col gap-5">
        {/* Search Controls & Demo Picker Header */}
        <section className="flex flex-col gap-2.5">
          <SearchBar
            address={address}
            setAddress={setAddress}
            onTrace={() => handleTrace()}
            loading={loading}
            maxDepth={maxDepth}
            setMaxDepth={setMaxDepth}
            dustThreshold={dustThreshold}
            setDustThreshold={setDustThreshold}
            mode={mode}
            setMode={setMode}
            saveDemo={saveDemo}
            setSaveDemo={setSaveDemo}
          />

          <DemoChips
            demos={demos}
            onSelectDemo={handleSelectDemo}
            selectedAddress={address}
            loading={loading}
          />
        </section>

        {/* Dynamic Main Workspace Area */}
        <div className="flex-1 flex flex-col">
          {/* STATE 1: LOADING (Radar Scanner) */}
          {loading && (
            <div className="flex-1 flex items-center justify-center">
              <LoadingRadar address={address} />
            </div>
          )}

          {/* STATE 2: ERROR STATE */}
          {!loading && error && (
            <div className="bg-red-50 dark:bg-red-950/30 border border-red-300 dark:border-red-500/40 rounded-2xl p-8 text-center space-y-3 max-w-xl mx-auto my-auto shadow-sm">
              <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-400 flex items-center justify-center mx-auto">
                <Shield className="w-6 h-6" />
              </div>
              <h3 className="font-bold text-lg text-red-900 dark:text-red-200">Investigation Trace Halted</h3>
              <p className="text-xs sm:text-sm text-slate-800 dark:text-zinc-300 font-mono bg-white dark:bg-zinc-950 p-3 rounded-lg border border-red-200 dark:border-red-500/20 break-all">
                {error}
              </p>
              <p className="text-xs text-slate-600 dark:text-zinc-400">
                Please verify the wallet address, check your Etherscan key, or test using one of the pre-recorded demo traces.
              </p>
            </div>
          )}

          {/* STATE 3: RESULTS LOADED (Graph + Findings Dashboard) */}
          {!loading && !error && data && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 flex-1 min-h-[640px]">
              {/* Left Column: Cytoscape Money-Flow Visualizer (8 cols on xl) */}
              <div className="lg:col-span-7 xl:col-span-8 flex flex-col relative h-[620px] lg:h-auto min-h-[600px]">
                <TraceGraph
                  data={data}
                  onSelectNode={(node) => {
                    setSelectedNode(node);
                    setSelectedEdge(null);
                  }}
                  onSelectEdge={(edge) => {
                    setSelectedEdge(edge);
                    setSelectedNode(null);
                  }}
                  selectedNodeId={selectedNode?.id}
                  selectedEdgeId={selectedEdge?.id}
                />

                {/* Slide-in Node & Edge Forensics Drawer */}
                <NodeDrawer
                  selectedNode={selectedNode}
                  selectedEdge={selectedEdge}
                  onClose={() => {
                    setSelectedNode(null);
                    setSelectedEdge(null);
                  }}
                  explorerBase={data.params?.explorer}
                />
              </div>

              {/* Right Column: Forensic Findings Panel (4 cols on xl) */}
              <div className="lg:col-span-5 xl:col-span-4 flex flex-col h-[620px] lg:h-auto">
                <FindingPanel
                  data={data}
                  onOpenSahyog={() => setIsSahyogOpen(true)}
                  onDownloadReport={handleDownloadReport}
                  onSelectAddress={handleSelectAddress}
                />
              </div>
            </div>
          )}

          {/* STATE 4: IDLE / WELCOME STATE */}
          {!loading && !error && !data && (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8 sm:p-12 border border-slate-200 dark:border-zinc-800/80 rounded-2xl bg-white dark:bg-zinc-950/40 backdrop-blur-sm space-y-6 my-auto shadow-sm dark:shadow-none">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-600 dark:text-cyan-400 shadow-xl shadow-cyan-500/10">
                <Shield className="w-8 h-8" />
              </div>

              <div className="max-w-md space-y-2">
                <h2 className="text-xl font-bold text-slate-900 dark:text-zinc-100">
                  Ready for Blockchain Attribution
                </h2>
                <p className="text-xs sm:text-sm text-slate-600 dark:text-zinc-400 leading-relaxed">
                  Enter an unhosted suspect wallet address or pick a pre-recorded demo above to trace funds forward to regulated exchange chokepoints.
                </p>
              </div>

              {/* Capability highlights */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-2xl text-left pt-4">
                <div className="bg-slate-50 dark:bg-zinc-900/60 border border-slate-200 dark:border-zinc-800/80 p-3.5 rounded-xl space-y-1">
                  <span className="font-semibold text-xs text-slate-800 dark:text-zinc-200 flex items-center gap-1.5">
                    <Database className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
                    Multi-Chain EVM
                  </span>
                  <p className="text-[11px] text-slate-600 dark:text-zinc-400">
                    Follow funds across Ethereum, Polygon, BNB Chain, and Arbitrum One.
                  </p>
                </div>

                <div className="bg-slate-50 dark:bg-zinc-900/60 border border-slate-200 dark:border-zinc-800/80 p-3.5 rounded-xl space-y-1">
                  <span className="font-semibold text-xs text-slate-800 dark:text-zinc-200 flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                    FIFO Taint Math
                  </span>
                  <p className="text-[11px] text-slate-600 dark:text-zinc-400">
                    Calculates exact stolen balances landing at exchanges via chronological replay.
                  </p>
                </div>

                <div className="bg-slate-50 dark:bg-zinc-900/60 border border-slate-200 dark:border-zinc-800/80 p-3.5 rounded-xl space-y-1">
                  <span className="font-semibold text-xs text-slate-800 dark:text-zinc-200 flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400" />
                    SAHYOG / I4C
                  </span>
                  <p className="text-[11px] text-slate-600 dark:text-zinc-400">
                    Generates statutory Section 91 notices and court-ready PDF forensic dossiers.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* SAHYOG Lawful Notice Modal */}
      <SahyogModal
        isOpen={isSahyogOpen}
        onClose={() => setIsSahyogOpen(false)}
        data={data}
        onShowToast={(msg) => setToast({ type: 'success', message: msg })}
      />

      {/* Toast Notifications */}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
