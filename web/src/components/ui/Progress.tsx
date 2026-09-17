import React from 'react';

interface ProgressProps {
  value: number;
  label: string;
  testId?: string;
  isDark?: boolean;
}

/** Accessible linear progress: always exposes role=progressbar semantics. */
export const Progress: React.FC<ProgressProps> = ({
  value,
  label,
  testId = 'progress-bar',
  isDark = true,
}) => {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        data-testid={testId}
        className={`h-2 rounded-full overflow-hidden ${isDark ? 'bg-[#232630]' : 'bg-[#e5e7eb]'}`}
      >
        <div
          className="h-full bg-[#ea580c] transition-all"
          style={{ width: `${clamped}%` }}
        />
      </div>
      <p className={`text-[11px] font-mono mt-1 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
        {label} — {clamped}%
      </p>
    </div>
  );
};

export default Progress;
