import React, { useRef, useEffect, useState, useMemo } from 'react';

export type StackArchitecture = 'wall_of_sound' | 'mechanical_totem' | 'underground_rig';
export type VisualizerTheme = 'rust' | 'crimson' | 'amber' | 'copper' | 'ochre';

export interface VisualizerSettings {
  architecture: StackArchitecture;
  theme: VisualizerTheme;
  excursionScale: number;
  strobeSensitivity: number;
  orbitSpeed: number;
  wireframe: boolean;
  atmosphericHaze: boolean;
}

interface SpeakerStackVisualizerProps {
  analyserNode?: AnalyserNode | null;
  settings: VisualizerSettings;
  isPlaying?: boolean;
}

interface SpeakerBox {
  type: 'sub_scoop' | 'kick_bin' | 'mid_horn' | 'top_flare';
  x: number; // grid units
  y: number;
  z: number;
  w: number;
  h: number;
  d: number;
  coneRadius: number;
  coneCount: number;
}

const THEME_PALETTES: Record<
  VisualizerTheme,
  { primary: string; accent: string; wood: string; grill: string; glow: string; horn: string }
> = {
  rust: {
    primary: '#c84b14',
    accent: '#ea580c',
    wood: '#1c1917',
    grill: '#292524',
    glow: 'rgba(200, 75, 20, 0.45)',
    horn: '#78350f',
  },
  crimson: {
    primary: '#8c1d1d',
    accent: '#dc2626',
    wood: '#18181b',
    grill: '#27272a',
    glow: 'rgba(140, 29, 29, 0.5)',
    horn: '#450a0a',
  },
  amber: {
    primary: '#d97706',
    accent: '#f59e0b',
    wood: '#262626',
    grill: '#404040',
    glow: 'rgba(217, 119, 6, 0.45)',
    horn: '#78350f',
  },
  copper: {
    primary: '#0d9488',
    accent: '#14b8a6',
    wood: '#111827',
    grill: '#1f2937',
    glow: 'rgba(13, 148, 136, 0.45)',
    horn: '#134e4a',
  },
  ochre: {
    primary: '#b45309',
    accent: '#d97706',
    wood: '#1c1917',
    grill: '#292524',
    glow: 'rgba(180, 83, 9, 0.45)',
    horn: '#713f12',
  },
};

export const SpeakerStackVisualizer: React.FC<SpeakerStackVisualizerProps> = ({
  analyserNode,
  settings,
  isPlaying = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [rotation, setRotation] = useState<{ yaw: number; pitch: number }>({ yaw: 0, pitch: 0.15 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [hudTelemetry, setHudTelemetry] = useState({ subDb: -60, midDb: -60, highDb: -60, excursionMm: 0 });

  // Generate Stack geometry based on selected architecture
  const boxes = useMemo<SpeakerBox[]>(() => {
    const list: SpeakerBox[] = [];

    if (settings.architecture === 'wall_of_sound') {
      // 4 Scoop Subs at bottom
      for (let i = -2; i < 2; i++) {
        list.push({
          type: 'sub_scoop',
          x: i * 1.6 + 0.8,
          y: -1.4,
          z: 0,
          w: 1.5,
          h: 1.3,
          d: 1.4,
          coneRadius: 0.52,
          coneCount: 2,
        });
      }
      // 4 Kick Bins in middle
      for (let i = -2; i < 2; i++) {
        list.push({
          type: 'kick_bin',
          x: i * 1.6 + 0.8,
          y: 0.0,
          z: 0.1,
          w: 1.5,
          h: 1.1,
          d: 1.2,
          coneRadius: 0.42,
          coneCount: 2,
        });
      }
      // 4 Top Mid/High Horn sections
      for (let i = -2; i < 2; i++) {
        list.push({
          type: 'mid_horn',
          x: i * 1.6 + 0.8,
          y: 1.2,
          z: 0.2,
          w: 1.5,
          h: 0.9,
          d: 1.0,
          coneRadius: 0.32,
          coneCount: 1,
        });
        list.push({
          type: 'top_flare',
          x: i * 1.6 + 0.8,
          y: 2.0,
          z: 0.25,
          w: 1.5,
          h: 0.6,
          d: 0.9,
          coneRadius: 0.22,
          coneCount: 2,
        });
      }
    } else if (settings.architecture === 'mechanical_totem') {
      // Vertical massive totem tower with side wings
      // Center Tower
      list.push({ type: 'sub_scoop', x: 0, y: -1.8, z: 0, w: 2.4, h: 1.5, d: 1.6, coneRadius: 0.65, coneCount: 2 });
      list.push({ type: 'sub_scoop', x: 0, y: -0.3, z: 0.1, w: 2.2, h: 1.4, d: 1.5, coneRadius: 0.58, coneCount: 2 });
      list.push({ type: 'kick_bin', x: 0, y: 1.1, z: 0.2, w: 2.0, h: 1.2, d: 1.3, coneRadius: 0.46, coneCount: 2 });
      list.push({ type: 'mid_horn', x: 0, y: 2.3, z: 0.3, w: 1.8, h: 0.9, d: 1.1, coneRadius: 0.36, coneCount: 2 });
      list.push({ type: 'top_flare', x: 0, y: 3.1, z: 0.35, w: 1.6, h: 0.6, d: 0.9, coneRadius: 0.25, coneCount: 4 });

      // Left & Right Flanks
      [-2.2, 2.2].forEach((offset) => {
        list.push({ type: 'sub_scoop', x: offset, y: -1.4, z: 0.4, w: 1.6, h: 1.3, d: 1.3, coneRadius: 0.5, coneCount: 1 });
        list.push({ type: 'kick_bin', x: offset, y: 0.0, z: 0.5, w: 1.5, h: 1.1, d: 1.1, coneRadius: 0.4, coneCount: 2 });
        list.push({ type: 'mid_horn', x: offset, y: 1.1, z: 0.6, w: 1.4, h: 0.8, d: 0.9, coneRadius: 0.3, coneCount: 1 });
      });
    } else {
      // Underground Rig: Dual Heavy Stacks
      [-2.0, 2.0].forEach((offset) => {
        list.push({ type: 'sub_scoop', x: offset, y: -1.3, z: 0, w: 1.8, h: 1.4, d: 1.4, coneRadius: 0.55, coneCount: 2 });
        list.push({ type: 'kick_bin', x: offset, y: 0.1, z: 0.1, w: 1.7, h: 1.2, d: 1.2, coneRadius: 0.45, coneCount: 2 });
        list.push({ type: 'mid_horn', x: offset, y: 1.3, z: 0.2, w: 1.6, h: 1.0, d: 1.0, coneRadius: 0.35, coneCount: 1 });
        list.push({ type: 'top_flare', x: offset, y: 2.2, z: 0.25, w: 1.5, h: 0.7, d: 0.9, coneRadius: 0.22, coneCount: 2 });
      });
      // Center Sub Cluster
      list.push({ type: 'sub_scoop', x: 0, y: -1.4, z: -0.2, w: 1.6, h: 1.2, d: 1.4, coneRadius: 0.52, coneCount: 2 });
    }

    return list;
  }, [settings.architecture]);

  // Main Render Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    const freqData = new Uint8Array(analyserNode ? analyserNode.frequencyBinCount : 128);

    const render = () => {
      // Resize handling
      const width = (canvas.width = canvas.parentElement?.clientWidth || 800);
      const height = (canvas.height = canvas.parentElement?.clientHeight || 500);

      // Audio Analysis Extraction
      let subEnergy = 0;
      let midEnergy = 0;
      let highEnergy = 0;

      if (analyserNode && isPlaying) {
        analyserNode.getByteFrequencyData(freqData);
        // Sub-bass: bins 1 to 6 (roughly 20 - 120 Hz)
        let subSum = 0;
        for (let i = 1; i <= 6; i++) subSum += freqData[i] || 0;
        subEnergy = subSum / (6 * 255);

        // Mid punch: bins 7 to 30
        let midSum = 0;
        for (let i = 7; i <= 30; i++) midSum += freqData[i] || 0;
        midEnergy = midSum / (24 * 255);

        // High shimmer: bins 31 to 80
        let highSum = 0;
        for (let i = 31; i <= 80; i++) highSum += freqData[i] || 0;
        highEnergy = highSum / (50 * 255);
      } else if (isPlaying) {
        // Subtle idle pulse
        const t = Date.now() / 300;
        subEnergy = 0.2 + Math.sin(t) * 0.15;
        midEnergy = 0.15 + Math.cos(t * 1.5) * 0.1;
        highEnergy = 0.1 + Math.sin(t * 2) * 0.08;
      }

      const excursion = subEnergy * settings.excursionScale * 14.0; // mm
      setHudTelemetry({
        subDb: Math.round(subEnergy * 60 - 60),
        midDb: Math.round(midEnergy * 60 - 60),
        highDb: Math.round(highEnergy * 60 - 60),
        excursionMm: parseFloat(excursion.toFixed(1)),
      });

      // Clear Canvas & draw industrial background gradient
      ctx.fillStyle = '#0a0a0a';
      ctx.fillRect(0, 0, width, height);

      // Radial stage glow reacting to sub hits
      const palette = THEME_PALETTES[settings.theme];
      const stageGlow = ctx.createRadialGradient(
        width / 2,
        height * 0.65,
        10,
        width / 2,
        height * 0.65,
        width * 0.6
      );
      stageGlow.addColorStop(0, palette.glow);
      stageGlow.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = stageGlow;
      ctx.fillRect(0, 0, width, height);

      // Grid Floor Projection
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
      ctx.lineWidth = 1;
      const floorY = height * 0.82;
      for (let i = -10; i <= 10; i++) {
        ctx.beginPath();
        ctx.moveTo(width / 2 + i * 80, floorY);
        ctx.lineTo(width / 2 + i * 280, height);
        ctx.stroke();
      }

      // Auto-orbit camera
      let curYaw = rotation.yaw;
      if (settings.orbitSpeed > 0 && !isDragging) {
        curYaw += settings.orbitSpeed * 0.008;
      }

      // 3D Projection Engine
      const scale = Math.min(width, height) / 5.5;
      const originX = width / 2;
      const originY = height * 0.6;
      const cosYaw = Math.cos(curYaw);
      const sinYaw = Math.sin(curYaw);
      const cosPitch = Math.cos(rotation.pitch);
      const sinPitch = Math.sin(rotation.pitch);

      const project3D = (x: number, y: number, z: number) => {
        // Rotate around Y (yaw)
        const rx = x * cosYaw - z * sinYaw;
        const rz = x * sinYaw + z * cosYaw + 6.0; // camera distance
        // Rotate around X (pitch)
        const ry = y * cosPitch - (rz - 6.0) * sinPitch;
        const fov = 4.5 / Math.max(0.1, rz);
        return {
          px: originX + rx * scale * fov,
          py: originY - ry * scale * fov,
          depth: rz,
          fovScale: fov,
        };
      };

      // Sort boxes back to front (Painter's algorithm)
      const sortedBoxes = [...boxes].map((b) => {
        const center = project3D(b.x, b.y, b.z);
        return { ...b, depth: center.depth };
      });
      sortedBoxes.sort((a, b) => b.depth - a.depth);

      // Render Speaker Cabinets
      sortedBoxes.forEach((box) => {
        const hw = box.w / 2;
        const hh = box.h / 2;
        const hd = box.d / 2;

        // 8 Corners of the cabinet box
        const corners = [
          project3D(box.x - hw, box.y - hh, box.z - hd),
          project3D(box.x + hw, box.y - hh, box.z - hd),
          project3D(box.x + hw, box.y + hh, box.z - hd),
          project3D(box.x - hw, box.y + hh, box.z - hd),
          project3D(box.x - hw, box.y - hh, box.z + hd),
          project3D(box.x + hw, box.y - hh, box.z + hd),
          project3D(box.x + hw, box.y + hh, box.z + hd),
          project3D(box.x - hw, box.y + hh, box.z + hd),
        ];

        // Front Face (corners 4, 5, 6, 7)
        ctx.beginPath();
        ctx.moveTo(corners[4].px, corners[4].py);
        ctx.lineTo(corners[5].px, corners[5].py);
        ctx.lineTo(corners[6].px, corners[6].py);
        ctx.lineTo(corners[7].px, corners[7].py);
        ctx.closePath();

        if (settings.wireframe) {
          ctx.strokeStyle = palette.accent;
          ctx.lineWidth = 1.5;
          ctx.stroke();
        } else {
          ctx.fillStyle = palette.wood;
          ctx.fill();
          ctx.strokeStyle = palette.primary;
          ctx.lineWidth = 1.2;
          ctx.stroke();
        }

        // Perforated Grille & Corner Bolts
        const centerFront = project3D(box.x, box.y, box.z + hd);
        const boxRadiusPx = box.coneRadius * scale * centerFront.fovScale;

        // Render Dynamic Cones / Horns
        if (box.type === 'sub_scoop' || box.type === 'kick_bin') {
          const coneDisp = box.type === 'sub_scoop' ? excursion * 0.02 : midEnergy * 0.015;
          const coneFront = project3D(box.x, box.y, box.z + hd + coneDisp);

          ctx.beginPath();
          ctx.arc(coneFront.px, coneFront.py, boxRadiusPx, 0, Math.PI * 2);
          ctx.fillStyle = '#111';
          ctx.fill();
          ctx.strokeStyle = palette.primary;
          ctx.lineWidth = 2;
          ctx.stroke();

          // Dust cap vibrating
          ctx.beginPath();
          ctx.arc(coneFront.px, coneFront.py, boxRadiusPx * 0.35, 0, Math.PI * 2);
          ctx.fillStyle = palette.grill;
          ctx.fill();
          ctx.stroke();
        } else if (box.type === 'mid_horn' || box.type === 'top_flare') {
          // Flare Horn with reactive illumination
          const flareFront = project3D(box.x, box.y, box.z + hd);
          const flareW = boxRadiusPx * 1.6;
          const flareH = boxRadiusPx * 0.9;

          ctx.fillStyle = box.type === 'top_flare' ? palette.horn : palette.grill;
          ctx.beginPath();
          ctx.rect(flareFront.px - flareW / 2, flareFront.py - flareH / 2, flareW, flareH);
          ctx.fill();
          ctx.strokeStyle = highEnergy > 0.4 ? palette.accent : palette.primary;
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }
      });

      // Strobe Trigger Flash
      if (subEnergy > settings.strobeSensitivity && isPlaying) {
        ctx.fillStyle = `rgba(255, 255, 255, ${Math.min(0.3, (subEnergy - settings.strobeSensitivity) * 0.8)})`;
        ctx.fillRect(0, 0, width, height);
      }

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [analyserNode, settings, isPlaying, rotation, isDragging, boxes]);

  // Drag Interaction
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const dx = e.clientX - dragStart.x;
    const dy = e.clientY - dragStart.y;
    setRotation((prev) => ({
      yaw: prev.yaw + dx * 0.006,
      pitch: Math.max(-0.4, Math.min(0.6, prev.pitch + dy * 0.006)),
    }));
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  const handleMouseUp = () => setIsDragging(false);

  return (
    <div
      className="relative w-full h-[480px] bg-neutral-950 rounded-lg overflow-hidden border border-neutral-800 shadow-2xl select-none"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <canvas ref={canvasRef} className="w-full h-full block cursor-grab active:cursor-grabbing" />

      {/* HUD Telemetry Overlay */}
      <div className="absolute top-3 left-3 bg-neutral-900/85 backdrop-blur border border-neutral-700 px-3 py-2 rounded text-xs font-mono text-neutral-300 space-y-1">
        <div className="text-orange-500 font-bold uppercase tracking-wider text-[10px]">
          SYCO23 // 3D STACK RIG
        </div>
        <div className="flex items-center space-x-3">
          <span>SUB: {hudTelemetry.subDb} dB</span>
          <span>MID: {hudTelemetry.midDb} dB</span>
          <span>EXCURSION: {hudTelemetry.excursionMm} mm</span>
        </div>
      </div>

      <div className="absolute bottom-3 right-3 text-[10px] font-mono text-neutral-500 bg-black/60 px-2 py-1 rounded">
        Drag to Orbit | 3D WebGL Projection
      </div>
    </div>
  );
};
