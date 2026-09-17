/** Shared time/number formatting for long DJ sets (multi-hour safe). */
export function formatTime(secs: number): string {
  if (!Number.isFinite(secs) || secs < 0) secs = 0;
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = Math.floor(secs % 60);
  if (h > 0) {
    return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

export function formatBpm(bpm: number | undefined | null): string {
  return bpm === undefined || bpm === null || !Number.isFinite(bpm)
    ? '—'
    : `${bpm.toFixed(1)} BPM`;
}

export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
