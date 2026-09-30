import { useRef, useEffect } from 'react';
import { CheckCircle, AlertTriangle, X } from 'lucide-react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';

gsap.registerPlugin(useGSAP);

export default function Toast({ toast, onClose }) {
  const toastRef = useRef(null);

  useGSAP(() => {
    if (toast) {
      gsap.fromTo(
        toastRef.current,
        { y: 50, opacity: 0, scale: 0.95 },
        { y: 0, opacity: 1, scale: 1, duration: 0.35, ease: 'back.out(1.5)' }
      );
    }
  }, { dependencies: [toast] });

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => {
      onClose();
    }, 4000);
    return () => clearTimeout(timer);
  }, [toast, onClose]);

  if (!toast) return null;

  const isError = toast.type === 'error';

  return (
    <div className="fixed bottom-6 right-6 z-50 pointer-events-none">
      <div
        ref={toastRef}
        className={`pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-xl shadow-xl dark:shadow-2xl border text-xs sm:text-sm font-medium backdrop-blur-md max-w-md ${
          isError
            ? 'bg-red-50 dark:bg-red-950/90 text-red-900 dark:text-red-200 border-red-200 dark:border-red-500/40'
            : 'bg-white/95 dark:bg-zinc-900/95 text-slate-800 dark:text-zinc-100 border-slate-200 dark:border-zinc-700/80'
        }`}
      >
        {isError ? (
          <AlertTriangle className="w-4 h-4 text-red-500 dark:text-red-400 shrink-0" />
        ) : (
          <CheckCircle className="w-4 h-4 text-emerald-500 dark:text-emerald-400 shrink-0" />
        )}
        <span className="flex-1">{toast.message || toast}</span>
        <button
          type="button"
          onClick={onClose}
          className="text-slate-400 dark:text-zinc-400 hover:text-slate-700 dark:hover:text-zinc-200 transition-colors p-1 cursor-pointer"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
