import React from 'react';

interface SkeletonProps {
  lines?: number;
  label?: string;
  isDark?: boolean;
}

/** Loading placeholder with accessible busy semantics. */
export const Skeleton: React.FC<SkeletonProps> = ({ lines = 3, label = 'Loading', isDark = true }) => (
  <div className="space-y-2" aria-busy="true" aria-label={label} data-testid="skeleton">
    {Array.from({ length: lines }, (_, i) => (
      <div
        key={i}
        className={`p-3 rounded border animate-pulse ${isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]'}`}
      >
        <div className={`h-4 rounded w-3/4 ${isDark ? 'bg-[#292c38]' : 'bg-[#e5e7eb]'}`} />
        <div className={`h-3 rounded w-1/2 mt-2 ${isDark ? 'bg-[#292c38]' : 'bg-[#e5e7eb]'}`} />
      </div>
    ))}
  </div>
);

export default Skeleton;
