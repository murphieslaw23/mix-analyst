/**
 * Upload transport + validation (Task 3).
 *
 * Reuses the backend upload-session protocol exactly as PipelinePanel does:
 * POST /uploads (init) -> PATCH /uploads/:id chunk loop (5 MB slices) ->
 * POST /uploads/:id/complete (persist mix). Transport goes through the typed
 * apiClient; the X-API-Key header is attached when one is stored, matching
 * the PipelinePanel mutation behavior.
 */
import { useCallback, useEffect, useReducer, useRef } from 'react';
import { authHeaders } from '../../api';
import { apiClient, type ApiProblem } from '../../api/client';
import { pipelinePath, navigate } from '../../app/routes';
import {
  initialProcessState,
  processReducer,
  type UploadStatus,
} from './processReducer';

export const UPLOAD_CHUNK_SIZE = 5 * 1024 * 1024;
export const MAX_UPLOAD_BYTES = 4 * 1024 * 1024 * 1024;

const AUDIO_EXTENSIONS = ['.wav', '.flac', '.mp3', '.ogg', '.m4a', '.aac', '.opus', '.aiff', '.aif'];

function mutationHeaders(): Record<string, string> {
  try {
    return authHeaders();
  } catch {
    return {};
  }
}

export function problemMessage(problem: unknown): string {
  const record = problem as Partial<ApiProblem> | null;
  if (record && typeof record.detail === 'string' && record.detail.length > 0) {
    return record.detail;
  }
  if (record && typeof record.title === 'string' && record.title.length > 0) {
    return record.title;
  }
  if (problem instanceof Error && problem.message) return problem.message;
  return 'Request failed';
}

/** Client-side gate: audio extension (or audio/* MIME) + non-empty + size cap. */
export function validateAudioFile(file: File): string | null {
  const name = file.name || '';
  const lower = name.toLowerCase();
  const hasAudioExt = AUDIO_EXTENSIONS.some((ext) => lower.endsWith(ext));
  const hasAudioMime = typeof file.type === 'string' && file.type.startsWith('audio/');
  if (!hasAudioExt && !hasAudioMime) {
    return `Unsupported file type "${name || 'unknown'}". Choose an audio file (${AUDIO_EXTENSIONS.join(', ')}).`;
  }
  if (file.size <= 0) {
    return 'That file is empty. Choose a non-empty audio file.';
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return 'That file exceeds the 4 GB upload limit.';
  }
  return null;
}

export interface ProcessInput {
  title: string;
  artist: string;
}

export interface UploadCallbacks {
  onInit?: (uploadId: string) => void;
  onProgress?: (percent: number) => void;
  signal?: AbortSignal;
}

interface UploadInitOut {
  upload_id: string;
}

interface UploadChunkOut {
  bytes_received: number;
}

interface UploadCompleteOut {
  mix_id: string;
}

/**
 * Run the chunked protocol for one file. Progress is reported per confirmed
 * server offset; a non-advancing server offset aborts instead of looping.
 */
export async function startUpload(
  file: File,
  input: ProcessInput,
  callbacks: UploadCallbacks = {},
): Promise<{ mixId: string; uploadId: string }> {
  const { onInit, onProgress, signal } = callbacks;
  const throwIfAborted = () => {
    if (signal?.aborted) throw new DOMException('Upload cancelled', 'AbortError');
  };

  const init = await apiClient<UploadInitOut>('/uploads', {
    method: 'POST',
    headers: { ...mutationHeaders() },
    body: JSON.stringify({
      filename: file.name,
      total_size_bytes: file.size,
      chunk_size: UPLOAD_CHUNK_SIZE,
    }),
    signal,
  });
  const uploadId = init.upload_id;
  onInit?.(uploadId);
  throwIfAborted();

  const total = file.size;
  let offset = 0;
  while (offset < total) {
    throwIfAborted();
    const slice = file.slice(offset, offset + UPLOAD_CHUNK_SIZE);
    const form = new FormData();
    form.append('file', slice, file.name);
    form.append('offset', String(offset));
    const chunk = await apiClient<UploadChunkOut>(
      `/uploads/${encodeURIComponent(uploadId)}`,
      { method: 'PATCH', headers: { ...mutationHeaders() }, body: form, signal },
    );
    if (chunk.bytes_received <= offset) {
      throw new Error('Upload stalled: the server confirmed no new bytes.');
    }
    offset = chunk.bytes_received;
    onProgress?.(Math.min(99, Math.round((offset / total) * 100)));
  }

  throwIfAborted();
  const fallbackTitle = file.name.replace(/\.[^.]+$/, '') || file.name;
  const done = await apiClient<UploadCompleteOut>(
    `/uploads/${encodeURIComponent(uploadId)}/complete`,
    {
      method: 'POST',
      headers: { ...mutationHeaders() },
      body: JSON.stringify({
        title: input.title.trim() || fallbackTitle,
        artist: input.artist.trim() || null,
      }),
      signal,
    },
  );
  onProgress?.(100);
  return { mixId: done.mix_id, uploadId };
}

async function abortUploadSession(uploadId: string | null): Promise<void> {
  if (!uploadId) return;
  try {
    await apiClient<void>(`/uploads/${encodeURIComponent(uploadId)}`, {
      method: 'DELETE',
      headers: { ...mutationHeaders() },
    });
  } catch {
    // Abort is best-effort: the session expires server-side on its own.
  }
}

export interface UseUploadResult {
  status: UploadStatus;
  fileName: string | null;
  fileSize: number | null;
  progress: number;
  mixId: string | null;
  error: string | null;
  liveMessage: string;
  title: string;
  artist: string;
  validationError: string | null;
  setTitle: (value: string) => void;
  setArtist: (value: string) => void;
  selectFile: (file: File | null) => void;
  clearSelection: () => void;
  start: () => void;
  cancel: () => void;
  reset: () => void;
  retry: () => void;
}

/** Reducer-backed upload machine with exactly one primary action per state. */
export function useUpload(): UseUploadResult {
  const [state, dispatch] = useReducer(processReducer, initialProcessState);
  const [title, setTitle] = useReducer((_prev: string, next: string) => next, '');
  const [artist, setArtist] = useReducer((_prev: string, next: string) => next, '');
  const [validationError, setValidationError] = useReducer(
    (_prev: string | null, next: string | null) => next,
    null as string | null,
  );
  const abortRef = useRef<AbortController | null>(null);
  const stateRef = useRef(state);
  stateRef.current = state;
  const inputRef = useRef<ProcessInput>({ title: '', artist: '' });
  inputRef.current = { title, artist };

  const selectFile = useCallback((file: File | null) => {
    if (!file) {
      setValidationError(null);
      dispatch({ type: 'CLEAR' });
      return;
    }
    const invalid = validateAudioFile(file);
    if (invalid) {
      setValidationError(invalid);
      return;
    }
    setValidationError(null);
    dispatch({ type: 'SELECT', file });
  }, []);

  const clearSelection = useCallback(() => {
    setValidationError(null);
    dispatch({ type: 'CLEAR' });
  }, []);

  const start = useCallback(() => {
    const current = stateRef.current;
    if (current.status !== 'selected' || !current.file) return;
    const file = current.file;
    const input = { ...inputRef.current };
    const controller = new AbortController();
    abortRef.current = controller;
    dispatch({ type: 'BEGIN' });
    void startUpload(file, input, {
      signal: controller.signal,
      onInit: (uploadId) => dispatch({ type: 'INIT_OK', uploadId }),
      onProgress: (percent) => {
        if (percent >= 100) return;
        dispatch({ type: 'UPLOAD_PROGRESS', percent });
      },
    })
      .then(({ mixId }) => {
        dispatch({ type: 'CHUNKS_DONE' });
        dispatch({ type: 'READY', mixId });
      })
      .catch((err: unknown) => {
        if ((err as DOMException)?.name === 'AbortError' || controller.signal.aborted) {
          // Report the server-side abort, then land the machine in ABORT.
          void abortUploadSession(stateRef.current.uploadId);
          dispatch({ type: 'ABORT' });
        } else {
          dispatch({ type: 'FAIL', message: `Upload failed: ${problemMessage(err)}` });
        }
      })
      .finally(() => {
        if (abortRef.current === controller) abortRef.current = null;
      });
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    if (!abortRef.current) {
      // No request in flight (edge: between BEGIN and first fetch resolve
      // the controller above always exists, so this is a safe fallback).
      void abortUploadSession(stateRef.current.uploadId);
      dispatch({ type: 'ABORT' });
    }
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setValidationError(null);
    dispatch({ type: 'RESET' });
  }, []);

  const retry = useCallback(() => {
    const current = stateRef.current;
    if (current.status !== 'error') return;
    if (current.file) {
      dispatch({ type: 'SELECT', file: current.file });
    } else {
      dispatch({ type: 'RESET' });
    }
  }, []);

  // Persisted mix -> hand off to the Pipeline surface scoped to the new
  // mix, where job dispatch lives. Navigation is a side effect of READY only.
  useEffect(() => {
    if (state.status === 'ready') {
      const target = pipelinePath(state.mixId ?? undefined);
      const timer = window.setTimeout(() => navigate(target), 600);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [state.status, state.mixId]);

  return {
    status: state.status,
    fileName: state.fileName,
    fileSize: state.fileSize,
    progress: state.progress,
    mixId: state.mixId,
    error: state.error,
    liveMessage: state.liveMessage,
    title,
    artist,
    validationError,
    setTitle,
    setArtist,
    selectFile,
    clearSelection,
    start,
    cancel,
    reset,
    retry,
  };
}
