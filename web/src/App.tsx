import { useEffect, useState, useRef, ChangeEvent } from "react";
import {
  Activity,
  UploadCloud,
  Music,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  PlayCircle,
  Loader2,
  XCircle,
  Gauge,
  KeyRound,
  Volume2,
  ListMusic,
  Disc,
} from "lucide-react";

interface BpmCandidate {
  bpm: number;
  confidence: number;
  support_count: number;
}

interface QualityFinding {
  type: string;
  severity: string;
  description: string;
}

interface AnalysisResult {
  primary_bpm: number;
  bpm_confidence: number;
  bpm_candidates: BpmCandidate[];
  detected_key: string;
  camelot_code: string;
  key_confidence: number;
  integrated_lufs: number;
  loudness_range_lra: number;
  true_peak_db: number;
  quality_findings: QualityFinding[];
}

interface TrackMatch {
  title: string;
  artist: string;
  album?: string;
  match_score: number;
  source: string;
}

interface TrackSegment {
  id: string;
  segment_index: number;
  start_time_seconds: number;
  end_time_seconds: number;
  duration_seconds: number;
  confidence: number;
  match?: TrackMatch;
}

interface MixItem {
  id: string;
  title: string;
  artist?: string;
  media_asset: {
    duration_seconds: number;
    sample_rate: number;
    channels: number;
    codec: string;
    file_size_bytes: number;
  };
  analysis_result?: AnalysisResult;
}

interface ActiveJobState {
  job_id: string;
  mix_id: string;
  status: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELLED";
  progress_percent: number;
  current_stage: string;
  error_message?: string;
}

const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB chunks

function App() {
  const [health, setHealth] = useState<any>(null);
  const [mixes, setMixes] = useState<MixItem[]>([]);
  const [tracklists, setTracklists] = useState<Record<string, TrackSegment[]>>({});
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadStatusText, setUploadStatusText] = useState<string>("");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [activeJobs, setActiveJobs] = useState<Record<string, ActiveJobState>>({});
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchStatusAndMixes = async () => {
    try {
      const hRes = await fetch("/api/v1/health");
      if (hRes.ok) setHealth(await hRes.json());

      const mRes = await fetch("/api/v1/mixes");
      if (mRes.ok) {
        const data = await mRes.json();
        setMixes(data.items || []);

        // Fetch tracklists for analyzed mixes
        for (const mix of data.items || []) {
          fetchMixTracklist(mix.id);
        }
      }
    } catch (err) {
      console.error("Failed fetching data", err);
    }
  };

  const fetchMixTracklist = async (mixId: string) => {
    try {
      const res = await fetch(`/api/v1/mixes/${mixId}/tracklist`);
      if (res.ok) {
        const data = await res.json();
        setTracklists((prev) => ({
          ...prev,
          [mixId]: data.tracks || [],
        }));
      }
    } catch (err) {
      console.error(`Failed to fetch tracklist for ${mixId}`, err);
    }
  };

  useEffect(() => {
    fetchStatusAndMixes();
    const timer = setInterval(fetchStatusAndMixes, 10000);
    return () => clearInterval(timer);
  }, []);

  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadError(null);
    setUploadProgress(0);
    setUploadStatusText("Initializing upload session...");

    try {
      const initRes = await fetch("/api/v1/uploads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: file.name,
          total_bytes: file.size,
          chunk_size: CHUNK_SIZE,
        }),
      });

      if (!initRes.ok) {
        const err = await initRes.json();
        throw new Error(err.detail || "Failed to initialize upload session");
      }

      const { upload_id } = await initRes.json();
      const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
      let offset = 0;

      for (let chunkIdx = 0; chunkIdx < totalChunks; chunkIdx++) {
        const chunk = file.slice(offset, offset + CHUNK_SIZE);
        setUploadStatusText(`Uploading chunk ${chunkIdx + 1} of ${totalChunks}...`);

        const chunkRes = await fetch(`/api/v1/uploads/${upload_id}/chunks`, {
          method: "POST",
          headers: {
            "Content-Type": "application/octet-stream",
            "X-Chunk-Index": chunkIdx.toString(),
            "X-Offset-Bytes": offset.toString(),
          },
          body: chunk,
        });

        if (!chunkRes.ok) {
          throw new Error(`Upload chunk ${chunkIdx} failed`);
        }

        setUploadProgress(Math.round(((chunkIdx + 1) / totalChunks) * 90));
        offset += chunk.size;
      }

      setUploadStatusText("Probing audio stream with ffprobe...");
      const completeRes = await fetch(`/api/v1/uploads/${upload_id}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: file.name.replace(/\.[^/.]+$/, ""),
        }),
      });

      if (!completeRes.ok) {
        const err = await completeRes.json();
        throw new Error(err.detail || "Failed to finalize audio analysis");
      }

      setUploadStatusText("Upload complete!");
      setUploadProgress(100);
      setTimeout(() => {
        setUploadProgress(null);
        setUploadStatusText("");
        if (fileInputRef.current) fileInputRef.current.value = "";
        fetchStatusAndMixes();
      }, 1200);
    } catch (err: any) {
      setUploadError(err.message || "Upload failed");
      setUploadProgress(null);
      setUploadStatusText("");
    }
  };

  const startAnalysisJob = async (mixId: string) => {
    try {
      const res = await fetch(`/api/v1/mixes/${mixId}/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_type: "ANALYSIS" }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to start analysis job");
      }

      const jobData = await res.json();
      const jobId = jobData.id;

      setActiveJobs((prev) => ({
        ...prev,
        [mixId]: {
          job_id: jobId,
          mix_id: mixId,
          status: "QUEUED",
          progress_percent: 0,
          current_stage: "Queued",
        },
      }));

      const evtSource = new EventSource(`/api/v1/jobs/${jobId}/events`);

      evtSource.addEventListener("update", (event) => {
        const data = JSON.parse(event.data);
        setActiveJobs((prev) => ({
          ...prev,
          [mixId]: {
            job_id: jobId,
            mix_id: mixId,
            status: data.status,
            progress_percent: data.progress_percent || 0,
            current_stage: data.current_stage || "",
            error_message: data.error_message,
          },
        }));

        if (data.status === "SUCCEEDED") {
          fetchStatusAndMixes();
        }
      });

      evtSource.addEventListener("close", () => {
        evtSource.close();
      });

      evtSource.onerror = () => {
        evtSource.close();
      };
    } catch (err: any) {
      alert(`Error starting analysis: ${err.message}`);
    }
  };

  const cancelJob = async (jobId: string, mixId: string) => {
    try {
      await fetch(`/api/v1/jobs/${jobId}/cancel`, { method: "POST" });
      setActiveJobs((prev) => ({
        ...prev,
        [mixId]: {
          ...prev[mixId],
          status: "CANCELLED",
          current_stage: "Cancelled",
        },
      }));
    } catch (err) {
      console.error("Failed to cancel job", err);
    }
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const formatSize = (bytes: number) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/40 backdrop-blur px-6 py-4 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/20">
            MA
          </div>
          <div>
            <h1 className="font-bold text-lg tracking-tight">Mix Analyst</h1>
            <p className="text-xs text-slate-400">Continuous DJ Mix Intelligence & Audio Pipeline</p>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800/80 border border-slate-700/50">
            <span
              className={`w-2 h-2 rounded-full ${
                health?.status === "ok" ? "bg-emerald-500 animate-pulse" : "bg-rose-500"
              }`}
            />
            <span className="text-slate-300">
              {health?.status === "ok" ? "Platform Online" : "Connecting..."}
            </span>
          </div>

          <button
            onClick={fetchStatusAndMixes}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
            title="Refresh State"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-6xl w-full mx-auto p-6 space-y-6">
        {/* Upload Section */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-4">
          <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
            <UploadCloud className="w-5 h-5 text-indigo-400" />
            Resumable Ingestion & Storage
          </h2>
          <p className="text-sm text-slate-400">
            Stream full DJ recordings (WAV, FLAC, MP3) in 5MB chunks. Validated with ffprobe and registered in PostgreSQL.
          </p>

          <div className="flex items-center gap-4">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept="audio/*"
              className="hidden"
              id="mix-file-input"
            />
            <label
              htmlFor="mix-file-input"
              className="cursor-pointer px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition shadow-md shadow-indigo-600/20 inline-flex items-center gap-2"
            >
              <UploadCloud className="w-4 h-4" />
              Upload DJ Mix File
            </label>
          </div>

          {/* Upload Progress Bar */}
          {uploadProgress !== null && (
            <div className="space-y-2 pt-2">
              <div className="flex justify-between text-xs text-slate-400">
                <span>{uploadStatusText}</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-indigo-500 h-full transition-all duration-200"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {uploadError && (
            <div className="flex items-center gap-2 text-rose-400 text-xs bg-rose-950/40 border border-rose-900/50 p-3 rounded-lg">
              <AlertCircle className="w-4 h-4" />
              <span>{uploadError}</span>
            </div>
          )}
        </div>

        {/* Mixes List with Real-time Job Queue & Analysis Card */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-4">
          <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
            <Music className="w-5 h-5 text-emerald-400" />
            Analyzed Mixes & Pipeline Queue ({mixes.length})
          </h2>

          {mixes.length === 0 ? (
            <div className="py-8 text-center text-slate-500 text-sm">
              No mixes uploaded yet. Upload a DJ set above to run analysis.
            </div>
          ) : (
            <div className="divide-y divide-slate-800">
              {mixes.map((mix) => {
                const activeJob = activeJobs[mix.id];
                const analysis = mix.analysis_result;
                const tracklist = tracklists[mix.id] || [];

                return (
                  <div key={mix.id} className="py-4 space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-slate-200">{mix.title}</span>
                          <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 uppercase">
                            {mix.media_asset.codec}
                          </span>
                        </div>
                        <div className="text-xs text-slate-400 flex items-center gap-4">
                          <span>Duration: {formatDuration(mix.media_asset.duration_seconds)}</span>
                          <span>Rate: {mix.media_asset.sample_rate} Hz</span>
                          <span>Channels: {mix.media_asset.channels}</span>
                          <span>Size: {formatSize(mix.media_asset.file_size_bytes)}</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        {!activeJob || activeJob.status === "SUCCEEDED" || activeJob.status === "CANCELLED" || activeJob.status === "FAILED" ? (
                          <button
                            onClick={() => startAnalysisJob(mix.id)}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition"
                          >
                            <PlayCircle className="w-3.5 h-3.5" />
                            {analysis ? "Re-Analyze" : "Start Analysis Pipeline"}
                          </button>
                        ) : (
                          <button
                            onClick={() => cancelJob(activeJob.job_id, mix.id)}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-900/60 hover:bg-rose-800 text-rose-200 border border-rose-800 rounded-lg text-xs font-semibold transition"
                          >
                            <XCircle className="w-3.5 h-3.5" />
                            Cancel
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Active Job Progress Bar */}
                    {activeJob && activeJob.status === "RUNNING" && (
                      <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-3 space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-2">
                            <Loader2 className="w-3.5 h-3.5 text-indigo-400 animate-spin" />
                            <span className="text-slate-300 font-medium">Stage: {activeJob.current_stage}</span>
                          </div>
                          <span className="text-slate-400">{activeJob.progress_percent}%</span>
                        </div>
                        <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                          <div
                            className="bg-indigo-500 h-full transition-all duration-300"
                            style={{ width: `${activeJob.progress_percent}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {/* Analysis Result Card (Phase 3) */}
                    {analysis && (
                      <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-4 grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                        {/* BPM & Tempo Map */}
                        <div className="space-y-1.5 bg-slate-900/40 p-3 rounded-md border border-slate-800/50">
                          <div className="flex items-center gap-1.5 text-indigo-400 font-medium">
                            <Gauge className="w-4 h-4" />
                            <span>Tempo & BPM</span>
                          </div>
                          <div className="text-xl font-bold text-slate-100">
                            {analysis.primary_bpm} <span className="text-xs font-normal text-slate-400">BPM</span>
                          </div>
                          <div className="text-slate-400">
                            Confidence: {(analysis.bpm_confidence * 100).toFixed(0)}%
                          </div>
                        </div>

                        {/* Harmonic Key & Camelot */}
                        <div className="space-y-1.5 bg-slate-900/40 p-3 rounded-md border border-slate-800/50">
                          <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
                            <KeyRound className="w-4 h-4" />
                            <span>Harmonic Key</span>
                          </div>
                          <div className="text-xl font-bold text-slate-100 flex items-center gap-2">
                            <span>{analysis.detected_key}</span>
                            <span className="text-xs bg-emerald-950 text-emerald-400 border border-emerald-800 px-1.5 py-0.5 rounded font-mono">
                              {analysis.camelot_code}
                            </span>
                          </div>
                          <div className="text-slate-400">
                            Confidence: {(analysis.key_confidence * 100).toFixed(0)}%
                          </div>
                        </div>

                        {/* Loudness & Dynamics */}
                        <div className="space-y-1.5 bg-slate-900/40 p-3 rounded-md border border-slate-800/50">
                          <div className="flex items-center gap-1.5 text-amber-400 font-medium">
                            <Volume2 className="w-4 h-4" />
                            <span>Loudness (EBU R128)</span>
                          </div>
                          <div className="text-slate-200">
                            Integrated: <span className="font-bold text-slate-100">{analysis.integrated_lufs}</span> LUFS
                          </div>
                          <div className="text-slate-400 flex justify-between">
                            <span>True Peak: {analysis.true_peak_db} dBTP</span>
                            <span>LRA: {analysis.loudness_range_lra} LU</span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Detected Tracklist & Fingerprints (Phase 4) */}
                    {tracklist.length > 0 && (
                      <div className="bg-slate-950/40 border border-slate-800/60 rounded-lg p-4 space-y-3">
                        <div className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-2 font-medium text-slate-300">
                            <ListMusic className="w-4 h-4 text-indigo-400" />
                            <span>Detected Track Segments ({tracklist.length})</span>
                          </div>
                          <span className="text-slate-500">
                            Acoustic Fingerprints Extracted
                          </span>
                        </div>

                        <div className="divide-y divide-slate-800/60">
                          {tracklist.map((track) => (
                            <div key={track.id} className="py-2.5 flex items-center justify-between text-xs">
                              <div className="flex items-center gap-3">
                                <span className="w-6 font-mono text-slate-500 text-center font-bold">
                                  #{track.segment_index}
                                </span>
                                <Disc className="w-4 h-4 text-slate-500" />
                                <div>
                                  <div className="font-medium text-slate-200">
                                    {track.match ? `${track.match.artist} - ${track.match.title}` : `Segment ${track.segment_index}`}
                                  </div>
                                  <div className="text-slate-500 text-[11px]">
                                    {formatDuration(track.start_time_seconds)} – {formatDuration(track.end_time_seconds)} ({formatDuration(track.duration_seconds)})
                                  </div>
                                </div>
                              </div>

                              <div className="flex items-center gap-2">
                                <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-400">
                                  Confidence {(track.confidence * 100).toFixed(0)}%
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
