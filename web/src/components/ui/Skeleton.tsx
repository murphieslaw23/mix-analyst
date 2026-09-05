interface SkeletonProps {
  label?: string;
}

export function Skeleton({ label = "Loading" }: SkeletonProps) {
  return (
    <section aria-busy="true" aria-label={label} className="resource-state resource-state--loading">
      <span className="skeleton" />
      <span className="skeleton skeleton--short" />
    </section>
  );
}
