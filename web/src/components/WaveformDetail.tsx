import React, { useEffect, useRef } from 'react';
import { clamp, formatTime } from '../audio/format';
import type {
  QualityFinding,
  RegionSelection,
  TrackCue,
  TransitionZone,
  ZoomWindow,
} from '../types';

interface WaveformDetailProps {
  peaks: number[] | null;
  duration: number;
  tracks: TrackCue[];
  transitions: TransitionZone[];
  qualityFindings: QualityFinding[];
  currentTime: number;
  zoom: ZoomWindow;
  onZoomChange: (zoom: ZoomWindow) => void;
  onSeek: (timeSeconds: number) => void;
  selection: RegionSelection;
  onSelectRegion: (selection: RegionSelection) => void;
  isDark: boolean;
}

const CANVAS_W = 1200;
const CANVAS_H = 240;

function regionId(kind: string, id: string | undefined, fallback: number): string {
  return id ?? `${kind}-${fallback}`;
}

/**
 * Zoomable waveform for large (multi-hour) mix sets. Renders backend peaks
 * plus every engine-processed area: track segments, transition blend zones
 * and analysis quality flags. Clicking a highlighted area seeks *and*
 * selects it for the detail inspector; keyboard arrows scrub.
 */
export const WaveformDetail: React.FC<WaveformDetailProps> = ({
  peaks,
  duration,
  tracks,
  transitions,
  qualityFindings,
  currentTime,
  zoom,
  onZoomChange,
  onSeek,
  selection,
  onSelectRegion,
  isDark,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const safeDuration = duration > 0 ? duration : 1;
  const viewStart = clamp(zoom.start, 0, 1);
  const viewEnd = clamp(zoom.end, 0, 1);
  const viewSpan = Math.max(0.001, viewEnd - viewStart);

  const timeToX = (t: number): number =>
    ((clamp(t, 0, safeDuration) / safeDuration - viewStart) / viewSpan) * CANVAS_W;
  const xToTime = (x: number): number =>
    clamp((viewStart + (x / CANVAS_W) * viewSpan) * safeDuration, 0, safeDuration);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const grid = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)';

    // Background
    const bg = ctx.createLinearGradient(0, 0, 0, CANVAS_H);
    if (isDark) {
      bg.addColorStop(0, '#14161d');
      bg.addColorStop(1, '#090a0d');
    } else {
      bg.addColorStop(0, '#eef0f3');
      bg.addColorStop(1, '#d7dae0');
    }
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

    // Time grid (adaptive step for long sets)
    const windowSecs = viewSpan * safeDuration;
    const step = windowSecs > 5400 ? 600 : windowSecs > 1800 ? 300 : windowSecs > 600 ? 60 : 30;
    ctx.strokeStyle = grid;
    ctx.lineWidth = 1;
    ctx.fillStyle = isDark ? '#71717a' : '#6b7280';
    ctx.font = '11px ui-monospace, monospace';
    const firstTick = Math.ceil(((viewStart * safeDuration) / step)) * step;
    for (let t = firstTick; t <= viewEnd * safeDuration; t += step) {
      const x = timeToX(t);
      ctx.beginPath();
      ctx.moveTo(x, 18);
      ctx.lineTo(x, CANVAS_H);
      ctx.stroke();
      ctx.fillText(formatTime(t), x + 4, 12);
    }

    // Track segment bands (alternate shading across the full height)
    tracks.forEach((tr, idx) => {
      const x0 = timeToX(tr.start_time);
      const next = tracks[idx + 1];
      const x1 = timeToX(next ? next.start_time : safeDuration);
      if (x1 < 0 || x0 > CANVAS_W) return;
      if (idx % 2 === 1) {
        ctx.fillStyle = isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)';
        ctx.fillRect(Math.max(0, x0), 18, Math.min(CANVAS_W, x1) - Math.max(0, x0), CANVAS_H - 18);
      }
      // Cue line
      const selected = selection?.kind === 'track' && selection.id === regionId('track', tr.id, idx);
      ctx.strokeStyle = selected ? '#ffffff' : '#dc2626';
      ctx.lineWidth = selected ? 3 : 2;
      ctx.beginPath();
      ctx.moveTo(x0, 18);
      ctx.lineTo(x0, CANVAS_H);
      ctx.stroke();
      if (x0 > -60 && x0 < CANVAS_W - 40) {
        ctx.fillStyle = isDark ? '#fca5a5' : '#991b1b';
        ctx.font = 'bold 11px ui-monospace, monospace';
        ctx.fillText(`T${idx + 1}`, x0 + 4, 30);
      }
    });

    // Quality flags from the analysis engine (timestamp_range overlays)
    qualityFindings.forEach((q, idx) => {
      const range = q.timestamp_range;
      if (!range || range.length < 2) return;
      const x0 = timeToX(range[0]);
      const x1 = timeToX(range[1]);
      if (x1 < 0 || x0 > CANVAS_W) return;
      const selected = selection?.kind === 'quality' && selection.id === `q-${idx}`;
      ctx.fillStyle = selected ? 'rgba(168,85,247,0.45)' : 'rgba(168,85,247,0.25)';
      ctx.fillRect(Math.max(0, x0), 18, Math.min(CANVAS_W, x1) - Math.max(0, x0), CANVAS_H - 18);
      ctx.strokeStyle = '#a855f7';
      ctx.lineWidth = selected ? 2.5 : 1;
      ctx.strokeRect(Math.max(0, x0), 18, Math.min(CANVAS_W, x1) - Math.max(0, x0), CANVAS_H - 18);
    });

    // Transition blend zones (engine-detected harmonic processing areas)
    transitions.forEach((tr, idx) => {
      const x0 = timeToX(tr.start_time);
      const x1 = timeToX(tr.end_time ?? tr.start_time + 30);
      if (x1 < 0 || x0 > CANVAS_W) return;
      const selected =
        selection?.kind === 'transition' && selection.id === regionId('transition', tr.id, idx);
      ctx.fillStyle = selected
        ? 'rgba(217,119,6,0.55)'
        : isDark
          ? 'rgba(217,119,6,0.32)'
          : 'rgba(245,158,11,0.4)';
      ctx.fillRect(Math.max(0, x0), 18, Math.min(CANVAS_W, x1) - Math.max(0, x0), CANVAS_H - 18);
      ctx.strokeStyle = selected ? '#ffffff' : '#d97706';
      ctx.lineWidth = selected ? 2.5 : 1.5;
      ctx.strokeRect(Math.max(0, x0), 18, Math.min(CANVAS_W, x1) - Math.max(0, x0), CANVAS_H - 18);
    });

    // Peaks (windowed slice of the backend buckets)
    const bars = 240;
    const barW = CANVAS_W / bars;
    ctx.fillStyle = isDark ? '#ea580c' : '#c2410c';
    for (let i = 0; i < bars; i++) {
      const frac = viewStart + (i / bars) * viewSpan;
      let v: number | null = null;
      if (peaks && peaks.length > 0) {
        const pi = clamp(Math.floor(frac * peaks.length), 0, peaks.length - 1);
        v = peaks[pi];
      }
      const h = v === null ? 2 : Math.max(2, clamp(v, 0, 1) * (CANVAS_H - 60));
      const y = (CANVAS_H + 18 - h) / 2 + 9;
      ctx.fillRect(i * barW, y, Math.max(1, barW - 1), h);
    }

    if (!peaks || peaks.length === 0) {
      ctx.fillStyle = isDark ? '#71717a' : '#6b7280';
      ctx.font = '12px ui-monospace, monospace';
      ctx.fillText('peaks unavailable — run analysis to render the waveform', 12, CANVAS_H - 10);
    }

    // Playhead
    const px = timeToX(currentTime);
    ctx.strokeStyle = isDark ? '#ffffff' : '#111827';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(px, 18);
    ctx.lineTo(px, CANVAS_H);
    ctx.stroke();
    ctx.fillStyle = isDark ? '#ffffff' : '#111827';
    ctx.beginPath();
    ctx.moveTo(px - 6, 18);
    ctx.lineTo(px + 6, 18);
    ctx.lineTo(px, 26);
    ctx.closePath();
    ctx.fill();
  }, [peaks, tracks, transitions, qualityFindings, currentTime, zoom, selection, isDark, safeDuration, viewStart, viewEnd, viewSpan]);

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * CANVAS_W;
    const t = xToTime(x);

    // Prefer the most specific engine area under the cursor.
    const trIdx = transitions.findIndex((tr) => {
      const end = tr.end_time ?? tr.start_time + 30;
      return t >= tr.start_time && t <= end;
    });
    if (trIdx >= 0) {
      onSelectRegion({ kind: 'transition', id: regionId('transition', transitions[trIdx].id, trIdx) });
      onSeek(t);
      return;
    }
    const qIdx = qualityFindings.findIndex((q) => {
      const r = q.timestamp_range;
      return r && r.length >= 2 && t >= r[0] && t <= r[1];
    });
    if (qIdx >= 0) {
      onSelectRegion({ kind: 'quality', id: `q-${qIdx}` });
      onSeek(t);
      return;
    }
    const trackIdxs = tracks
      .map((tr, idx) => ({ tr, idx }))
      .filter(({ tr, idx }) => {
        const end = tracks[idx + 1]?.start_time ?? safeDuration;
        return t >= tr.start_time && t < end;
      });
    if (trackIdxs.length > 0) {
      const { tr, idx } = trackIdxs[0];
      onSelectRegion({ kind: 'track', id: regionId('track', tr.id, idx) });
    }
    onSeek(t);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    const step = e.shiftKey ? 30 : 5;
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      onSeek(clamp(currentTime - step, 0, safeDuration));
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      onSeek(clamp(currentTime + step, 0, safeDuration));
    } else if (e.key === 'Home') {
      e.preventDefault();
      onSeek(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      onSeek(safeDuration);
    }
  };

  const zoomIn = () => {
    const center = clamp(currentTime / safeDuration, 0, 1);
    const half = Math.max(0.01, viewSpan / 4);
    onZoomChange({ start: clamp(center - half, 0, 1), end: clamp(center + half, 0, 1) });
  };
  const zoomOut = () => {
    const center = (viewStart + viewEnd) / 2;
    const half = Math.min(0.5, viewSpan);
    onZoomChange({ start: clamp(center - half, 0, 1), end: clamp(center + half, 0, 1) });
  };
  const zoomReset = () => onZoomChange({ start: 0, end: 1 });

  const windowLabel = `${formatTime(viewStart * safeDuration)} – ${formatTime(viewEnd * safeDuration)}`;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <div
          className={`flex items-center rounded-lg border text-xs font-mono ${
            isDark ? 'border-[#292c38]' : 'border-[#d1d5db]'
          }`}
          role="group"
          aria-label="Waveform zoom"
        >
          <button
            onClick={zoomIn}
            data-testid="waveform-zoom-in"
            aria-label="Zoom waveform in"
            className="px-3 py-1.5 min-w-[44px] min-h-[44px] font-bold"
          >
            +
          </button>
          <button
            onClick={zoomOut}
            data-testid="waveform-zoom-out"
            aria-label="Zoom waveform out"
            className="px-3 py-1.5 min-w-[44px] min-h-[44px] font-bold border-x border-inherit"
          >
            −
          </button>
          <button
            onClick={zoomReset}
            data-testid="waveform-zoom-reset"
            aria-label="Reset waveform zoom"
            className="px-3 py-1.5 min-w-[44px] min-h-[44px]"
          >
            Reset
          </button>
        </div>
        <span className={`text-xs font-mono ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`} aria-live="polite">
          Window: {windowLabel}
        </span>
      </div>

      <div
        role="slider"
        tabIndex={0}
        aria-label="Mix waveform position. Arrow keys scrub, Home and End jump."
        aria-valuemin={0}
        aria-valuemax={Math.round(safeDuration)}
        aria-valuenow={Math.round(currentTime)}
        aria-valuetext={`${formatTime(currentTime)} of ${formatTime(safeDuration)}`}
        onKeyDown={handleKeyDown}
        className="relative border rounded overflow-hidden cursor-crosshair border-[#374151]/40 focus:outline-none focus:ring-2 focus:ring-[#ea580c] scroll-mt-[300px]"
      >
        <canvas
          ref={canvasRef}
          width={CANVAS_W}
          height={CANVAS_H}
          onClick={handleClick}
          data-testid="waveform-canvas"
          className="w-full h-[240px] block"
        />
      </div>

      <div className={`mt-2 flex flex-wrap gap-4 text-xs ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 bg-[#dc2626] rounded-sm inline-block" aria-hidden="true" /> Track cues ({tracks.length})
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 bg-[#d97706] rounded-sm inline-block" aria-hidden="true" /> Engine transition zones ({transitions.length})
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 bg-[#a855f7] rounded-sm inline-block" aria-hidden="true" /> Quality flags ({qualityFindings.filter((q) => q.timestamp_range && q.timestamp_range.length >= 2).length})
        </span>
      </div>
    </div>
  );
};
