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
        className={`pointer-events-auto flex items-center gap-3 px-4 py-3 border text-xs sm:text-sm font-medium font-mono max-w-md ${
          isError
            ? 'bg-[#181111] text-red-200 border-red-500/60 shadow-[4px_4px_0px_#ef4444]'
            : 'bg-[#111111] text-[#f5f5f5] border-[#627EEA] shadow-[4px_4px_0px_#627EEA]'
        }`}
      >
        {isError ? (
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
        ) : (
          <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
        )}
        <span className="flex-1">{toast.message || toast}</span>
        <button
          type="button"
          onClick={onClose}
          className="text-[#888888] hover:text-white transition-colors p-1 cursor-pointer border border-[#262626]"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
