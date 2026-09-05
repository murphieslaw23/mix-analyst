import type { JobDto, JobListDto, JobAttemptDto, StageRunDto } from "../../api/contracts";

export type JobStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELLED";

export interface StageViewModel {
  id: string;
  name: string;
  version: string;
  status: string;
  progressPercent: number;
  errorMessage: string | null;
  startedAt: string;
  finishedAt: string | null;
}

export interface JobAttemptViewModel {
  id: string;
  number: number;
  status: string;
  workerHostname: string | null;
  startedAt: string;
  finishedAt: string | null;
}

export interface JobViewModel {
  id: string;
  mixId: string;
  type: string;
  typeLabel: string;
  status: JobStatus;
  progressPercent: number;
  currentStage: string | null;
  errorMessage: string | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  stages: StageViewModel[];
  attempts: JobAttemptViewModel[];
}

const knownStatuses = new Set<JobStatus>(["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNullableString(value: unknown): value is string | null {
  return typeof value === "string" || value === null;
}

function isStageRunDto(value: unknown): value is StageRunDto {
  return isRecord(value)
    && typeof value.id === "string"
    && typeof value.stage_name === "string"
    && typeof value.stage_version === "string"
    && typeof value.status === "string"
    && typeof value.progress_percent === "number"
    && isNullableString(value.stage_output)
    && isNullableString(value.error_message)
    && typeof value.started_at === "string"
    && isNullableString(value.finished_at);
}

function isJobAttemptDto(value: unknown): value is JobAttemptDto {
  return isRecord(value)
    && typeof value.id === "string"
    && typeof value.attempt_number === "number"
    && typeof value.status === "string"
    && isNullableString(value.worker_hostname)
    && typeof value.started_at === "string"
    && isNullableString(value.finished_at);
}

/** Reject malformed API data before it can be presented as a job state. */
export function asJobDto(value: unknown): JobDto {
  if (!isRecord(value)
    || typeof value.id !== "string"
    || typeof value.mix_id !== "string"
    || typeof value.job_type !== "string"
    || typeof value.status !== "string"
    || typeof value.progress_percent !== "number"
    || !isNullableString(value.current_stage)
    || !isRecord(value.parameters)
    || !isNullableString(value.celery_task_id)
    || !isNullableString(value.error_message)
    || typeof value.created_at !== "string"
    || !isNullableString(value.started_at)
    || !isNullableString(value.finished_at)
    || !Array.isArray(value.stage_runs)
    || !value.stage_runs.every(isStageRunDto)
    || !Array.isArray(value.attempts)
    || !value.attempts.every(isJobAttemptDto)
  ) {
    throw new TypeError("The job response did not match the expected durable job contract.");
  }
  if (!knownStatuses.has(value.status as JobStatus)) {
    throw new TypeError("The job response contained an unknown durable status.");
  }
  return value as unknown as JobDto;
}

export function asJobListDto(value: unknown): JobListDto {
  if (!isRecord(value) || !Array.isArray(value.items) || !value.items.every((job) => {
    try {
      asJobDto(job);
      return true;
    } catch {
      return false;
    }
  }) || typeof value.total !== "number" || !Number.isInteger(value.total) || value.total < 0
    || !isNullableString(value.next_cursor)) {
    throw new TypeError("The jobs response did not match the expected paginated contract.");
  }
  return value as unknown as JobListDto;
}

function typeLabel(type: string): string {
  return type === "MASTERING" ? "Mastering" : type.charAt(0) + type.slice(1).toLowerCase();
}

function boundedProgress(progress: number): number {
  return Math.max(0, Math.min(100, progress));
}

export function toJobViewModel(job: JobDto): JobViewModel {
  return {
    id: job.id,
    mixId: job.mix_id,
    type: job.job_type,
    typeLabel: typeLabel(job.job_type),
    status: job.status as JobStatus,
    progressPercent: boundedProgress(job.progress_percent),
    currentStage: job.current_stage,
    errorMessage: job.error_message,
    createdAt: job.created_at,
    startedAt: job.started_at,
    finishedAt: job.finished_at,
    stages: job.stage_runs.map((stage) => ({
      id: stage.id,
      name: stage.stage_name,
      version: stage.stage_version,
      status: stage.status,
      progressPercent: boundedProgress(stage.progress_percent),
      errorMessage: stage.error_message,
      startedAt: stage.started_at,
      finishedAt: stage.finished_at,
    })),
    attempts: job.attempts.map((attempt) => ({
      id: attempt.id,
      number: attempt.attempt_number,
      status: attempt.status,
      workerHostname: attempt.worker_hostname,
      startedAt: attempt.started_at,
      finishedAt: attempt.finished_at,
    })),
  };
}

export function toJobViewModels(response: JobListDto): JobViewModel[] {
  return response.items.map(toJobViewModel);
}

export function isTerminalStatus(status: JobStatus): boolean {
  return status === "SUCCEEDED" || status === "FAILED" || status === "CANCELLED";
}

export function canCancelJob(status: JobStatus): boolean {
  return status === "QUEUED" || status === "RUNNING";
}

export function canRetryJob(status: JobStatus): boolean {
  return status === "FAILED" || status === "CANCELLED";
}
