/**
 * Reducer-first upload state machine (Task 3).
 *
 * States: idle -> selected -> initializing -> uploading -> finalizing
 *          -> ready | error | aborted. Exactly one primary action is rendered
 * per state by ProcessPage; this module owns transitions only.
 */

export type UploadStatus =
  | 'idle'
  | 'selected'
  | 'initializing'
  | 'uploading'
  | 'finalizing'
  | 'ready'
  | 'error'
  | 'aborted';

export interface ProcessState {
  status: UploadStatus;
  file: File | null;
  fileName: string | null;
  fileSize: number | null;
  progress: number;
  uploadId: string | null;
  mixId: string | null;
  error: string | null;
  /** Last meaningful transition, announced through the live region. */
  liveMessage: string;
}

export type UploadEvent =
  | { type: 'SELECT'; file: File }
  | { type: 'CLEAR' }
  | { type: 'BEGIN' }
  | { type: 'INIT_OK'; uploadId: string }
  | { type: 'UPLOAD_PROGRESS'; percent: number }
  | { type: 'CHUNKS_DONE' }
  | { type: 'READY'; mixId: string }
  | { type: 'FAIL'; message: string }
  | { type: 'ABORT' }
  | { type: 'RESET' };

export const initialProcessState: ProcessState = {
  status: 'idle',
  file: null,
  fileName: null,
  fileSize: null,
  progress: 0,
  uploadId: null,
  mixId: null,
  error: null,
  liveMessage: 'Process audio. Choose an audio file to begin.',
};

function failMessage(message: string): Pick<ProcessState, 'error' | 'liveMessage'> {
  return { error: message, liveMessage: `Upload failed. ${message}` };
}

export function processReducer(state: ProcessState, event: UploadEvent): ProcessState {
  switch (event.type) {
    case 'SELECT':
      return {
        ...state,
        status: 'selected',
        file: event.file,
        fileName: event.file.name,
        fileSize: event.file.size,
        progress: 0,
        uploadId: null,
        mixId: null,
        error: null,
        liveMessage: `Ready to process ${event.file.name}.`,
      };
    case 'CLEAR':
      return {
        ...initialProcessState,
        liveMessage: 'Selection cleared. Choose an audio file to begin.',
      };
    case 'BEGIN':
      if (state.status !== 'selected' || !state.file) return state;
      return {
        ...state,
        status: 'initializing',
        progress: 0,
        error: null,
        liveMessage: 'Initializing upload session.',
      };
    case 'INIT_OK':
      if (state.status !== 'initializing') return state;
      return {
        ...state,
        status: 'uploading',
        uploadId: event.uploadId,
        progress: 0,
        liveMessage: 'Uploading audio in 5 megabyte chunks.',
      };
    case 'UPLOAD_PROGRESS':
      if (state.status !== 'uploading') return state;
      return { ...state, progress: event.percent };
    case 'CHUNKS_DONE':
      if (state.status !== 'uploading') return state;
      return {
        ...state,
        status: 'finalizing',
        progress: 100,
        liveMessage: 'Finalizing upload and validating audio.',
      };
    case 'READY':
      if (state.status !== 'finalizing' && state.status !== 'uploading') return state;
      return {
        ...state,
        status: 'ready',
        progress: 100,
        mixId: event.mixId,
        error: null,
        liveMessage: 'Upload complete. Continuing to Pipeline and Broadcast.',
      };
    case 'FAIL':
      if (state.status === 'ready' || state.status === 'idle') return state;
      return { ...state, status: 'error', ...failMessage(event.message) };
    case 'ABORT':
      if (
        state.status !== 'initializing' &&
        state.status !== 'uploading' &&
        state.status !== 'finalizing'
      ) {
        return state;
      }
      return {
        ...state,
        status: 'aborted',
        error: null,
        liveMessage: 'Upload cancelled.',
      };
    case 'RESET':
      return {
        ...initialProcessState,
        liveMessage: 'Process audio. Choose an audio file to begin.',
      };
    default:
      return state;
  }
}
