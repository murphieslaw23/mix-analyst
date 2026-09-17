import React from 'react';

interface EmptyStateProps {
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
}

/** Honest empty state — never renders fabricated content. */
export const EmptyState: React.FC<EmptyStateProps> = ({ title, description, action }) => (
  <div data-testid="empty-state">
    <p className="text-xs leading-relaxed">{title}</p>
    {description ? <div className="text-xs leading-relaxed mt-1">{description}</div> : null}
    {action ? <div className="mt-3">{action}</div> : null}
  </div>
);

export default EmptyState;
