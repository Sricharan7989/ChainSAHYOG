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
import SourceBadge from '../components/SourceBadge';
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
  const [dustThreshold, setDustThreshold] = useState(0.01);
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
  const [selectedPosition, setSelectedPosition] = useState(null);
  const [isSahyogOpen, setIsSahyogOpen] = useState(false);

  const handleSelectNode = useCallback((node, pos) => {
    setSelectedNode(node);
    setSelectedEdge(null);
    if (pos) setSelectedPosition(pos);
    else if (!node) setSelectedPosition(null);
  }, []);

  const handleSelectEdge = useCallback((edge, pos) => {
    setSelectedEdge(edge);
    setSelectedNode(null);
    if (pos) setSelectedPosition(pos);
    else if (!edge) setSelectedPosition(null);
  }, []);

  const handlePositionChange = useCallback((pos) => {
    setSelectedPosition(pos);
  }, []);

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
      dustThreshold: data.params?.dust_threshold_eth ?? dustThreshold,
      // Describe the result on screen, not whatever the mode toggle says now: a
      // replayed result is reported from the same recording, and a live result
      // is served from the backend's in-memory copy of that exact trace.
      mode: data.source === 'cache' ? 'cache' : 'live',
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
    <div ref={workspaceRef} className="min-h-screen flex flex-col bg-[#f4f4f5] dark:bg-[#0a0a0a] text-[#09090b] dark:text-[#f5f5f5] selection:bg-[#627EEA]/30 selection:text-white transition-colors duration-200">
      {/* Top Navbar & System Status */}
      <Navbar
        health={health}
        selectedChainId={selectedChainId}
        onSelectChain={setSelectedChainId}
        chains={health?.chains?.supported || []}
        variant="dashboard"
      />

      {/* Main Forensic Investigation Canvas (100% Screen Width) */}
      <main className="flex-1 w-full max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 pt-1 sm:pt-2 pb-6 flex flex-col gap-6">
        {/* Search Controls & Demo Picker Header (Centered & Compact) */}
        <section className="w-full max-w-5xl mx-auto flex flex-col gap-2.5">
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
            <div className="bg-[#ffffff] dark:bg-[#111111] border border-red-500/50 border-l-4 border-l-red-500 p-8 text-center space-y-3 max-w-xl mx-auto my-auto shadow-[4px_4px_0px_#18181b] dark:shadow-[4px_4px_0px_#000000]">
              <div className="w-12 h-12 bg-red-500/20 text-red-500 dark:text-red-400 border border-red-500/30 flex items-center justify-center mx-auto">
                <Shield className="w-6 h-6" />
              </div>
              <h3 className="font-bold text-lg text-red-600 dark:text-red-200">Investigation Trace Halted</h3>
              <p className="text-xs sm:text-sm text-[#09090b] dark:text-[#f5f5f5] font-mono bg-[#f4f4f5] dark:bg-[#0a0a0a] p-3 border border-red-500/20 break-all">
                {error}
              </p>
              <p className="text-xs text-[#71717a] dark:text-[#a3a3a3]">
                Please verify the wallet address, check your Etherscan key, or test using one of the pre-recorded demo traces.
              </p>
            </div>
          )}

          {/* STATE 3: RESULTS LOADED (Graph + Findings Dashboard - Exact 50-50 Split) */}
          {!loading && !error && data && (
            <>
              {/* Provenance of the result above everything else, so nobody has to
                  guess whether these figures came off the chain just now. */}
              <SourceBadge data={data} />
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 flex-1 min-h-[660px]">
              {/* Left Column: Cytoscape Money-Flow Visualizer (50%) */}
              <div className="flex flex-col relative h-[660px] lg:h-auto min-h-[640px]">
                <TraceGraph
                  data={data}
                  onSelectNode={handleSelectNode}
                  onSelectEdge={handleSelectEdge}
                  onPositionChange={handlePositionChange}
                  selectedNodeId={selectedNode?.id}
                  selectedEdgeId={selectedEdge?.id}
                />

                {/* Minimal Contextual Node & Edge Forensics Popover */}
                <NodeDrawer
                  selectedNode={selectedNode}
                  selectedEdge={selectedEdge}
                  position={selectedPosition}
                  onClose={() => {
                    setSelectedNode(null);
                    setSelectedEdge(null);
                    setSelectedPosition(null);
                  }}
                  explorerBase={data.params?.explorer}
                />
              </div>

              {/* Right Column: Forensic Findings Panel (50%) */}
              <div className="flex flex-col h-[660px] lg:h-auto">
                <FindingPanel
                  data={data}
                  onOpenSahyog={() => setIsSahyogOpen(true)}
                  onDownloadReport={handleDownloadReport}
                  onSelectAddress={handleSelectAddress}
                />
              </div>
              </div>
            </>
          )}

          {/* STATE 4: IDLE / WELCOME STATE */}
          {!loading && !error && !data && (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8 sm:p-12 border border-[#d4d4d8] dark:border-[#262626] bg-[#ffffff] dark:bg-[#111111] space-y-6 my-auto shadow-[4px_4px_0px_#18181b] dark:shadow-[4px_4px_0px_#000000]">
              <div className="w-16 h-16 border-2 border-[#627EEA] bg-[#f4f4f5] dark:bg-[#0a0a0a] flex items-center justify-center text-[#627EEA]">
                <Shield className="w-8 h-8" />
              </div>

              <div className="max-w-md space-y-2">
                <h2 className="text-xl font-bold text-[#09090b] dark:text-[#f5f5f5]">
                  Ready for Blockchain Attribution
                </h2>
                <p className="text-xs sm:text-sm text-[#71717a] dark:text-[#a3a3a3] leading-relaxed">
                  Enter an unhosted suspect wallet address or pick a pre-recorded demo above to trace funds forward to regulated exchange chokepoints.
                </p>
              </div>

              {/* Capability highlights */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-2xl text-left pt-4">
                <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] hover:border-[#627EEA] hover:shadow-[3px_3px_0px_#627EEA] p-3.5 space-y-1 transition-all">
                  <span className="font-semibold text-xs text-[#09090b] dark:text-[#f5f5f5] flex items-center gap-1.5 font-mono">
                    <Database className="w-3.5 h-3.5 text-[#627EEA]" />
                    Multi-Chain EVM
                  </span>
                  <p className="text-[11px] text-[#71717a] dark:text-[#888888]">
                    Follow funds across Ethereum, Polygon, BNB Chain, and Arbitrum One.
                  </p>
                </div>

                <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] hover:border-[#627EEA] hover:shadow-[3px_3px_0px_#627EEA] p-3.5 space-y-1 transition-all">
                  <span className="font-semibold text-xs text-[#09090b] dark:text-[#f5f5f5] flex items-center gap-1.5 font-mono">
                    <Activity className="w-3.5 h-3.5 text-emerald-500 dark:text-emerald-400" />
                    FIFO Taint Math
                  </span>
                  <p className="text-[11px] text-[#71717a] dark:text-[#888888]">
                    Calculates exact stolen balances landing at exchanges via chronological replay.
                  </p>
                </div>

                <div className="bg-[#f4f4f5] dark:bg-[#0a0a0a] border border-[#d4d4d8] dark:border-[#262626] hover:border-[#627EEA] hover:shadow-[3px_3px_0px_#627EEA] p-3.5 space-y-1 transition-all">
                  <span className="font-semibold text-xs text-[#09090b] dark:text-[#f5f5f5] flex items-center gap-1.5 font-mono">
                    <FileText className="w-3.5 h-3.5 text-[#627EEA]" />
                    SAHYOG / I4C
                  </span>
                  <p className="text-[11px] text-[#71717a] dark:text-[#888888]">
                    Drafts a lawful request under the applicable provisions of the Bharatiya Nagarik Suraksha Sanhita, 2023 and the Information Technology Act, 2000, with a court-ready dossier.
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
