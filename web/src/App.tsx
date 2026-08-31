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

interface MixItem {
  id: string;
  title: string;
  artist: string | null;
  status: string;
  created_at: string;
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
  const [apiStatus, setApiStatus] = useState<string>("checking...");
  const [mixes, setMixes] = useState<MixItem[]>([]);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadStatusText, setUploadStatusText] = useState<string>("");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [activeJobs, setActiveJobs] = useState<Record<string, ActiveJobState>>({});
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchStatusAndMixes = async () => {
    try {
      const healthRes = await fetch("/api/v1/health/ready");
      const healthData = await healthRes.json();
      setApiStatus(healthData.status || "unknown");

      const mixesRes = await fetch("/api/v1/mixes");
      if (mixesRes.ok) {
        const mixesData = await mixesRes.json();
        setMixes(mixesData.items || []);
      }
    } catch {
      setApiStatus("unreachable");
    }
  };

  useEffect(() => {
    fetchStatusAndMixes();
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
          total_size_bytes: file.size,
          chunk_size: CHUNK_SIZE,
        }),
      });

      if (!initRes.ok) {
        const err = await initRes.json();
        throw new Error(err.detail || "Failed to initialize upload");
      }

      const { upload_id } = await initRes.json();
      const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
      let offset = 0;

      for (let i = 0; i < totalChunks; i++) {
        const chunk = file.slice(offset, offset + CHUNK_SIZE);
        const formData = new FormData();
        formData.append("file", chunk, file.name);
        formData.append("offset", offset.toString());

        setUploadStatusText(`Uploading chunk ${i + 1} of ${totalChunks}...`);

        const chunkRes = await fetch(`/api/v1/uploads/${upload_id}`, {
          method: "PATCH",
          body: formData,
        });

        if (!chunkRes.ok) {
          const err = await chunkRes.json();
          throw new Error(err.detail || `Failed to upload chunk ${i + 1}`);
        }

        const chunkData = await chunkRes.json();
        setUploadProgress(chunkData.progress_percent);
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
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-12">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="w-8 h-8 text-emerald-400" />
            <div>
              <h1 className="text-2xl font-bold">Mix Analyst</h1>
              <p className="text-xs text-slate-400">Continuous DJ Mix & Recording Analyzer</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={fetchStatusAndMixes}
              className="p-2 text-slate-400 hover:text-slate-200 bg-slate-900 border border-slate-800 rounded-lg"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg text-sm">
              <div
                className={`w-2.5 h-2.5 rounded-full ${
                  apiStatus === "ok" ? "bg-emerald-400" : "bg-amber-400"
                }`}
              />
              <span className="text-slate-300 capitalize">{apiStatus}</span>
            </div>
          </div>
        </div>

        {/* Upload Box */}
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
              accept="audio/*"
              onChange={handleFileUpload}
              className="block w-full text-sm text-slate-400
                file:mr-4 file:py-2 file:px-4
                file:rounded-md file:border-0
                file:text-sm file:font-semibold
                file:bg-indigo-600 file:text-white
                hover:file:bg-indigo-500 cursor-pointer"
            />
          </div>

          {uploadProgress !== null && (
            <div className="space-y-2 pt-2">
              <div className="flex justify-between text-xs text-slate-400">
                <span>{uploadStatusText}</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-indigo-500 h-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {uploadError && (
            <div className="flex items-center gap-2 text-rose-400 text-sm bg-rose-950/40 border border-rose-900/50 p-3 rounded-lg">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
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
            <div className="text-center py-10 text-slate-500 text-sm">
              No mixes uploaded yet. Choose an audio file above to start analyzing.
            </div>
          ) : (
            <div className="divide-y divide-slate-800">
              {mixes.map((mix) => {
                const activeJob = activeJobs[mix.id];
                const analysis = mix.analysis_result;

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
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
