import React from 'react';

interface LiveRegionProps {
  message: string;
  politeness?: 'polite' | 'assertive';
}

/** Visually-hidden live region for route/state announcements. */
export const LiveRegion: React.FC<LiveRegionProps> = ({
  message,
  politeness = 'polite',
}) => (
  <div
    aria-live={politeness}
    role="status"
    data-testid="live-region"
    className="sr-only"
  >
    {message}
  </div>
);

export default LiveRegion;
