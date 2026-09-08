import { useParams } from "react-router-dom";
import { Button } from "../../components/ui/Button";
import { ErrorState } from "../../components/ui/ErrorState";
import { LiveRegion } from "../../components/ui/LiveRegion";
import { Progress } from "../../components/ui/Progress";
import { Skeleton } from "../../components/ui/Skeleton";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { canCancelJob, canRetryJob } from "./jobAdapters";
import { useJobEvents } from "./useJobEvents";

function jobHeading(typeLabel: string, status: string): string {
  if (status === "FAILED") return `${typeLabel} failed`;
  if (status === "CANCELLED") return `${typeLabel} cancelled`;
  if (status === "SUCCEEDED") return `${typeLabel} complete`;
  return `${typeLabel} job`;
}

function connectionLabel(connection: "connecting" | "live" | "polling" | "closed") {
  if (connection === "live") return "Live progress connected.";
  if (connection === "connecting") return "Reconnecting to live progress.";
  if (connection === "polling") return "Live progress is unavailable. Checking the server every few seconds.";
  return "This job is no longer receiving progress updates.";
}

export function JobDetailPage() {
  const { jobId } = useParams();
  const { status, job, problem, connection, actionPending, actionProblem, cancel, retry, retryLoad } = useJobEvents(jobId);

  if (status === "loading") {
    return <section className="route-page jobs-page" aria-labelledby="page-heading"><p className="eyebrow">Work queue</p><h1 id="page-heading" tabIndex={-1}>Job</h1><Skeleton label="Loading job" /></section>;
  }
  if (status === "error" || !job) {
    return (
      <section className="route-page jobs-page" aria-labelledby="page-heading">
        <p className="eyebrow">Work queue</p>
        <h1 id="page-heading" tabIndex={-1}>Job unavailable</h1>
        {problem ? <ErrorState onRetry={retryLoad} problem={problem} /> : null}
      </section>
    );
  }

  return (
    <section className="route-page job-detail-page" aria-labelledby="page-heading">
      <p className="eyebrow">Work queue · attempt {job.attempts[job.attempts.length - 1]?.number ?? 1}</p>
      <div className="job-detail-page__heading">
        <h1 id="page-heading" tabIndex={-1}>{jobHeading(job.typeLabel, job.status)}</h1>
        <StatusBadge status={job.status} />
      </div>
      <p className="route-page__description">{job.currentStage ? `Current stage: ${job.currentStage}.` : "The service has not reported a processing stage yet."}</p>
      <LiveRegion className="job-detail-page__connection">{connectionLabel(connection)}</LiveRegion>
      <Progress className="job-detail-page__progress" label={`${job.typeLabel} progress`} value={job.progressPercent} />

      {job.errorMessage ? (
        <section className="job-detail-page__error" aria-labelledby="job-error-heading" role="alert">
          <h2 id="job-error-heading">Recovery information</h2>
          <p>{job.errorMessage}</p>
        </section>
      ) : null}
      {job.stages.length > 0 ? (
        <section className="job-detail-page__stages" aria-labelledby="stage-heading">
          <h2 id="stage-heading">Processing stages</h2>
          <ol>
            {job.stages.map((stage) => (
              <li key={stage.id}>
                <div><h3>{stage.name}</h3><StatusBadge status={stage.status} /></div>
                <Progress label={`${stage.name} progress`} value={stage.progressPercent} />
                {stage.errorMessage ? <p className="job-detail-page__stage-error">{stage.errorMessage}</p> : null}
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {actionProblem ? <ErrorState problem={actionProblem} /> : null}
      <div className="job-detail-page__actions" aria-label="Job actions">
        {canCancelJob(job.status) ? <Button disabled={actionPending} onClick={() => void cancel()} tone="secondary">Cancel job</Button> : null}
        {canRetryJob(job.status) ? <Button disabled={actionPending} onClick={() => void retry()}>Retry job</Button> : null}
      </div>
    </section>
  );
}
