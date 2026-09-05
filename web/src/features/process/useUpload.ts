import { useCallback, useEffect, useReducer, useRef } from "react";
import { ApiProblemError, apiClient, asApiProblem } from "../../api/client";
import type { ApiProblem, JobDto, UploadChunkDto, UploadCompleteDto, UploadSessionDto, UploadStatusDto } from "../../api/contracts";
import { initialProcessUploadState, processReducer } from "./processReducer";
import { allowedAudioExtensions, type ProcessSettings } from "./types";

const audioTypePrefix = "audio/";
const resumableUploadStorageKey = "mix-master.resumable-upload.v1";

interface StoredUploadSession {
  fileName: string;
  fileSize: number;
  fileLastModified: number;
  session: UploadSessionDto;
}

class SessionResumeError extends ApiProblemError {
  readonly discardSession = true;
}

function fileExtension(filename: string) {
  const dotIndex = filename.lastIndexOf(".");
  return dotIndex < 0 ? "" : filename.slice(dotIndex).toLowerCase();
}

function readableTitle(filename: string) {
  const extension = fileExtension(filename);
  return filename.slice(0, Math.max(1, filename.length - extension.length));
}

function validationProblem(file: File): ApiProblem | null {
  if (file.size === 0) {
    return { status: 422, title: "Choose an audio file with content", detail: "The selected file is empty.", retryable: false };
  }
  const extension = fileExtension(file.name);
  if (!allowedAudioExtensions.includes(extension as (typeof allowedAudioExtensions)[number])) {
    return { status: 422, title: "Choose a supported audio file", detail: "Use WAV, AIFF, FLAC, or MP3 audio.", retryable: false };
  }
  if (file.type && !file.type.startsWith(audioTypePrefix) && file.type !== "application/octet-stream") {
    return { status: 422, title: "Choose a supported audio file", detail: "The selected file is not marked as audio by your device.", retryable: false };
  }
  return null;
}

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

function safeUploadProblem(status: number): ApiProblem {
  if (status === 404 || status === 410) return { status, title: "Upload session expired", detail: "Choose the file again to start a new secure upload session.", retryable: false };
  if (status === 409) return { status, title: "Upload needs to resume", detail: "The saved upload position changed. Try again to continue safely.", retryable: true };
  if (status === 413) return { status, title: "Audio file is too large", detail: "Choose a smaller file and try again.", retryable: false };
  if (status === 422) return { status, title: "Audio could not be processed", detail: "Choose another supported audio file and try again.", retryable: false };
  if (status === 401 || status === 403) return { status, title: "Sign-in required", detail: "You do not have permission to upload audio here.", retryable: false };
  return { status, title: "Upload could not continue", detail: "Check your connection and try again.", retryable: true };
}

function sameOriginUploadUrl(url: string) {
  const parsed = new URL(url, window.location.origin);
  if (parsed.origin !== window.location.origin) {
    throw new ApiProblemError({ status: 0, title: "Unsafe upload address", detail: "The service returned an invalid upload address.", retryable: false });
  }
  return `${parsed.pathname}${parsed.search}`;
}

async function uploadRequest<T>(url: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(sameOriginUploadUrl(url), { ...init, credentials: "include" });
  } catch (error) {
    if (isAbort(error)) throw error;
    throw new ApiProblemError({ status: 0, title: "Could not reach Mix Master", detail: "Check your connection and try again.", retryable: true });
  }
  if (!response.ok) throw new ApiProblemError(safeUploadProblem(response.status));
  try {
    return await response.json() as T;
  } catch {
    throw new ApiProblemError({ status: response.status, title: "Unexpected upload response", detail: "The service sent a response we could not read. Try again.", retryable: true });
  }
}

function assertSession(session: UploadSessionDto, file: File) {
  if (!session.upload_id || !session.upload_url || session.total_size_bytes !== file.size || session.chunk_size <= 0 || session.offset < 0 || session.offset > file.size) {
    throw new ApiProblemError({ status: 0, title: "Unexpected upload response", detail: "The service returned an invalid upload session. Try again.", retryable: true });
  }
}

function resumeProblem(title: string, detail: string) {
  return new SessionResumeError({ status: 409, title, detail, retryable: false });
}

function expiryTimestamp(value: string): number | null {
  // `Date.parse` treats ISO strings without an offset as local time in some
  // browsers. The API sends an aware timestamp, and accepting a naive value
  // here could keep an expired upload resumable in a different timezone.
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/i.test(value)) {
    return null;
  }
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
}

function assertResumableExpiry(expiresAt: string) {
  const timestamp = expiryTimestamp(expiresAt);
  if (timestamp === null) {
    throw resumeProblem("Upload session cannot be resumed", "The saved upload has an invalid expiry time. Choose the file again to start a new secure upload session.");
  }
  if (timestamp <= Date.now()) {
    throw resumeProblem("Upload session expired", "Choose the file again to start a new secure upload session.");
  }
}

function sessionForResume(session: UploadSessionDto, status: UploadStatusDto, file: File): UploadSessionDto {
  // The status response omits upload_url and chunk_size by design. Those are
  // accepted init-session metadata, kept only in this browser, while the
  // server remains the sole authority for offset and lifecycle status.
  assertSession(session, file);
  if (
    status.upload_id !== session.upload_id ||
    status.filename !== file.name ||
    status.total_size_bytes !== file.size ||
    status.offset < 0 ||
    status.offset > file.size ||
    status.bytes_received !== status.offset
  ) {
    throw resumeProblem("Upload session cannot be resumed", "The saved upload does not match the selected file. Choose the file again to begin a new upload.");
  }
  // The status endpoint may still report PENDING shortly after the TTL has
  // elapsed. Its timestamp is authoritative for whether this browser may
  // continue sending protected audio chunks.
  assertResumableExpiry(status.expires_at);

  const lifecycle = status.status.toUpperCase();
  if (lifecycle === "COMPLETED") {
    throw resumeProblem("Upload session already completed", "This upload has already finished and cannot be resumed safely. Choose the file again if you still need to process it.");
  }
  if (lifecycle !== "PENDING" && lifecycle !== "UPLOADING") {
    throw resumeProblem("Upload session is no longer available", "This saved upload can no longer accept audio. Choose the file again to begin a new upload.");
  }

  return {
    ...session,
    filename: status.filename,
    total_size_bytes: status.total_size_bytes,
    offset: status.offset,
    expires_at: status.expires_at,
    status: status.status,
  };
}

function loadStoredSession(file: File): UploadSessionDto | null {
  try {
    const raw = window.sessionStorage.getItem(resumableUploadStorageKey);
    if (!raw) return null;
    const stored = JSON.parse(raw) as StoredUploadSession;
    if (
      stored.fileName !== file.name ||
      stored.fileSize !== file.size ||
      stored.fileLastModified !== file.lastModified ||
      !stored.session
    ) return null;
    assertSession(stored.session, file);
    return stored.session;
  } catch {
    return null;
  }
}

function rememberSession(file: File, session: UploadSessionDto) {
  try {
    const stored: StoredUploadSession = {
      fileName: file.name,
      fileSize: file.size,
      fileLastModified: file.lastModified,
      session,
    };
    window.sessionStorage.setItem(resumableUploadStorageKey, JSON.stringify(stored));
  } catch {
    // Private browsing/storage quotas must not prevent an otherwise valid
    // current-page upload. The in-memory reducer still owns this attempt.
  }
}

function forgetStoredSession() {
  try {
    window.sessionStorage.removeItem(resumableUploadStorageKey);
  } catch {
    // Storage may be unavailable; there is no user-visible recovery needed.
  }
}

export function useUpload() {
  const [state, dispatch] = useReducer(processReducer, initialProcessUploadState);
  const stateRef = useRef(state);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const selectFile = useCallback((file: File | null) => {
    if (!file) return;
    dispatch({ type: "SELECT", file });
    const problem = validationProblem(file);
    if (problem) {
      forgetStoredSession();
      dispatch({ type: "INVALID", problem });
      return;
    }
    const storedSession = loadStoredSession(file);
    if (storedSession) {
      dispatch({ type: "RESUME_AVAILABLE", session: storedSession, offset: storedSession.offset });
      return;
    }
    // Selecting a different file intentionally abandons only the local resume
    // record; the server still expires the old protected upload on schedule.
    forgetStoredSession();
    dispatch({ type: "VALID" });
  }, []);

  const uploadAudio = useCallback(async (file: File, controller: AbortController): Promise<{ mixId: string }> => {
    const current = stateRef.current;
    let session = current.session;

    try {
      if (session) {
        let serverStatus: UploadStatusDto;
        try {
          serverStatus = await uploadRequest<UploadStatusDto>(session.upload_url, { signal: controller.signal });
        } catch (error) {
          if (error instanceof ApiProblemError && (error.status === 404 || error.status === 410)) {
            throw resumeProblem("Upload session expired", "Choose the file again to start a new secure upload session.");
          }
          throw error;
        }
        session = sessionForResume(session, serverStatus, file);
        rememberSession(file, session);
        dispatch({ type: "SESSION", session, offset: session.offset });
      } else {
        dispatch({ type: "INITIALIZING" });
        session = await apiClient<UploadSessionDto>("/", {
          method: "POST",
          signal: controller.signal,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ filename: file.name, total_size_bytes: file.size, content_type: file.type || "application/octet-stream" }),
        });
        assertSession(session, file);
        rememberSession(file, session);
        dispatch({ type: "SESSION", session, offset: session.offset });
      }

      let offset = session.offset;
      while (offset < file.size) {
        const nextOffset = Math.min(file.size, offset + session.chunk_size);
        const chunk = file.slice(offset, nextOffset);
        const update: UploadChunkDto = await uploadRequest<UploadChunkDto>(session.upload_url, {
          method: "PATCH",
          signal: controller.signal,
          headers: { "Content-Type": "application/offset+octet-stream", "Upload-Offset": String(offset) },
          body: chunk,
        });
        if (update.upload_id !== session.upload_id || update.total_size_bytes !== file.size || update.offset <= offset || update.offset > file.size) {
          throw new ApiProblemError({ status: 0, title: "Unexpected upload progress", detail: "The service returned an invalid upload position. Try again.", retryable: true });
        }
        offset = update.offset;
        session = { ...session, offset, status: update.status };
        rememberSession(file, session);
        dispatch({ type: "UPLOAD_PROGRESS", percent: (offset / file.size) * 100 });
      }

      dispatch({ type: "FINALIZING" });
      const complete = await uploadRequest<UploadCompleteDto>(`${session.upload_url}/complete`, {
        method: "POST",
        signal: controller.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: readableTitle(file.name) }),
      });
      if (!complete.mix_id) {
        throw new ApiProblemError({ status: 0, title: "Unexpected completion response", detail: "The service did not confirm a saved audio item. Try again.", retryable: true });
      }
      forgetStoredSession();
      dispatch({ type: "READY", mixId: complete.mix_id });
      return { mixId: complete.mix_id };
    } catch (error) {
      if (isAbort(error)) {
        dispatch({ type: "ABORT" });
        throw error;
      }
      const problem = asApiProblem(error);
      // A 410 can arrive while appending a chunk or finalizing, after this
      // page has already retained its session metadata. It is terminal for
      // that metadata, unlike network/5xx/conflict failures which remain
      // honestly retryable.
      const discardSession = error instanceof SessionResumeError || (error instanceof ApiProblemError && error.status === 410);
      if (discardSession) forgetStoredSession();
      dispatch({ type: "FAIL", problem, discardSession });
      throw error;
    }
  }, []);

  const startMastering = useCallback(async (settings: ProcessSettings): Promise<{ jobId: string } | null> => {
    const current = stateRef.current;
    const file = current.file;
    if (!file) return null;
    const validation = validationProblem(file);
    if (validation) {
      dispatch({ type: "FAIL", problem: validation });
      return null;
    }

    const controller = new AbortController();
    controllerRef.current?.abort();
    controllerRef.current = controller;

    try {
      const mixId = current.mixId ?? (await uploadAudio(file, controller)).mixId;
      dispatch({ type: "QUEUEING" });
      const job = await apiClient<JobDto>(`/mixes/${encodeURIComponent(mixId)}/master`, {
        method: "POST",
        signal: controller.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preset_id: settings.presetId }),
      });
      if (!job.id || job.mix_id !== mixId) {
        throw new ApiProblemError({ status: 0, title: "Unexpected mastering response", detail: "The service did not confirm a saved mastering job. Try again.", retryable: true });
      }
      // The job is durable before ProcessPage navigates to it. Clearing the
      // busy state also removes the cancel control as its controller closes.
      dispatch({ type: "JOB_CREATED", jobId: job.id });
      return { jobId: job.id };
    } catch (error) {
      if (isAbort(error)) {
        // `uploadAudio` also emits this transition when it owns the aborted
        // request. Repeating the terminal reducer event is harmless and,
        // crucially, covers an abort while the durable job command is pending.
        dispatch({ type: "ABORT" });
        return null;
      }
      dispatch({ type: "FAIL", problem: asApiProblem(error) });
      return null;
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null;
    }
  }, [uploadAudio]);

  const cancel = useCallback(() => controllerRef.current?.abort(), []);
  const reset = useCallback(() => {
    forgetStoredSession();
    dispatch({ type: "RESET" });
  }, []);

  return { state, selectFile, startMastering, cancel, reset };
}
