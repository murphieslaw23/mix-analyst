import type { ApiProblem, UploadSessionDto } from "../../api/contracts";
import type { ProcessUploadModel } from "./types";

export type ProcessUploadEvent =
  | { type: "SELECT"; file: File }
  | { type: "VALID" }
  | { type: "INVALID"; problem: ApiProblem }
  | { type: "INITIALIZING" }
  | { type: "SESSION"; session: UploadSessionDto; offset: number }
  | { type: "UPLOAD_PROGRESS"; percent: number }
  | { type: "FINALIZING" }
  | { type: "READY"; mixId: string }
  | { type: "QUEUEING" }
  | { type: "FAIL"; problem: ApiProblem }
  | { type: "ABORT" }
  | { type: "RESET" };

export const initialProcessUploadState: ProcessUploadModel = {
  status: "idle",
  file: null,
  session: null,
  mixId: null,
  progressPercent: 0,
  stage: null,
  problem: null,
};

export function processReducer(state: ProcessUploadModel, event: ProcessUploadEvent): ProcessUploadModel {
  switch (event.type) {
    case "SELECT":
      return { ...initialProcessUploadState, status: "selected", file: event.file, stage: "selection" };
    case "VALID":
      return { ...state, status: "ready", stage: "selection", problem: null };
    case "INVALID":
      return { ...state, status: "error", stage: "selection", problem: event.problem };
    case "INITIALIZING":
      return { ...state, status: "initializing", stage: "upload", problem: null, progressPercent: 0, mixId: null };
    case "SESSION":
      return {
        ...state,
        status: "uploading",
        stage: "upload",
        session: event.session,
        progressPercent: Math.max(0, Math.min(100, Math.round((event.offset / event.session.total_size_bytes) * 100))),
      };
    case "UPLOAD_PROGRESS":
      return { ...state, status: "uploading", stage: "upload", progressPercent: Math.max(0, Math.min(100, event.percent)) };
    case "FINALIZING":
      return { ...state, status: "finalizing", stage: "finalizing", progressPercent: 100, problem: null };
    case "READY":
      return { ...state, status: "ready", mixId: event.mixId, stage: "selection", progressPercent: 100, problem: null };
    case "QUEUEING":
      return { ...state, status: "finalizing", stage: "queueing", problem: null };
    case "FAIL":
      return { ...state, status: "error", problem: event.problem };
    case "ABORT":
      return { ...state, status: "aborted", problem: null };
    case "RESET":
      return initialProcessUploadState;
  }
}
