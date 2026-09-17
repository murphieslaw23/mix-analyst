import React from 'react';

interface StatusBadgeProps {
  status: string | undefined | null;
  isDark?: boolean;
}

/** Non-destructive status pill for jobs/batches (oil/iron/bone/rust only). */
export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, isDark = true }) => {
  const s = (status || 'unknown').toUpperCase();
  const base = 'px-2 py-0.5 rounded text-[10px] font-mono font-bold border inline-flex items-center min-h-[22px] ';
  let tone: string;
  if (s === 'SUCCEEDED' || s === 'COMPLETED' || s === 'SYNCED' || s === 'RENDERED') {
    tone = 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40';
  } else if (s === 'FAILED' || s === 'PARTIAL_FAILED') {
    tone = 'bg-red-500/15 text-red-400 border-red-500/40';
  } else if (
    s === 'RUNNING' ||
    s === 'PROCESSING' ||
    s === 'QUEUED' ||
    s === 'RENDERING' ||
    s === 'UPLOADING' ||
    s === 'PENDING'
  ) {
    tone = 'bg-amber-500/15 text-amber-400 border-amber-500/40';
  } else {
    tone = isDark
      ? 'bg-neutral-800 text-neutral-300 border-neutral-700'
      : 'bg-neutral-100 text-neutral-600 border-neutral-300';
  }
  return (
    <span className={base + tone} data-testid="status-badge">
      {s}
    </span>
  );
};

export default StatusBadge;
