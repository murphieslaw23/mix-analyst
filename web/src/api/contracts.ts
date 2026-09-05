/** Browser-side contracts mirror the public API response models. */
export interface MediaAssetDto {
  id: string;
  original_filename: string;
  file_size_bytes: number;
  sha256_hash: string;
  duration_seconds: number;
  sample_rate: number;
  channels: number;
  codec: string;
  bit_rate: number | null;
  format_name: string | null;
  created_at: string;
}

export interface AnalysisResultDto {
  id: string;
  mix_id: string;
  media_asset_id: string;
  primary_bpm: number;
  bpm_confidence: number;
  detected_key: string;
  camelot_code: string;
  key_confidence: number;
  integrated_lufs: number;
  loudness_range_lra: number;
  true_peak_db: number;
  created_at: string;
}

export interface ArtifactDto {
  id: string;
  role: string;
  key: string;
  sha256: string;
  algorithm_version: string;
  media_type: string;
  byte_length: number;
  report: Record<string, unknown> | null;
  download_url: string;
  created_at: string;
}

export interface MixDto {
  id: string;
  title: string;
  artist: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  media_asset: MediaAssetDto;
  analysis_result: AnalysisResultDto | null;
  artifacts: ArtifactDto[];
  suggested_download_name: string | null;
}

/** The public `/mixes` response is an envelope, never an array. */
export interface MixListDto {
  items: MixDto[];
  total: number;
}

/** Backwards-compatible spelling while feature code migrates to `*Dto`. */
export type MixOut = MixDto;
export type MixListResponse = MixListDto;

export interface TrackDto {
  id: string;
  mix_id: string;
  segment_index: number;
  start_time_seconds: number;
  end_time_seconds: number;
  duration_seconds: number;
  confidence: number;
}

export interface TracklistResponse { mix_id: string; total_tracks: number; identified_tracks: number; tracks: TrackDto[]; }

export interface TransitionDto {
  id: string;
  mix_id: string;
  transition_index: number;
  start_time_seconds: number;
  end_time_seconds: number;
  cue_in_time: number;
  cue_out_time: number;
  transition_type: string;
  energy_delta: number;
  tempo_shift_bpm: number;
  camelot_compatibility: string;
  confidence: number;
}

export interface TransitionListResponse { mix_id: string; total_transitions: number; transitions: TransitionDto[]; }

export interface ApiProblem { status: number; title: string; detail: string; retryable: boolean; }

export interface UploadSessionDto {
  upload_id: string;
  upload_url: string;
  filename: string;
  total_size_bytes: number;
  chunk_size: number;
  offset: number;
  expires_at: string;
  status: string;
}

/**
 * `GET /:upload_id` deliberately exposes only the server-authoritative
 * progress/status fields.  It is not interchangeable with the init response:
 * the browser retains the accepted chunk size and same-origin upload URL from
 * the original POST while it resumes a selected local file.
 */
export interface UploadStatusDto {
  upload_id: string;
  filename: string;
  total_size_bytes: number;
  bytes_received: number;
  offset: number;
  progress_percent: number;
  status: string;
  expires_at: string;
  created_at: string;
  updated_at: string;
}

export interface UploadChunkDto {
  upload_id: string;
  bytes_received: number;
  offset: number;
  total_size_bytes: number;
  progress_percent: number;
  status: string;
}

export interface UploadCompleteDto {
  mix_id: string;
  media_asset_id: string;
  title: string;
  artist: string | null;
  duration_seconds: number;
  sample_rate: number;
  channels: number;
  codec: string;
  sha256_hash: string;
  status: string;
}

export interface JobDto {
  id: string;
  mix_id: string;
  job_type: string;
  status: string;
  progress_percent: number;
  current_stage: string | null;
  parameters: Record<string, unknown>;
  celery_task_id: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  stage_runs: StageRunDto[];
  attempts: JobAttemptDto[];
}

export interface StageRunDto {
  id: string;
  stage_name: string;
  stage_version: string;
  status: string;
  progress_percent: number;
  stage_output: string | null;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface JobAttemptDto {
  id: string;
  attempt_number: number;
  status: string;
  worker_hostname: string | null;
  started_at: string;
  finished_at: string | null;
}

/** A project-scoped jobs snapshot. Follow only the server-issued cursor. */
export interface JobListDto {
  items: JobDto[];
  total: number;
  next_cursor: string | null;
}
