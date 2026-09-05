import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient, asApiProblem, type ApiProblem } from "../../api/client";
import type { JobListDto } from "../../api/contracts";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorState } from "../../components/ui/ErrorState";
import { Button } from "../../components/ui/Button";
import { Progress } from "../../components/ui/Progress";
import { Skeleton } from "../../components/ui/Skeleton";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { BATCHES_ROUTE, JOBS_ROUTE } from "../../app/routes";
import { asJobListDto, toJobViewModels, type JobViewModel } from "./jobAdapters";

type JobsResource =
  | { status: "loading"; jobs: JobViewModel[]; total: number; problem: null; nextCursor: string | null; loadingMore: false; loadMoreProblem: null }
  | { status: "ready"; jobs: JobViewModel[]; total: number; problem: null; nextCursor: string | null; loadingMore: boolean; loadMoreProblem: ApiProblem | null }
  | { status: "error"; jobs: JobViewModel[]; total: number; problem: ApiProblem; nextCursor: string | null; loadingMore: false; loadMoreProblem: null };

const PAGE_SIZE = 20;
const loadingState: JobsResource = { status: "loading", jobs: [], total: 0, problem: null, nextCursor: null, loadingMore: false, loadMoreProblem: null };

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
  const resourceRef = useRef<JobsResource>(loadingState);

  useEffect(() => {
    resourceRef.current = resource;
  }, [resource]);

  const load = useCallback((cursor: string | null = null, append = false) => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    const version = ++requestVersion.current;
    if (append) {
      setResource((current) => current.status === "ready"
        ? { ...current, loadingMore: true, loadMoreProblem: null }
        : current);
    } else {
      setResource(loadingState);
    }
    void (async () => {
      try {
        const query = cursor ? `?limit=${PAGE_SIZE}&cursor=${encodeURIComponent(cursor)}` : `?limit=${PAGE_SIZE}`;
        const response = await apiClient<unknown>(`/jobs${query}`, { signal: controller.signal });
        const list: JobListDto = asJobListDto(response);
        if (!controller.signal.aborted && mounted.current && version === requestVersion.current) {
          const pageJobs = toJobViewModels(list);
          setResource((current) => {
            const jobs = append
              ? [...current.jobs, ...pageJobs.filter((candidate) => !current.jobs.some((job) => job.id === candidate.id))]
              : pageJobs;
            return {
              status: "ready",
              jobs,
              total: list.total,
              problem: null,
              nextCursor: list.next_cursor,
              loadingMore: false,
              loadMoreProblem: null,
            };
          });
        }
      } catch (error) {
        if (!controller.signal.aborted && mounted.current && version === requestVersion.current) {
          if (append) {
            setResource((current) => current.status === "ready"
              ? { ...current, loadingMore: false, loadMoreProblem: asApiProblem(error) }
              : current);
          } else {
            setResource({ status: "error", jobs: [], total: 0, problem: asApiProblem(error), nextCursor: null, loadingMore: false, loadMoreProblem: null });
          }
        }
      }
    })();
  }, []);

  const loadMore = useCallback(() => {
    const current = resourceRef.current;
    if (current.status !== "ready" || current.loadingMore || !current.nextCursor) return;
    load(current.nextCursor, true);
  }, [load]);

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
        <>
          <p className="jobs-page__count" aria-live="polite">Showing {resource.jobs.length} of {resource.total} job{resource.total === 1 ? "" : "s"}.</p>
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
                {job.batchId ? <Link className="job-card__batch-link" to={`${BATCHES_ROUTE}/${encodeURIComponent(job.batchId)}`}>View batch recovery</Link> : null}
              </li>
            ))}
          </ol>
          {resource.nextCursor ? (
            <div className="jobs-page__pagination">
              <Button tone="secondary" onClick={loadMore} disabled={resource.loadingMore}>
                {resource.loadingMore ? "Loading more jobs" : "Load more jobs"}
              </Button>
              {resource.loadMoreProblem ? <ErrorState onRetry={loadMore} problem={resource.loadMoreProblem} /> : null}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
