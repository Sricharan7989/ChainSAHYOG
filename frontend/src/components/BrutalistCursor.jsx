import { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';

/**
 * BrutalistCursor
 * High-performance tactical neo-brutalist cursor powered by GSAP quickTo.
 * Features a precision crosshair frame and center target dot.
 * Automatically expands and highlights in Ethereum purple (#627EEA) over interactive elements.
 */
export default function BrutalistCursor() {
  const cursorRef = useRef(null);
  const dotRef = useRef(null);
  const [isHovering, setIsHovering] = useState(false);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Disable on touch devices
    if (window.matchMedia('(pointer: coarse)').matches) {
      return;
    }

    const cursor = cursorRef.current;
    const dot = dotRef.current;
    if (!cursor || !dot) return;

    // Use GSAP quickTo for 60fps GPU-accelerated cursor following
    const xTo = gsap.quickTo(cursor, 'x', { duration: 0.18, ease: 'power2.out' });
    const yTo = gsap.quickTo(cursor, 'y', { duration: 0.18, ease: 'power2.out' });
    const xDotTo = gsap.quickTo(dot, 'x', { duration: 0.05, ease: 'power1.out' });
    const yDotTo = gsap.quickTo(dot, 'y', { duration: 0.05, ease: 'power1.out' });

    const handleMouseMove = (e) => {
      if (!isVisible) setIsVisible(true);
      xTo(e.clientX);
      yTo(e.clientY);
      xDotTo(e.clientX);
      yDotTo(e.clientY);
    };

    const handleMouseLeave = () => {
      setIsVisible(false);
    };

    const handleMouseEnter = () => {
      setIsVisible(true);
    };

    const handleOver = (e) => {
      const target = e.target;
      if (
        target.closest('button') ||
        target.closest('a') ||
        target.closest('input') ||
        target.closest('select') ||
        target.closest('[role="button"]') ||
        target.closest('.cursor-pointer') ||
        target.closest('.brutal-press')
      ) {
        setIsHovering(true);
      } else {
        setIsHovering(false);
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseover', handleOver);
    document.addEventListener('mouseleave', handleMouseLeave);
    document.addEventListener('mouseenter', handleMouseEnter);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseover', handleOver);
      document.removeEventListener('mouseleave', handleMouseLeave);
      document.removeEventListener('mouseenter', handleMouseEnter);
    };
  }, [isVisible]);

  return (
    <div
      className={`pointer-events-none fixed inset-0 z-50 transition-opacity duration-200 select-none ${
        isVisible ? 'opacity-100' : 'opacity-0'
      }`}
      aria-hidden="true"
    >
      {/* Outer Tactical Crosshair Frame */}
      <div
        ref={cursorRef}
        className="fixed top-0 left-0 -translate-x-1/2 -translate-y-1/2 will-change-transform"
      >
        <div
          className={`transition-all duration-150 ease-out border flex items-center justify-center ${
            isHovering
              ? 'w-9 h-9 border-2 border-[#627EEA] shadow-[2px_2px_0px_#627EEA] rotate-45 bg-[#627EEA]/15'
              : 'w-6 h-6 border border-[#a1a1aa] dark:border-[#71717a] bg-transparent'
          }`}
        >
          {/* Subtle Corner notches */}
          <span className="absolute -top-1 -left-1 w-1.5 h-1.5 bg-[#627EEA]" />
          <span className="absolute -bottom-1 -right-1 w-1.5 h-1.5 bg-[#627EEA]" />
        </div>
      </div>

      {/* Center Target Dot */}
      <div
        ref={dotRef}
        className="fixed top-0 left-0 -translate-x-1/2 -translate-y-1/2 will-change-transform"
      >
        <div
          className={`w-1.5 h-1.5 transition-colors duration-150 ${
            isHovering ? 'bg-[#627EEA] scale-125' : 'bg-[#09090b] dark:bg-[#f5f5f5]'
          }`}
        />
      </div>
    </div>
  );
}
