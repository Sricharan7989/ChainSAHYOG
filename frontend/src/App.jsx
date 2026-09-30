import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Shield } from 'lucide-react';
import { ThemeProvider } from './context/ThemeContext';

const LandingPage = lazy(() => import('./pages/LandingPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));

function RouteLoader() {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 flex flex-col items-center justify-center space-y-4">
      <div className="w-12 h-12 rounded-xl bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center text-cyan-500 animate-pulse">
        <Shield className="w-6 h-6" />
      </div>
      <p className="text-xs font-mono text-slate-600 dark:text-zinc-400">Loading ChainSAHYOG Intelligence...</p>
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
