import type { ReactNode } from "react";

interface LiveRegionProps {
  children?: ReactNode;
  assertive?: boolean;
  className?: string;
}

/** Announces meaningful application state changes without moving focus. */
export function LiveRegion({ children, assertive = false, className }: LiveRegionProps) {
  return (
    <div
      aria-atomic="true"
      aria-live={assertive ? "assertive" : "polite"}
      className={className}
      role={assertive ? "alert" : "status"}
    >
      {children}
    </div>
  );
}
