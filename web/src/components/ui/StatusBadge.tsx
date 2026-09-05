interface StatusBadgeProps {
  status: string;
}

const statusLabels: Record<string, string> = {
  QUEUED: "Queued",
  RUNNING: "Running",
  SUCCEEDED: "Complete",
  FAILED: "Failed",
  PARTIAL_FAILED: "Partial failure",
  CANCELLED: "Cancelled",
  PENDING: "Pending",
  COMPLETED: "Complete",
  SKIPPED: "Skipped",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const tone = status.toLowerCase().replace(/[^a-z]+/g, "-");
  return <span className={`status-badge status-badge--${tone}`}>{statusLabels[status] ?? status}</span>;
}
