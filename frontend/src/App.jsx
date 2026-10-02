import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Shield } from 'lucide-react';
import { ThemeProvider } from './context/ThemeContext';

import BrutalistCursor from './components/BrutalistCursor';

const LandingPage = lazy(() => import('./pages/LandingPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));

function RouteLoader() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] flex flex-col items-center justify-center space-y-4">
      <div className="w-12 h-12 bg-[#111111] border-2 border-[#627EEA] flex items-center justify-center text-[#627EEA] animate-pulse">
        <Shield className="w-6 h-6" />
      </div>
      <p className="text-xs font-mono text-[#a3a3a3] uppercase tracking-widest">Loading ChainSAHYOG Intelligence...</p>
    </div>
  );
}

/**
 * Main Application Router
 * - Route /           : Clear visual Landing Page explaining the problem & chokepoint breakthrough
 * - Route /dashboard  : Investigative Forensic Workspace (Graph visualization, finding panel, drawer, report generation)
 */
export default function App() {
  return (
    <ThemeProvider>
      <BrutalistCursor />
      <BrowserRouter>
        <Suspense fallback={<RouteLoader />}>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ThemeProvider>
  );
}
