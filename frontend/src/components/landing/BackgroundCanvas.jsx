import { useEffect, useRef } from 'react';
import { useTheme } from '../../context/ThemeContext';

/**
 * BackgroundCanvas
 * High-visibility, interactive neo-brutalist network canvas.
 * Interactive dots, vector connections, traveling packets, and magnetic cursor lasers.
 * Theme-aware: adapts contrast and colors between dark and light modes.
 */
export default function BackgroundCanvas() {
  const canvasRef = useRef(null);
  const { theme } = useTheme();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', handleResize);

    const isDark = theme === 'dark';
    const count = Math.min(Math.floor((width * height) / 8500), 160);
    const nodes = [];

    // Distinct theme palette
    const nodeColor = isDark ? '#71717a' : '#52525b';
    const hubColor = '#627EEA';
    const lineColor = isDark ? '#3f3f46' : '#a1a1aa';

    for (let i = 0; i < count; i++) {
      const isHub = Math.random() < 0.16;
      nodes.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.55,
        vy: (Math.random() - 0.5) * 0.55,
        radius: isHub ? Math.random() * 2 + 3.5 : Math.random() * 1.5 + 2,
        color: isHub ? hubColor : nodeColor,
        alpha: isHub ? (isDark ? 0.9 : 0.85) : (isDark ? 0.55 : 0.45),
        isHub,
        pulsePhase: Math.random() * Math.PI * 2,
      });
    }

    const packets = [];
    const maxPackets = 22;
    let mouse = { x: -1000, y: -1000, radius: 200 };

    const handleMouseMove = (e) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    };
    const handleMouseLeave = () => {
      mouse.x = -1000;
      mouse.y = -1000;
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseleave', handleMouseLeave);

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // 1. Draw connecting vector lines
      for (let i = 0; i < nodes.length; i++) {
        const p1 = nodes[i];

        p1.x += p1.vx;
        p1.y += p1.vy;
        p1.pulsePhase += 0.03;

        // Bounce at boundaries
        if (p1.x < 0 || p1.x > width) p1.vx *= -1;
        if (p1.y < 0 || p1.y > height) p1.vy *= -1;

        // Magnetic cursor interaction
        const dxMouse = p1.x - mouse.x;
        const dyMouse = p1.y - mouse.y;
        const distMouse = Math.hypot(dxMouse, dyMouse);
        if (distMouse < mouse.radius) {
          const force = (1 - distMouse / mouse.radius) * 1.6;
          p1.x += (dxMouse / distMouse) * force;
          p1.y += (dyMouse / distMouse) * force;

          // Interactive laser connection to cursor!
          ctx.beginPath();
          ctx.moveTo(mouse.x, mouse.y);
          ctx.lineTo(p1.x, p1.y);
          ctx.strokeStyle = '#627EEA';
          ctx.globalAlpha = (1 - distMouse / mouse.radius) * 0.65;
          ctx.lineWidth = 1.4;
          ctx.stroke();
        }

        // Connect near neighbor nodes
        for (let j = i + 1; j < nodes.length; j++) {
          const p2 = nodes[j];
          const dx = p1.x - p2.x;
          const dy = p1.y - p2.y;
          const dist = Math.hypot(dx, dy);

          if (dist < 125) {
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = p1.isHub || p2.isHub ? '#627EEA' : lineColor;
            ctx.globalAlpha = (1 - dist / 125) * (p1.isHub || p2.isHub ? 0.45 : 0.28);
            ctx.lineWidth = p1.isHub || p2.isHub ? 1.2 : 0.9;
            ctx.stroke();

            // Spawn traveling data packets along connections
            if (packets.length < maxPackets && Math.random() < 0.0035) {
              packets.push({
                x: p1.x,
                y: p1.y,
                targetX: p2.x,
                targetY: p2.y,
                progress: 0,
                speed: 0.0001 + Math.random() * 0.02,
                color: p1.isHub || p2.isHub ? '#627EEA' : (isDark ? '#e4e4e7' : '#27272a'),
              });
            }
          }
        }

        // Draw node dot
        ctx.beginPath();
        ctx.arc(p1.x, p1.y, p1.radius, 0, Math.PI * 2);
        ctx.fillStyle = p1.color;
        ctx.globalAlpha = p1.alpha;
        ctx.fill();

        // Hub outer pulse rings
        if (p1.isHub) {
          const pulseR = p1.radius + Math.sin(p1.pulsePhase) * 3 + 4;
          ctx.beginPath();
          ctx.arc(p1.x, p1.y, pulseR, 0, Math.PI * 2);
          ctx.strokeStyle = '#627EEA';
          ctx.globalAlpha = 0.35 + Math.sin(p1.pulsePhase) * 0.2;
          ctx.lineWidth = 1.2;
          ctx.stroke();
        }
      }

      // 2. Render and step traveling energy packets
      for (let k = packets.length - 1; k >= 0; k--) {
        const pkt = packets[k];
        pkt.progress += pkt.speed;

        if (pkt.progress >= 1) {
          packets.splice(k, 1);
          continue;
        }

        const currX = pkt.x + (pkt.targetX - pkt.x) * pkt.progress;
        const currY = pkt.y + (pkt.targetY - pkt.y) * pkt.progress;

        ctx.beginPath();
        ctx.arc(currX, currY, 2.8, 0, Math.PI * 2);
        ctx.fillStyle = pkt.color;
        ctx.globalAlpha = 0.95;
        ctx.fill();
      }

      // 3. Cursor Beacon Halo
      if (mouse.x > 0 && mouse.y > 0) {
        ctx.beginPath();
        ctx.arc(mouse.x, mouse.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = '#627EEA';
        ctx.globalAlpha = 0.9;
        ctx.fill();

        // Subtle outer pulse
        ctx.beginPath();
        ctx.arc(mouse.x, mouse.y, 14, 0, Math.PI * 2);
        ctx.strokeStyle = '#627EEA';
        ctx.globalAlpha = 0.3;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      ctx.globalAlpha = 1;
      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, [theme]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0 opacity-60 select-none transition-opacity duration-300"
      aria-hidden="true"
    />
  );
}
