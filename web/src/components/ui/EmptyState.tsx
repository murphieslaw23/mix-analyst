import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  children?: ReactNode;
}

export function EmptyState({ title, children }: EmptyStateProps) {
  return (
    <section className="resource-state resource-state--empty" aria-labelledby="empty-state-title">
      <h2 id="empty-state-title">{title}</h2>
      {children ? <p>{children}</p> : null}
    </section>
  );
}
