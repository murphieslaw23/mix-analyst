import type {
  AnalysisResultDto,
  ArtifactDto,
  MixDto,
  MixListDto,
  TrackDto,
  TransitionDto,
} from "./contracts";

export interface LibraryMixSummary {
  id: string;
  title: string;
  artist: string | null;
  status: string;
  createdAt: string;
  updatedAt: string;
  durationSeconds: number;
  sourceFilename: string;
  suggestedDownloadName: string | null;
}

export interface MixDetail extends LibraryMixSummary {
  artifacts: ArtifactDto[];
  analysisResult: AnalysisResultDto | null;
}

export interface AnalysisSummary {
  bpm: number;
  key: string;
  camelotCode: string;
  integratedLufs: number;
  truePeakDb: number;
}

export interface TrackSummary {
  id: string;
  index: number;
  startSeconds: number;
  endSeconds: number;
  confidence: number;
}

export interface TransitionSummary {
  id: string;
  index: number;
  startSeconds: number;
  endSeconds: number;
  type: string;
  confidence: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isArtifactDto(value: unknown): value is ArtifactDto {
  return isRecord(value)
    && typeof value.id === "string"
    && typeof value.role === "string"
    && typeof value.key === "string"
    && typeof value.sha256 === "string"
    && typeof value.algorithm_version === "string"
    && typeof value.media_type === "string"
    && typeof value.byte_length === "number"
    && typeof value.download_url === "string"
    && typeof value.created_at === "string";
}

export function isMixDto(value: unknown): value is MixDto {
  return isRecord(value)
    && typeof value.id === "string"
    && typeof value.title === "string"
    && typeof value.status === "string"
    && typeof value.created_at === "string"
    && typeof value.updated_at === "string"
    && isRecord(value.media_asset)
    && typeof value.media_asset.original_filename === "string"
    && typeof value.media_asset.duration_seconds === "number"
    && Array.isArray(value.artifacts)
    && value.artifacts.every(isArtifactDto);
}

/** Validates a detail response before playback can use its protected URLs. */
export function asMixDto(value: unknown): MixDto {
  if (!isMixDto(value)) throw new TypeError("The mix response did not match the expected contract.");
  return value;
}

/** Validates the public list envelope before any feature receives it. */
export function asMixListDto(value: unknown): MixListDto {
  if (!isRecord(value) || !Array.isArray(value.items) || typeof value.total !== "number" || !Number.isInteger(value.total) || value.total < 0 || !value.items.every(isMixDto)) {
    throw new TypeError("The mixes response did not match the expected paginated contract.");
  }
  return value as unknown as MixListDto;
}

export function toLibraryMixSummary(mix: MixDto): LibraryMixSummary {
  return {
    id: mix.id,
    title: mix.title,
    artist: mix.artist,
    status: mix.status,
    createdAt: mix.created_at,
    updatedAt: mix.updated_at,
    durationSeconds: mix.media_asset.duration_seconds,
    sourceFilename: mix.media_asset.original_filename,
    suggestedDownloadName: mix.suggested_download_name,
  };
}

export function toLibraryMixSummaries(response: MixListDto): LibraryMixSummary[] {
  return response.items
    .filter((mix) => mix.artifacts.some((artifact) => artifact.role === "mastered"))
    .map(toLibraryMixSummary);
}

export function toMixDetail(mix: MixDto): MixDetail {
  return { ...toLibraryMixSummary(mix), artifacts: mix.artifacts, analysisResult: mix.analysis_result };
}

export function toAnalysisSummary(analysis: AnalysisResultDto): AnalysisSummary {
  return {
    bpm: analysis.primary_bpm,
    key: analysis.detected_key,
    camelotCode: analysis.camelot_code,
    integratedLufs: analysis.integrated_lufs,
    truePeakDb: analysis.true_peak_db,
  };
}

export function toTrackSummary(track: TrackDto): TrackSummary {
  return { id: track.id, index: track.segment_index, startSeconds: track.start_time_seconds, endSeconds: track.end_time_seconds, confidence: track.confidence };
}

export function toTransitionSummary(transition: TransitionDto): TransitionSummary {
  return { id: transition.id, index: transition.transition_index, startSeconds: transition.start_time_seconds, endSeconds: transition.end_time_seconds, type: transition.transition_type, confidence: transition.confidence };
}

export function toArtifacts(artifacts: ArtifactDto[]): ArtifactDto[] {
  return artifacts.map((artifact) => ({ ...artifact }));
}
