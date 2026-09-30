import { useState, useEffect } from 'react';
import BackgroundCanvas from '../components/landing/BackgroundCanvas';
import HeroSection from '../components/landing/HeroSection';
import InteractiveHeistVisualizer from '../components/landing/InteractiveHeistVisualizer';
import ProblemSolutionSection from '../components/landing/ProblemSolutionSection';
import TypologiesShowcase from '../components/landing/TypologiesShowcase';
import EngineCapabilitiesSection from '../components/landing/EngineCapabilitiesSection';
import WorkflowSection from '../components/landing/WorkflowSection';
import LandingFooter from '../components/landing/LandingFooter';
import Navbar from '../components/Navbar';
import { fetchHealth, fetchDemos } from '../api/client';

export default function LandingPage() {
  const [health, setHealth] = useState(null);
  const [demos, setDemos] = useState([]);

  useEffect(() => {
    async function loadData() {
      try {
        const healthData = await fetchHealth();
        setHealth(healthData);
      } catch (err) {
        console.warn('Backend /health unreachable on landing page:', err);
      }

      try {
        const demosData = await fetchDemos();
        setDemos(demosData.demos || []);
      } catch (err) {
        console.warn('Backend /demos unreachable on landing page:', err);
      }
    }
    loadData();
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-100 flex flex-col relative selection:bg-cyan-500/30 selection:text-cyan-200 transition-colors duration-200">
      {/* Background Interactive Canvas */}
      <BackgroundCanvas />

      {/* Main Top Navigation */}
      <Navbar health={health} variant="landing" />

      {/* Landing Content Container */}
      <main className="flex-1 relative z-10">
        <HeroSection demos={demos} />
        <InteractiveHeistVisualizer />
        <ProblemSolutionSection />
        <TypologiesShowcase />
        <EngineCapabilitiesSection />
        <WorkflowSection />
      </main>

      {/* Landing Page Footer */}
      <LandingFooter />
    </div>
  );
}
