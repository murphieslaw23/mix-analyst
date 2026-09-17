/**
 * Backend DTO -> view-model adapters (moved from App.tsx, Task 2).
 * App.tsx imports these so existing behavior is unchanged.
 */
import type {
  AnalysisSummary,
  MixDetail,
  MixListItem,
} from '../types';

// Backend contracts: GET /mixes returns {total, items[]} with nested
// media_asset/analysis_result, GET /mixes/{id} returns the same field names
// flattened (see api/app/schemas/mix.py MixDetailOut). E2E fixtures and
// older payloads may already be flat arrays — accept every known shape.
export const normalizeMixListItem = (raw: any): MixListItem => ({
  id: raw.id,
  original_filename: raw.original_filename ?? raw.media_asset?.original_filename ?? 'unknown-mix',
  title: raw.title,
  duration_seconds: raw.duration_seconds ?? raw.media_asset?.duration_seconds,
  bpm: raw.bpm ?? raw.analysis_result?.primary_bpm,
});

export const normalizeMixDetail = (raw: any): MixDetail => ({
  ...normalizeMixListItem(raw),
  audio_url: raw.audio_url ?? raw.audio,
  tracks: (raw.tracks ?? []).map((t: any) => ({
    id: t.id,
    title: t.title ?? t.name,
    artist: t.artist,
    start_time: t.start_time ?? t.start_time_seconds ?? 0,
    end_time: t.end_time ?? t.end_time_seconds,
    bpm: t.bpm,
    camelot_key: t.camelot_key,
  })),
  transitions: (raw.transitions ?? []).map((tr: any) => ({
    id: tr.id,
    start_time: tr.start_time ?? tr.start_time_seconds ?? 0,
    end_time: tr.end_time ?? tr.end_time_seconds,
    transition_type: tr.transition_type,
    from_key: tr.from_key,
    to_key: tr.to_key,
    harmonic_compatibility: tr.harmonic_compatibility ?? tr.camelot_compatibility,
    confidence: tr.confidence,
  })),
});

export const normalizeAnalysis = (raw: any): AnalysisSummary => ({
  primary_bpm: raw.primary_bpm,
  bpm_confidence: raw.bpm_confidence,
  bpm_candidates: (raw.bpm_candidates ?? []).map((c: any) => ({
    bpm: c.bpm,
    confidence: c.confidence,
    support_count: c.support_count ?? 0,
  })),
  detected_key: raw.detected_key,
  camelot_code: raw.camelot_code,
  key_confidence: raw.key_confidence,
  integrated_lufs: raw.integrated_lufs,
  loudness_range_lra: raw.loudness_range_lra,
  true_peak_db: raw.true_peak_db,
  quality_findings: (raw.quality_findings ?? []).map((q: any) => ({
    type: q.type,
    severity: q.severity,
    description: q.description,
    timestamp_range: q.timestamp_range ?? null,
  })),
});
