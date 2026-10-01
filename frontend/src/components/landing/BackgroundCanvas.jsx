import { useEffect, useRef } from 'react';
import { useTheme } from '../../context/ThemeContext';

/**
 * BackgroundCanvas
 * High-density, interactive HTML5 Canvas animation depicting an interconnected
 * forensic blockchain network with magnetic cursor laser threads and traveling packets.
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

    // Dynamic density: 120-160 nodes
    const count = Math.min(Math.floor((width * height) / 9000), 160);
    const nodes = [];

    const isDark = theme === 'dark';
    const palette = isDark
      ? ['#06b6d4', '#3b82f6', '#10b981', '#8b5cf6']
      : ['#0284c7', '#2563eb', '#059669', '#7c3aed'];

    for (let i = 0; i < count; i++) {
      const isHub = Math.random() < 0.15; // 15% are major hubs
      nodes.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.6,
        vy: (Math.random() - 0.5) * 0.6,
        radius: isHub ? Math.random() * 2 + 3.5 : Math.random() * 2 + 1.8,
        color: palette[Math.floor(Math.random() * palette.length)],
        alpha: isHub ? 0.8 : Math.random() * 0.4 + 0.3,
        isHub,
        pulsePhase: Math.random() * Math.PI * 2,
      });
    }

    // Traveling energy packets along network connections
    const packets = [];
    const maxPackets = 24;

    // Mouse coordinates for interactive magnetic beacon
    let mouse = { x: -1000, y: -1000, radius: 180 };

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

      // 1. Draw connecting lines between nodes
      for (let i = 0; i < nodes.length; i++) {
        const p1 = nodes[i];

        p1.x += p1.vx;
        p1.y += p1.vy;
        p1.pulsePhase += 0.03;

        // Bounce screen edges
        if (p1.x < 0 || p1.x > width) p1.vx *= -1;
        if (p1.y < 0 || p1.y > height) p1.vy *= -1;

        // Mouse repulsion & attraction balance
        const dxMouse = p1.x - mouse.x;
        const dyMouse = p1.y - mouse.y;
        const distMouse = Math.hypot(dxMouse, dyMouse);
        if (distMouse < mouse.radius) {
          const force = (1 - distMouse / mouse.radius) * 1.5;
          p1.x += (dxMouse / distMouse) * force;
          p1.y += (dyMouse / distMouse) * force;

          // Interactive laser connection to cursor!
          ctx.beginPath();
          ctx.moveTo(mouse.x, mouse.y);
          ctx.lineTo(p1.x, p1.y);
          ctx.strokeStyle = isDark ? '#06b6d4' : '#0284c7';
          ctx.globalAlpha = (1 - distMouse / mouse.radius) * 0.45;
          ctx.lineWidth = 1.2;
          ctx.stroke();
        }

        // Connect near neighbors
        for (let j = i + 1; j < nodes.length; j++) {
          const p2 = nodes[j];
          const dx = p1.x - p2.x;
          const dy = p1.y - p2.y;
          const dist = Math.hypot(dx, dy);

          if (dist < 120) {
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = isDark ? '#38bdf8' : '#0284c7';
            ctx.globalAlpha = (1 - dist / 120) * (isDark ? 0.22 : 0.16);
            ctx.lineWidth = 0.9;
            ctx.stroke();

            // Spawn occasional energy packet along connection
            if (packets.length < maxPackets && Math.random() < 0.003) {
              packets.push({
                x: p1.x,
                y: p1.y,
                targetX: p2.x,
                targetY: p2.y,
                progress: 0,
                speed: 0.015 + Math.random() * 0.02,
                color: p1.color,
              });
            }
          }
        }

        // Draw node
        ctx.beginPath();
        ctx.arc(p1.x, p1.y, p1.radius, 0, Math.PI * 2);
        ctx.fillStyle = p1.color;
        ctx.globalAlpha = p1.alpha;
        ctx.fill();

        // Hub nodes get a pulsing outer glow ring
        if (p1.isHub) {
          const pulseR = p1.radius + Math.sin(p1.pulsePhase) * 3 + 4;
          ctx.beginPath();
          ctx.arc(p1.x, p1.y, pulseR, 0, Math.PI * 2);
          ctx.strokeStyle = p1.color;
          ctx.globalAlpha = 0.25 + Math.sin(p1.pulsePhase) * 0.15;
          ctx.lineWidth = 1;
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
        ctx.arc(currX, currY, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = pkt.color;
        ctx.globalAlpha = 0.9;
        ctx.fill();
      }

      // 3. Cursor Beacon Halo
      if (mouse.x > 0 && mouse.y > 0) {
        ctx.beginPath();
        ctx.arc(mouse.x, mouse.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = isDark ? '#38bdf8' : '#0284c7';
        ctx.globalAlpha = 0.8;
        ctx.fill();
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
      className="fixed inset-0 pointer-events-none z-0 opacity-50 transition-opacity"
      aria-hidden="true"
    />
  );
}
