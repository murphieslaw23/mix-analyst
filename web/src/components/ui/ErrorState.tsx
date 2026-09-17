import React from 'react';

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  isDark?: boolean;
}

/** Honest error state with retry. Retry control meets 44px touch target. */
export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Something went wrong',
  message,
  onRetry,
  retryLabel = 'Retry',
  isDark = true,
}) => (
  <div role="alert" data-testid="error-state" className="text-sm">
    <p className="font-semibold text-red-400">{title}</p>
    <p className={`text-xs mt-1 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>{message}</p>
    {onRetry ? (
      <button
        onClick={onRetry}
        className="mt-3 px-4 py-2 min-h-[44px] min-w-[44px] rounded bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold"
      >
        {retryLabel}
      </button>
    ) : null}
  </div>
);

export default ErrorState;
