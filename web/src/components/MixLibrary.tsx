import React from 'react';
import { formatTime } from '../audio/format';
import type { MixListItem } from '../types';
import { EmptyState } from './ui/EmptyState';
import { ErrorState } from './ui/ErrorState';
import { Skeleton } from './ui/Skeleton';

interface MixLibraryProps {
  mixes: MixListItem[];
  selectedId: string | null;
  loading: boolean;
  error: string | null;
  onSelect: (mixId: string) => void;
  onRetry: () => void;
  isDark: boolean;
}

/** Honest library states: loading skeleton, empty, error+retry, content. No demo data. */
export const MixLibrary: React.FC<MixLibraryProps> = ({
  mixes,
  selectedId,
  loading,
  error,
  onSelect,
  onRetry,
  isDark,
}) => (
  <div
    className={`border rounded-lg p-4 h-fit ${
      isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'
    }`}
  >
    <div className="flex justify-between items-center mb-3">
      <h2 className={`text-xs font-bold uppercase tracking-widest ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>
        Mix Archive
      </h2>
      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#ea580c]/20 text-[#ea580c]">
        {loading ? '…' : `${mixes.length} Sets`}
      </span>
    </div>

    {loading && <Skeleton lines={3} label="Loading mixes" isDark={isDark} />}

    {!loading && error && (
      <ErrorState
        title="Could not load mixes"
        message={error}
        onRetry={onRetry}
        retryLabel="Retry"
        isDark={isDark}
      />
    )}

    {!loading && !error && mixes.length === 0 && (
      <div className={`text-xs leading-relaxed ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
        <EmptyState
          title="No mixes yet."
          description={
            <>
              Upload a long set from <span className="font-semibold">Pipeline &amp; Broadcast</span> to
              start engine analysis.
            </>
          }
        />
        {/* Live announcements for the library surface are handled by the AppShell route region. */}
      </div>
    )}

    {!loading && !error && mixes.length > 0 && (
      <ul className="space-y-2">
        {mixes.map((m) => {
          const selected = selectedId === m.id;
          return (
            <li key={m.id}>
              <button
                onClick={() => onSelect(m.id)}
                aria-current={selected ? 'true' : undefined}
                className={`w-full text-left p-3 rounded text-sm transition-all border min-h-[44px] ${
                  selected
                    ? isDark
                      ? 'bg-[#241a18] border-[#ea580c] text-white shadow'
                      : 'bg-orange-50 border-[#ea580c] text-[#c2410c] font-bold shadow-sm'
                    : isDark
                      ? 'bg-[#1a1c24] border-[#292c38] text-[#9ca3af] hover:border-[#4b5563]'
                      : 'bg-[#f9fafb] border-[#e5e7eb] text-[#4b5563] hover:border-[#cbd5e1]'
                }`}
              >
                <div className="font-semibold truncate">{m.title || m.original_filename}</div>
                <div className={`text-xs mt-1 flex justify-between font-mono ${isDark ? 'text-[#71717a]' : 'text-[#6b7280]'}`}>
                  <span>{formatTime(m.duration_seconds || 0)}</span>
                  <span>{m.bpm ? `${m.bpm.toFixed(1)} BPM` : 'Pending analysis'}</span>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    )}
  </div>
);
