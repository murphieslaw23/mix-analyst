import type { BatchDto, JobDto } from "../../api/contracts";
import { asJobDto, toJobViewModel, type JobViewModel } from "../jobs/jobAdapters";

export type BatchStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "PARTIAL_FAILED" | "CANCELLED";

export interface BatchViewModel {
  id: string;
  status: BatchStatus;
  totalCount: number;
  completedCount: number;
  failedCount: number;
  cancelledCount: number;
  maxParallelism: number;
  presetName: string;
  preset: Record<string, unknown>;
  items: JobViewModel[];
  createdAt: string;
  updatedAt: string;
}

const batchStatuses = new Set<BatchStatus>(["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "PARTIAL_FAILED", "CANCELLED"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function hasNonNegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

/** Reject malformed aggregate read models instead of deriving a fake batch. */
export function asBatchDto(value: unknown): BatchDto {
  if (!isRecord(value)
    || typeof value.id !== "string"
    || typeof value.status !== "string" || !batchStatuses.has(value.status as BatchStatus)
    || !hasNonNegativeInteger(value.total_count)
    || !hasNonNegativeInteger(value.completed_count)
    || !hasNonNegativeInteger(value.failed_count)
    || !hasNonNegativeInteger(value.cancelled_count)
    || !Array.isArray(value.items)
    || !value.items.every((item) => {
      try { asJobDto(item); return true; } catch { return false; }
    })
    || !isRecord(value.preset)
    || !hasNonNegativeInteger(value.max_parallelism) || value.max_parallelism < 1 || value.max_parallelism > 4
    || typeof value.created_at !== "string"
    || typeof value.updated_at !== "string") {
    throw new TypeError("The batch response did not match the expected durable batch contract.");
  }
  const terminalCount = value.completed_count + value.failed_count + value.cancelled_count;
  if (terminalCount > value.total_count || value.items.length !== value.total_count) {
    throw new TypeError("The batch response contained inconsistent aggregate counts.");
  }
  return value as unknown as BatchDto;
}

function presetName(preset: Record<string, unknown>): string {
  if (typeof preset.preset_name === "string" && preset.preset_name.trim()) return preset.preset_name;
  if (typeof preset.preset_id === "string" && preset.preset_id.trim()) return preset.preset_id.replace(/[_-]+/g, " ");
  return "Custom mastering settings";
}

export function toBatchViewModel(batch: BatchDto): BatchViewModel {
  return {
    id: batch.id,
    status: batch.status as BatchStatus,
    totalCount: batch.total_count,
    completedCount: batch.completed_count,
    failedCount: batch.failed_count,
    cancelledCount: batch.cancelled_count,
    maxParallelism: batch.max_parallelism,
    presetName: presetName(batch.preset),
    preset: { ...batch.preset },
    items: batch.items.map((item: JobDto) => toJobViewModel(item)),
    createdAt: batch.created_at,
    updatedAt: batch.updated_at,
  };
}

export function isBatchTerminal(status: BatchStatus): boolean {
  return status === "SUCCEEDED" || status === "FAILED" || status === "PARTIAL_FAILED" || status === "CANCELLED";
}

export function aggregateProgress(batch: BatchViewModel): number {
  if (batch.totalCount === 0) return 0;
  return ((batch.completedCount + batch.failedCount + batch.cancelledCount) / batch.totalCount) * 100;
}
