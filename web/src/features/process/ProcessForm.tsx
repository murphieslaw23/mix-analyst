import { useId } from "react";
import { Button } from "../../components/ui/Button";
import { LiveRegion } from "../../components/ui/LiveRegion";
import type { MasteringPresetId, ProcessSettings, ProcessUploadModel } from "./types";
import { presetOptions } from "./types";

interface ProcessFormProps {
  settings: ProcessSettings;
  state: ProcessUploadModel;
  onFileSelected(file: File | null): void;
  onPresetChange(presetId: MasteringPresetId): void;
  onStart(): void;
  onCancel(): void;
  onReset(): void;
}

function announce(state: ProcessUploadModel) {
  if (state.jobId) return "Mastering job created. Opening its progress.";
  if (state.status === "ready" && state.mixId) return "Audio is saved. Creating your mastering job.";
  if (state.status === "ready") return "Ready to process";
  if (state.status === "initializing") return "Creating secure upload session.";
  // The semantic progress element continuously exposes its numeric value.
  // Keep the live region for state changes only so assistive tech is not
  // interrupted once per chunk.
  if (state.status === "uploading") return "Uploading audio.";
  if (state.status === "finalizing") return state.stage === "queueing" ? "Creating mastering job." : "Validating and saving your audio.";
  if (state.status === "aborted") return state.mixId ? "Mastering request cancelled. You can try again when ready." : "Upload paused. You can resume it when ready.";
  if (state.status === "error") return state.problem?.detail ?? "The process could not continue.";
  return "";
}

export function ProcessForm({ settings, state, onFileSelected, onPresetChange, onStart, onCancel, onReset }: ProcessFormProps) {
  const inputId = useId();
  const presetId = useId();
  const busy = state.status === "initializing" || state.status === "uploading" || state.status === "finalizing";
  const ready = state.status === "ready" && !state.mixId;
  const canRetry = state.status === "error" || state.status === "aborted";
  const hasSelectedFile = state.file !== null;

  return (
    <form className="process-form" onSubmit={(event) => { event.preventDefault(); if (ready || canRetry) onStart(); }}>
      <div className="process-form__field">
        <label className="process-form__label" htmlFor={inputId}>Choose audio</label>
        <input
          accept="audio/wav,audio/x-wav,audio/aiff,audio/x-aiff,audio/flac,audio/mpeg,.wav,.aiff,.aif,.flac,.mp3"
          className="process-form__file"
          disabled={busy}
          id={inputId}
          onChange={(event) => onFileSelected(event.currentTarget.files?.item(0) ?? null)}
          type="file"
        />
        <p className="process-form__hint">WAV, AIFF, FLAC, or MP3. Your file stays private until you start mastering.</p>
        {hasSelectedFile ? <p className="process-form__file-name"><span>Selected</span> {state.file?.name}</p> : null}
      </div>

      <fieldset className="process-form__field" disabled={busy || !hasSelectedFile}>
        <legend className="process-form__label">Mastering preset</legend>
        <label className="process-form__select-label" htmlFor={presetId}>Choose mastering character</label>
        <select id={presetId} onChange={(event) => onPresetChange(event.target.value as MasteringPresetId)} value={settings.presetId}>
          {presetOptions.map((preset) => <option key={preset.id} value={preset.id}>{preset.label}</option>)}
        </select>
        <p className="process-form__hint">{presetOptions.find((preset) => preset.id === settings.presetId)?.description}</p>
      </fieldset>

      {busy ? (
        <div className="process-form__progress" aria-describedby="upload-progress-detail">
          <div className="process-form__progress-label"><span>{state.stage === "queueing" ? "Starting mastering" : state.stage === "finalizing" ? "Saving audio" : "Uploading audio"}</span><span>{Math.round(state.progressPercent)}%</span></div>
          <progress aria-label="Upload progress" max={100} value={state.progressPercent} />
          <p id="upload-progress-detail">Keep this page open while your audio is secured.</p>
        </div>
      ) : null}

      {state.status === "error" && state.problem ? <p className="process-form__problem" role="alert"><strong>{state.problem.title}</strong> {state.problem.detail}</p> : null}
      <LiveRegion className="process-form__live">{announce(state)}</LiveRegion>

      <div className="process-form__actions">
        {!hasSelectedFile ? null : ready ? <Button type="submit">Start mastering</Button> : null}
        {canRetry ? <Button type="submit">{state.mixId ? "Create mastering job" : state.session ? "Resume upload" : "Try again"}</Button> : null}
        {busy ? <Button onClick={onCancel} tone="secondary">{state.stage === "queueing" ? "Cancel request" : "Cancel upload"}</Button> : null}
        {(state.status === "error" || state.status === "aborted") ? <Button onClick={onReset} tone="quiet">Choose another file</Button> : null}
      </div>
    </form>
  );
}
