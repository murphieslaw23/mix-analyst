import { useCallback, useEffect, useReducer, useRef } from "react";
import { ApiProblemError, apiClient, asApiProblem } from "../../api/client";
import type { ApiProblem, JobDto, UploadChunkDto, UploadCompleteDto, UploadSessionDto } from "../../api/contracts";
import { initialProcessUploadState, processReducer } from "./processReducer";
import { allowedAudioExtensions, type ProcessSettings } from "./types";

const audioTypePrefix = "audio/";

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
    dispatch(problem ? { type: "INVALID", problem } : { type: "VALID" });
  }, []);

  const startUpload = useCallback(async (file: File, _settings: ProcessSettings): Promise<{ mixId: string }> => {
    const controller = new AbortController();
    controllerRef.current?.abort();
    controllerRef.current = controller;
    const current = stateRef.current;
    let session = current.session;

    try {
      if (session) {
        const serverSession = await uploadRequest<UploadSessionDto>(session.upload_url, { signal: controller.signal });
        assertSession(serverSession, file);
        session = serverSession;
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
        dispatch({ type: "SESSION", session, offset: session.offset });
      }

      let offset = session.offset;
      while (offset < file.size) {
        const nextOffset = Math.min(file.size, offset + session.chunk_size);
        const chunk = file.slice(offset, nextOffset);
        const update = await uploadRequest<UploadChunkDto>(session.upload_url, {
          method: "PATCH",
          signal: controller.signal,
          headers: { "Content-Type": "application/offset+octet-stream", "Upload-Offset": String(offset) },
          body: chunk,
        });
        if (update.upload_id !== session.upload_id || update.total_size_bytes !== file.size || update.offset <= offset || update.offset > file.size) {
          throw new ApiProblemError({ status: 0, title: "Unexpected upload progress", detail: "The service returned an invalid upload position. Try again.", retryable: true });
        }
        offset = update.offset;
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
      dispatch({ type: "READY", mixId: complete.mix_id });
      return { mixId: complete.mix_id };
    } catch (error) {
      if (isAbort(error)) {
        dispatch({ type: "ABORT" });
        throw error;
      }
      const problem = asApiProblem(error);
      dispatch({ type: "FAIL", problem });
      throw error;
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null;
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

    try {
      const mixId = current.mixId ?? (await startUpload(file, settings)).mixId;
      dispatch({ type: "QUEUEING" });
      const job = await apiClient<JobDto>(`/mixes/${encodeURIComponent(mixId)}/master`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preset_id: settings.presetId }),
      });
      if (!job.id || job.mix_id !== mixId) {
        throw new ApiProblemError({ status: 0, title: "Unexpected mastering response", detail: "The service did not confirm a saved mastering job. Try again.", retryable: true });
      }
      return { jobId: job.id };
    } catch (error) {
      if (isAbort(error)) return null;
      dispatch({ type: "FAIL", problem: asApiProblem(error) });
      return null;
    }
  }, [startUpload]);

  const cancel = useCallback(() => controllerRef.current?.abort(), []);
  const reset = useCallback(() => dispatch({ type: "RESET" }), []);

  return { state, selectFile, startUpload, startMastering, cancel, reset };
}
