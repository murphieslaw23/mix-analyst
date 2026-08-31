import { useEffect, useState, useRef, ChangeEvent } from "react";
import { Activity, UploadCloud, Music, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";

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
}

const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB chunks

function App() {
  const [apiStatus, setApiStatus] = useState<string>("checking...");
  const [mixes, setMixes] = useState<MixItem[]>([]);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadStatusText, setUploadStatusText] = useState<string>("");
  const [uploadError, setUploadError] = useState<string | null>(null);
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
      // 1. Initialize upload session
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

      // 2. Upload chunks sequentially
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

      // 3. Complete and probe audio
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

      setUploadStatusText("Upload & audio probe complete!");
      setUploadProgress(100);
      setTimeout(() => {
        setUploadProgress(null);
        setUploadStatusText("");
        if (fileInputRef.current) fileInputRef.current.value = "";
        fetchStatusAndMixes();
      }, 1500);
    } catch (err: any) {
      setUploadError(err.message || "Upload failed");
      setUploadProgress(null);
      setUploadStatusText("");
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
            Resumable Stream Ingestion (Phase 1)
          </h2>
          <p className="text-sm text-slate-400">
            Stream full DJ recordings (WAV, FLAC, MP3) in 5MB chunks without memory exhaustion. Audio is validated using ffprobe.
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

        {/* Mixes List */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-4">
          <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
            <Music className="w-5 h-5 text-emerald-400" />
            Analyzed Mixes ({mixes.length})
          </h2>

          {mixes.length === 0 ? (
            <div className="text-center py-10 text-slate-500 text-sm">
              No mixes uploaded yet. Choose an audio file above to start analyzing.
            </div>
          ) : (
            <div className="divide-y divide-slate-800">
              {mixes.map((mix) => (
                <div key={mix.id} className="py-4 flex items-center justify-between">
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
                  <div className="flex items-center gap-2 text-xs text-emerald-400 bg-emerald-950/40 border border-emerald-900/50 px-2.5 py-1 rounded-md">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Ready</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
