import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient, asApiProblem, type ApiProblem } from "../../api/client";
import type { JobListDto } from "../../api/contracts";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorState } from "../../components/ui/ErrorState";
import { Progress } from "../../components/ui/Progress";
import { Skeleton } from "../../components/ui/Skeleton";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { JOBS_ROUTE } from "../../app/routes";
import { asJobListDto, toJobViewModels, type JobViewModel } from "./jobAdapters";

type JobsResource =
  | { status: "loading"; jobs: JobViewModel[]; total: number; problem: null }
  | { status: "ready"; jobs: JobViewModel[]; total: number; problem: null }
  | { status: "error"; jobs: JobViewModel[]; total: number; problem: ApiProblem };

const loadingState: JobsResource = { status: "loading", jobs: [], total: 0, problem: null };

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Date unavailable" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

/** Project-scoped durable job list. Each card links to server-authoritative detail. */
export function JobsPage() {
  const [resource, setResource] = useState<JobsResource>(loadingState);
  const mounted = useRef(false);
  const activeRequest = useRef<AbortController | null>(null);
  const requestVersion = useRef(0);

  const load = useCallback(() => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    const version = ++requestVersion.current;
    setResource(loadingState);
    void (async () => {
      try {
        const response = await apiClient<unknown>("/jobs?page=1&limit=20", { signal: controller.signal });
        const list: JobListDto = asJobListDto(response);
        if (!controller.signal.aborted && mounted.current && version === requestVersion.current) {
          setResource({ status: "ready", jobs: toJobViewModels(list), total: list.total, problem: null });
        }
      } catch (error) {
        if (!controller.signal.aborted && mounted.current && version === requestVersion.current) {
          setResource({ status: "error", jobs: [], total: 0, problem: asApiProblem(error) });
        }
      }
    })();
  }, []);

  useEffect(() => {
    mounted.current = true;
    load();
    return () => {
      mounted.current = false;
      activeRequest.current?.abort();
    };
  }, [load]);

  return (
    <section className="route-page jobs-page" aria-labelledby="page-heading">
      <p className="eyebrow">Work queue</p>
      <h1 id="page-heading" tabIndex={-1}>Jobs</h1>
      <p className="route-page__description">Every status is read from the processing service. Open a job to see its current stage and recovery options.</p>
      {resource.status === "loading" ? <Skeleton label="Loading jobs" /> : null}
      {resource.status === "error" && resource.problem ? <ErrorState onRetry={load} problem={resource.problem} /> : null}
      {resource.status === "ready" && resource.total === 0 ? (
        <EmptyState title="No jobs yet">Choose an audio file in Process to start a server-confirmed mastering job.</EmptyState>
      ) : null}
      {resource.status === "ready" && resource.jobs.length > 0 ? (
        <ol className="jobs-list" aria-label={`${resource.total} job${resource.total === 1 ? "" : "s"}`}>
          {resource.jobs.map((job) => (
            <li className="job-card" key={job.id}>
              <div className="job-card__summary">
                <div>
                  <p className="job-card__eyebrow">{job.typeLabel}</p>
                  <h2>{job.currentStage ?? `${job.typeLabel} job`}</h2>
                </div>
                <StatusBadge status={job.status} />
              </div>
              <Progress label={`${job.typeLabel} progress`} value={job.progressPercent} />
              <p className="job-card__time">Started {formatTime(job.createdAt)}</p>
              <Link className="button button--secondary" to={`${JOBS_ROUTE}/${encodeURIComponent(job.id)}`}>View job</Link>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
