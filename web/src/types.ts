export interface TrackCue {
  id?: string;
  title?: string;
  artist?: string;
  start_time: number;
  end_time?: number;
  bpm?: number;
  camelot_key?: string;
}

export interface TransitionZone {
  id?: string;
  start_time: number;
  end_time?: number;
  transition_type?: string;
  from_key?: string;
  to_key?: string;
  harmonic_compatibility?: string;
  confidence?: number;
}

export interface QualityFinding {
  type: string;
  severity: string;
  description: string;
  timestamp_range?: number[] | null;
}

export interface BpmCandidate {
  bpm: number;
  confidence: number;
  support_count: number;
}

export interface AnalysisSummary {
  primary_bpm?: number;
  bpm_confidence?: number;
  bpm_candidates?: BpmCandidate[];
  detected_key?: string;
  camelot_code?: string;
  key_confidence?: number;
  integrated_lufs?: number;
  loudness_range_lra?: number;
  true_peak_db?: number;
  quality_findings?: QualityFinding[];
}

export interface MixListItem {
  id: string;
  original_filename: string;
  title?: string;
  duration_seconds?: number;
  bpm?: number;
}

export interface MixDetail extends MixListItem {
  audio_url?: string;
  tracks?: TrackCue[];
  transitions?: TransitionZone[];
}

export type RegionSelection =
  | { kind: 'track' | 'transition' | 'quality'; id: string }
  | null;

export interface ZoomWindow {
  /** Visible window as fractions of total duration (0..1). */
  start: number;
  end: number;
}
