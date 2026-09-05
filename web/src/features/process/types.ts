import type { ApiProblem, UploadSessionDto } from "../../api/contracts";

export type UploadState = "idle" | "selected" | "initializing" | "uploading" | "finalizing" | "ready" | "error" | "aborted";

export type MasteringPresetId = "sound_system_heavy" | "club_broadcast" | "vinyl_premaster";

export interface ProcessSettings {
  presetId: MasteringPresetId;
}

export interface ProcessUploadModel {
  status: UploadState;
  file: File | null;
  session: UploadSessionDto | null;
  mixId: string | null;
  progressPercent: number;
  stage: "selection" | "upload" | "finalizing" | "queueing" | null;
  problem: ApiProblem | null;
}

export const allowedAudioExtensions = [".wav", ".aiff", ".aif", ".flac", ".mp3"] as const;

export const presetOptions: ReadonlyArray<{ id: MasteringPresetId; label: string; description: string }> = [
  { id: "sound_system_heavy", label: "Sound System Heavy", description: "Weight-forward master for a sound-system playback." },
  { id: "club_broadcast", label: "Club Broadcast", description: "Balanced loudness for club and stream playback." },
  { id: "vinyl_premaster", label: "Vinyl Pre-Master", description: "More headroom for a vinyl-cut workflow." },
];
