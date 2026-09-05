interface ProgressProps {
  value: number;
  label: string;
  className?: string;
}

export function Progress({ value, label, className }: ProgressProps) {
  const boundedValue = Math.max(0, Math.min(100, value));
  return (
    <div className={className ? `progress ${className}` : "progress"}>
      <div className="progress__label">
        <span>{label}</span>
        <span>{Math.round(boundedValue)}%</span>
      </div>
      <progress aria-label={label} max={100} value={boundedValue}>{Math.round(boundedValue)}%</progress>
    </div>
  );
}
