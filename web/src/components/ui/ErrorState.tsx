import type { ApiProblem } from "../../api/client";
import { Button } from "./Button";

interface ErrorStateProps {
  problem: ApiProblem;
  onRetry?: () => void;
}

export function ErrorState({ problem, onRetry }: ErrorStateProps) {
  return (
    <section className="resource-state resource-state--error" aria-labelledby="error-state-title" role="alert">
      <h2 id="error-state-title">{problem.title}</h2>
      <p>{problem.detail}</p>
      {problem.retryable && onRetry ? <Button onClick={onRetry}>Try again</Button> : null}
    </section>
  );
}
