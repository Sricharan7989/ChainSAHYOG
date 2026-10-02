import { useState, useEffect } from 'react';
import BackgroundCanvas from '../components/landing/BackgroundCanvas';
import HeroSection from '../components/landing/HeroSection';
import MarqueeTicker from '../components/landing/MarqueeTicker';
import InteractiveHeistVisualizer from '../components/landing/InteractiveHeistVisualizer';
import ProblemSolutionSection from '../components/landing/ProblemSolutionSection';
import TypologiesShowcase from '../components/landing/TypologiesShowcase';
import EngineCapabilitiesSection from '../components/landing/EngineCapabilitiesSection';
import WorkflowSection from '../components/landing/WorkflowSection';
import LandingFooter from '../components/landing/LandingFooter';
import Navbar from '../components/Navbar';
import { fetchHealth } from '../api/client';

export default function LandingPage() {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    async function loadData() {
      try {
        const healthData = await fetchHealth();
        setHealth(healthData);
      } catch (err) {
        console.warn('Backend /health unreachable on landing page:', err);
      }
    }
    loadData();
  }, []);

  return (
    <div className="min-h-screen bg-[#f4f4f5] dark:bg-[#0a0a0a] text-[#09090b] dark:text-[#f5f5f5] flex flex-col relative selection:bg-[#627EEA]/30 selection:text-inherit transition-colors duration-200">
      {/* Background Interactive Vector & Dot Canvas */}
      <BackgroundCanvas />

      {/* Floating Tactical Top Navigation */}
      <Navbar health={health} variant="landing" />

      {/* Landing Content Container (Translucent so canvas vectors remain visible) */}
      <main className="flex-1 relative z-10">
        <HeroSection />
        <MarqueeTicker />
        <InteractiveHeistVisualizer />
        <ProblemSolutionSection />
        <MarqueeTicker />
        <TypologiesShowcase />
        <EngineCapabilitiesSection />
        <MarqueeTicker />
        <WorkflowSection />
      </main>

      {/* Landing Page Footer */}
      <LandingFooter />
    </div>
  );
}
