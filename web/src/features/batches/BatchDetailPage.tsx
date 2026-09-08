import { useParams } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { ErrorState } from "../../components/ui/ErrorState";
import { LiveRegion } from "../../components/ui/LiveRegion";
import { Progress } from "../../components/ui/Progress";
import { Skeleton } from "../../components/ui/Skeleton";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { aggregateProgress } from "./batchAdapters";
import { useBatch } from "./useBatch";

export function BatchDetailPage() {
  const { batchId } = useParams();
  const { status, batch, problem, actionPending, actionProblem, retryFailed, retryLoad } = useBatch(batchId);
  if (status === "loading") return <section className="route-page batch-detail-page" aria-labelledby="page-heading"><p className="eyebrow">Work queue · batch</p><h1 id="page-heading" tabIndex={-1}>Batch</h1><Skeleton label="Loading batch" /></section>;
  if (status === "error" || !batch) return <section className="route-page batch-detail-page" aria-labelledby="page-heading"><p className="eyebrow">Work queue · batch</p><h1 id="page-heading" tabIndex={-1}>Batch unavailable</h1>{problem ? <ErrorState problem={problem} onRetry={retryLoad} /> : null}</section>;

  const completedItems = batch.items.filter((item) => item.status === "SUCCEEDED");
  const failedItems = batch.items.filter((item) => item.status === "FAILED");
  const aggregateLabel = `Batch progress: ${batch.completedCount} complete, ${batch.failedCount} failed, ${batch.cancelledCount} cancelled out of ${batch.totalCount}`;
  return (
    <section className="route-page batch-detail-page" aria-labelledby="page-heading">
      <p className="eyebrow">Work queue · batch</p>
      <div className="batch-detail-page__heading"><h1 id="page-heading" tabIndex={-1}>Batch review</h1><StatusBadge status={batch.status} /></div>
      <p className="route-page__description">{batch.presetName} · up to {batch.maxParallelism} job{batch.maxParallelism === 1 ? "" : "s"} at a time.</p>
      <Progress className="batch-detail-page__progress" label={aggregateLabel} value={aggregateProgress(batch)} />
      <dl className="batch-detail-page__counts" aria-label="Batch result counts">
        <div><dt>Selected</dt><dd>{batch.totalCount}</dd></div>
        <div><dt>Complete</dt><dd>{batch.completedCount}</dd></div>
        <div><dt>Failed</dt><dd>{batch.failedCount}</dd></div>
        <div><dt>Cancelled</dt><dd>{batch.cancelledCount}</dd></div>
      </dl>
      {!failedItems.length ? <LiveRegion className="batch-detail-page__live">{batch.status === "SUCCEEDED" ? "All selected items completed." : "The server will refresh this batch while work remains."}</LiveRegion> : null}
      {completedItems.length > 0 ? <BatchItems heading={`Completed items (${completedItems.length})`} items={completedItems} /> : null}
      {failedItems.length > 0 ? <BatchItems heading={`Failed items (${failedItems.length})`} items={failedItems} /> : null}
      {actionProblem ? <ErrorState problem={actionProblem} /> : null}
      {failedItems.length > 0 ? (
        <div className="batch-detail-page__actions">
          <p>Retry scope: {failedItems.length} failed item{failedItems.length === 1 ? "" : "s"} only. Completed and cancelled items stay unchanged.</p>
          <Button disabled={actionPending} onClick={() => void retryFailed(failedItems.map((item) => item.id))}>{actionPending ? "Retrying failed items" : "Retry failed items"}</Button>
        </div>
      ) : null}
    </section>
  );
}

function BatchItems({ heading, items }: { heading: string; items: Array<{ id: string; currentStage: string | null; errorMessage: string | null; typeLabel: string; status: string }> }) {
  return (
    <section className="batch-detail-page__items" aria-labelledby={`${heading.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-heading`}>
      <h2 id={`${heading.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-heading`}>{heading}</h2>
      <ol>{items.map((item) => <li key={item.id}><div><strong>{item.currentStage ?? item.typeLabel}</strong><StatusBadge status={item.status} /></div>{item.errorMessage ? <p>{item.errorMessage}</p> : null}</li>)}</ol>
    </section>
  );
}
