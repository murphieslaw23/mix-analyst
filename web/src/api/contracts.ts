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

export interface MasteringReport { integrated_lufs: number | null; true_peak_dbtp: number | null; }
export interface ApiProblem { status: number; title: string; detail: string; retryable: boolean; }
