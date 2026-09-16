import React, { useCallback, useEffect, useRef, useState } from 'react';
import { API_BASE, api, authHeaders, getApiKey, setApiKey } from '../api';

interface JobStatus {
  id: string;
  job_type: string;
  status: string;
  progress_percent: number;
  current_stage?: string | null;
  error_message?: string | null;
}

interface SelectedMix {
  id: string;
  title?: string;
}

interface PipelinePanelProps {
  selectedMix: SelectedMix | null;
  isDark: boolean;
  onLibraryChanged: () => void;
}

const TERMINAL = new Set(['SUCCEEDED', 'FAILED', 'CANCELLED', 'completed', 'failed', 'synced', 'rendered']);

function badge(status: string | undefined, isDark: boolean): string {
  const base = 'px-2 py-0.5 rounded text-[10px] font-mono font-bold border ';
  const s = (status || '').toUpperCase();
  if (s === 'SUCCEEDED' || s === 'COMPLETED' || s === 'SYNCED' || s === 'RENDERED') {
    return base + 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40';
  }
  if (s === 'FAILED') {
    return base + 'bg-red-500/15 text-red-400 border-red-500/40';
  }
  if (s === 'RUNNING' || s === 'PROCESSING' || s === 'QUEUED' || s === 'RENDERING') {
    return base + 'bg-amber-500/15 text-amber-400 border-amber-500/40';
  }
  return base + (isDark ? 'bg-neutral-800 text-neutral-300 border-neutral-700' : 'bg-neutral-100 text-neutral-600 border-neutral-300');
}

/** Subscribe to job SSE; fall back to polling when the stream errors out. */
function useJobEvents(
  jobId: string | null,
  onUpdate: (data: Partial<JobStatus> & { id: string }) => void,
): void {
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  useEffect(() => {
    if (!jobId) return;
    let stopped = false;
    let source: EventSource | null = null;
    let poller: number | null = null;

    const pollOnce = async () => {
      try {
        const res = await api.get(`/jobs/${jobId}`);
        if (!stopped) onUpdateRef.current(res.data);
      } catch {
        // backend unreachable — leave last known state in place
      }
    };

    try {
      source = new EventSource(`${API_BASE}/jobs/${jobId}/events`);
      source.addEventListener('update', (event) => {
        try {
          onUpdateRef.current(JSON.parse((event as MessageEvent).data));
        } catch {
          // ignore malformed frames
        }
      });
      source.addEventListener('close', () => {
        source?.close();
        void pollOnce();
      });
      source.onerror = () => {
        source?.close();
        source = null;
        if (!stopped && poller === null) {
          poller = window.setInterval(() => void pollOnce(), 3000);
          void pollOnce();
        }
      };
    } catch {
      poller = window.setInterval(() => void pollOnce(), 3000);
    }

    return () => {
      stopped = true;
      source?.close();
      if (poller !== null) window.clearInterval(poller);
    };
  }, [jobId]);
}

export const PipelinePanel: React.FC<PipelinePanelProps> = ({ selectedMix, isDark, onLibraryChanged }) => {
  const [apiKey, setApiKeyState] = useState<string>(() => getApiKey());
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [panelError, setPanelError] = useState<string | null>(null);
  const [panelNotice, setPanelNotice] = useState<string | null>(null);

  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadArtist, setUploadArtist] = useState('');
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadDoneName, setUploadDoneName] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const [mastering, setMastering] = useState<any>(null);
  const [masterPreset, setMasterPreset] = useState('sound_system_heavy');
  const [stems, setStems] = useState<any>(null);
  const [stemModel, setStemModel] = useState('htdemucs');
  const [sidechain, setSidechain] = useState<any>(null);
  const [broadcast, setBroadcast] = useState<any>(null);
  const [renderTitle, setRenderTitle] = useState('');
  const [syncStation, setSyncStation] = useState('syco23_live');
  const [syncPlaylist, setSyncPlaylist] = useState('Underground Freetekno Sets');

  const card = isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm';
  const input = isDark
    ? 'bg-[#0d0e12] border-[#292c38] text-neutral-200'
    : 'bg-[#f9fafb] border-[#d1d5db] text-neutral-800';
  const btnPrimary = 'px-3 py-1.5 bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold rounded shadow-sm disabled:opacity-50';
  const btnGhost = isDark
    ? 'px-3 py-1.5 bg-[#1f222c] hover:bg-[#282c38] border border-[#374151] text-[#d1d5db] text-xs font-semibold rounded'
    : 'px-3 py-1.5 bg-[#f3f4f6] hover:bg-[#e5e7eb] border border-[#d1d5db] text-[#374151] text-xs font-semibold rounded';

  const liveJobId = jobs.find((j) => !TERMINAL.has((j.status || '').toUpperCase()))?.id ?? null;

  const mergeJob = useCallback((data: Partial<JobStatus> & { id: string }) => {
    setJobs((prev) => prev.map((j) => (j.id === data.id ? { ...j, ...data } : j)));
  }, []);

  useJobEvents(liveJobId, mergeJob);

  const fetchAll = useCallback(async () => {
    if (!selectedMix) return;
    const headers = authHeaders();
    try {
      const [jobsRes, masteringRes, stemsRes, sidechainRes, broadcastRes] = await Promise.all([
        api.get(`/mixes/${selectedMix.id}/jobs`, { headers }).catch(() => null),
        api.get(`/mixes/${selectedMix.id}/mastering-report`, { headers }).catch(() => null),
        api.get(`/mixes/${selectedMix.id}/stems`, { headers }).catch(() => null),
        api.get(`/mixes/${selectedMix.id}/sidechain`, { headers }).catch(() => null),
        api.get(`/mixes/${selectedMix.id}/broadcast-status`, { headers }).catch(() => null),
      ]);
      if (jobsRes) setJobs(jobsRes.data || []);
      setMastering(masteringRes?.data ?? null);
      setStems(stemsRes?.data ?? null);
      setSidechain(sidechainRes?.data ?? null);
      setBroadcast(broadcastRes?.data ?? null);
      setPanelError(null);
    } catch {
      setPanelError('Backend unreachable — start the API service to use pipeline operations.');
    }
  }, [selectedMix]);

  useEffect(() => {
    setJobs([]);
    setMastering(null);
    setStems(null);
    setSidechain(null);
    setBroadcast(null);
    void fetchAll();
    const timer = window.setInterval(() => void fetchAll(), 5000);
    return () => window.clearInterval(timer);
  }, [fetchAll]);

  const describeError = (err: unknown): string => {
    const detail = (err as any)?.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    return (err as Error)?.message || 'Request failed';
  };

  const saveKey = () => {
    setApiKey(apiKey.trim());
    setPanelNotice(apiKey.trim() ? 'API key saved for mutation requests.' : 'API key cleared — open mode.');
    setTimeout(() => setPanelNotice(null), 3000);
  };

  const dispatchAnalysis = async () => {
    if (!selectedMix) return;
    try {
      await api.post(`/mixes/${selectedMix.id}/jobs`, { job_type: 'ANALYSIS' }, { headers: authHeaders() });
      await fetchAll();
    } catch (err) {
      setPanelError(describeError(err));
    }
  };

  const cancelJob = async (id: string) => {
    try {
      await api.post(`/jobs/${id}/cancel`, {}, { headers: authHeaders() });
      await fetchAll();
    } catch (err) {
      setPanelError(describeError(err));
    }
  };

  const retryJob = async (id: string) => {
    try {
      await api.post(`/jobs/${id}/retry`, {}, { headers: authHeaders() });
      await fetchAll();
    } catch (err) {
      setPanelError(describeError(err));
    }
  };

  const startUpload = async () => {
    if (!uploadFile || uploading) return;
    setUploading(true);
    setUploadProgress(0);
    try {
      const CHUNK = 5 * 1024 * 1024;
      const total = uploadFile.size;
      const init = await api.post(
        '/uploads',
        { filename: uploadFile.name, total_size_bytes: total, chunk_size: CHUNK },
        { headers: authHeaders() },
      );
      const uploadId: string = init.data.upload_id;
      let offset = 0;
      while (offset < total) {
        const slice = uploadFile.slice(offset, offset + CHUNK);
        const form = new FormData();
        form.append('file', slice, uploadFile.name);
        form.append('offset', String(offset));
        const res = await api.patch(`/uploads/${uploadId}`, form, { headers: authHeaders() });
        offset = res.data.bytes_received;
        setUploadProgress(Math.min(99, Math.round((offset / total) * 100)));
      }
      const title = uploadTitle.trim() || uploadFile.name.replace(/\.[^.]+$/, '');
      const done = await api.post(`/uploads/${uploadId}/complete`, { title, artist: uploadArtist.trim() || null }, { headers: authHeaders() });
      setUploadProgress(100);
      setUploadDoneName(uploadFile.name);
      setPanelNotice(`Upload complete — mix "${done.data.title}" registered.`);
      setTimeout(() => setPanelNotice(null), 4000);
      setUploadFile(null);
      setUploadTitle('');
      setUploadArtist('');
      onLibraryChanged();
    } catch (err) {
      setPanelError(`Upload failed: ${describeError(err)}`);
    } finally {
      setUploading(false);
      setTimeout(() => setUploadProgress(null), 4000);
    }
  };

  const triggerMastering = async () => {
    if (!selectedMix) return;
    try {
      await api.post(`/mixes/${selectedMix.id}/master`, { preset_id: masterPreset }, { headers: authHeaders() });
      await fetchAll();
    } catch (err) {
      setPanelError(describeError(err));
    }
  };

  const triggerStems = async () => {
    if (!selectedMix) return;
    try {
      await api.post(`/mixes/${selectedMix.id}/stems`, { model_name: stemModel }, { headers: authHeaders() });
      await fetchAll();
    } catch (err) {
      setPanelError(describeError(err));
    }
  };

  const triggerSidechain = async () => {
    if (!selectedMix) return;
    try {
      await api.post('/mastering/sidechain', { media_id: selectedMix.id }, { headers: authHeaders() });
      await fetchAll();
    } catch (err) {
      setPanelError(describeError(err));
    }
  };

  const triggerRender = async () => {
    if (!selectedMix) return;
    try {
      await api.post(
        '/broadcast/render-stream',
        { media_id: selectedMix.id, stream_title: renderTitle.trim() || selectedMix.title || 'Live Set' },
        { headers: authHeaders() },
      );
      await fetchAll();
    } catch (err) {
      setPanelError(describeError(err));
    }
  };

  const triggerSync = async () => {
    if (!selectedMix) return;
    try {
      await api.post(
        `/mixes/${selectedMix.id}/sync/azuracast`,
        { station_id: syncStation.trim() || 'syco23_live', playlist_name: syncPlaylist.trim() || undefined },
        { headers: authHeaders() },
      );
      await fetchAll();
      setPanelNotice('AzuraCast sync recorded.');
      setTimeout(() => setPanelNotice(null), 3000);
    } catch (err) {
      setPanelError(describeError(err));
    }
  };

  return (
    <div className="space-y-6" data-testid="pipeline-panel">
      {(panelError || panelNotice) && (
        <div
          className={`px-4 py-2.5 rounded-lg border text-xs font-medium ${
            panelError
              ? 'bg-red-950/40 border-red-800 text-red-200'
              : 'bg-emerald-950/40 border-emerald-800 text-emerald-200'
          }`}
        >
          {panelError ?? panelNotice}
        </div>
      )}

      <div className={`border rounded-lg p-5 ${card}`}>
        <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
          <div>
            <h3 className="text-sm font-bold uppercase tracking-widest text-[#ea580c]">Mix Ingestion</h3>
            <p className={`text-xs mt-1 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
              Resumable chunked upload (5 MB slices) with ffprobe validation.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKeyState(e.target.value)}
              placeholder="X-API-Key (optional)"
              data-testid="pipeline-api-key"
              className={`px-2.5 py-1.5 rounded border text-xs font-mono w-48 ${input}`}
            />
            <button onClick={saveKey} className={btnGhost} data-testid="pipeline-api-key-save">
              Save Key
            </button>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="file"
            accept="audio/*,.wav,.flac,.mp3,.ogg,.m4a"
            onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
            data-testid="pipeline-upload-input"
            className={`text-xs file:mr-3 file:px-3 file:py-1.5 file:rounded file:border-0 file:bg-[#ea580c] file:text-white file:text-xs file:font-bold ${isDark ? 'text-neutral-300' : 'text-neutral-600'}`}
          />
          <input
            value={uploadTitle}
            onChange={(e) => setUploadTitle(e.target.value)}
            placeholder="Title (optional)"
            data-testid="pipeline-upload-title"
            className={`px-2.5 py-1.5 rounded border text-xs w-44 ${input}`}
          />
          <input
            value={uploadArtist}
            onChange={(e) => setUploadArtist(e.target.value)}
            placeholder="Artist (optional)"
            data-testid="pipeline-upload-artist"
            className={`px-2.5 py-1.5 rounded border text-xs w-40 ${input}`}
          />
          <button onClick={() => void startUpload()} disabled={!uploadFile || uploading} className={btnPrimary} data-testid="pipeline-upload-start">
            {uploading ? 'Uploading…' : 'Upload Mix'}
          </button>
        </div>
        {uploadProgress !== null && (
          <div className="mt-3">
            <div className={`h-2 rounded-full overflow-hidden ${isDark ? 'bg-[#232630]' : 'bg-[#e5e7eb]'}`}>
              <div className="h-full bg-[#ea580c] transition-all" style={{ width: `${uploadProgress}%` }} data-testid="pipeline-upload-progress" />
            </div>
            <div className={`text-[11px] font-mono mt-1 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
              {uploadDoneName ?? uploadFile?.name} — {uploadProgress}%
            </div>
          </div>
        )}
      </div>

      <div className={`border rounded-lg p-5 ${card}`}>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h3 className="text-sm font-bold uppercase tracking-widest text-[#ea580c]">Analysis Jobs</h3>
            <p className={`text-xs mt-1 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
              {selectedMix ? `Target: ${selectedMix.title || selectedMix.id}` : 'Select a mix from the archive first.'}
            </p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => void fetchAll()} className={btnGhost} data-testid="pipeline-refresh">
              Refresh
            </button>
            <button onClick={() => void dispatchAnalysis()} disabled={!selectedMix} className={btnPrimary} data-testid="pipeline-dispatch-analysis">
              Dispatch Analysis
            </button>
          </div>
        </div>
        <div className="space-y-2" data-testid="pipeline-jobs-list">
          {jobs.length === 0 && (
            <div className={`text-xs ${isDark ? 'text-[#71717a]' : 'text-[#9ca3af]'}`}>No jobs dispatched for this mix yet.</div>
          )}
          {jobs.map((job) => (
            <div key={job.id} className={`p-2.5 rounded border text-xs flex flex-wrap items-center gap-3 ${isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]'}`} data-testid="pipeline-job-row">
              <span className="font-mono font-bold text-[#ea580c]">{job.job_type}</span>
              <span className={badge(job.status, isDark)}>{job.status}</span>
              <div className={`flex-1 min-w-[120px] h-1.5 rounded-full overflow-hidden ${isDark ? 'bg-[#232630]' : 'bg-[#e5e7eb]'}`}>
                <div className="h-full bg-[#0f766e] transition-all" style={{ width: `${Math.min(100, job.progress_percent || 0)}%` }} />
              </div>
              <span className={`font-mono ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
                {(job.progress_percent || 0).toFixed(0)}% · {job.current_stage || '—'}
              </span>
              {job.error_message && <span className="text-red-400 font-mono text-[11px] w-full">{job.error_message}</span>}
              <span className="flex gap-1.5 ml-auto">
                {job.status !== 'SUCCEEDED' && job.status !== 'FAILED' && job.status !== 'CANCELLED' && (
                  <button onClick={() => void cancelJob(job.id)} className={btnGhost} data-testid={`pipeline-job-cancel-${job.id}`}>
                    Cancel
                  </button>
                )}
                {(job.status === 'FAILED' || job.status === 'CANCELLED') && (
                  <button onClick={() => void retryJob(job.id)} className={btnGhost} data-testid={`pipeline-job-retry-${job.id}`}>
                    Retry
                  </button>
                )}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className={`border rounded-lg p-4 ${card}`}>
          <h4 className="text-xs font-bold uppercase tracking-widest text-[#ea580c] mb-2">Mastering</h4>
          <div className="flex gap-2 mb-3">
            <select value={masterPreset} onChange={(e) => setMasterPreset(e.target.value)} data-testid="pipeline-master-preset" className={`flex-1 px-2.5 py-1.5 rounded border text-xs ${input}`}>
              <option value="sound_system_heavy">Sound System Heavy (-11 LUFS)</option>
              <option value="club_broadcast">Club Broadcast (-14 LUFS)</option>
              <option value="vinyl_premaster">Vinyl Pre-Master (-16 LUFS)</option>
            </select>
            <button onClick={() => void triggerMastering()} disabled={!selectedMix} className={btnPrimary} data-testid="pipeline-master-trigger">
              Master
            </button>
          </div>
          <div className="text-xs font-mono" data-testid="pipeline-master-status">
            {mastering ? (
              <span className="flex flex-wrap items-center gap-2">
                <span className={badge(mastering.status, isDark)}>{mastering.status}</span>
                {mastering.status === 'completed' && (
                  <>
                    <span className={isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}>
                      {mastering.output_measurements?.integrated_lufs} LUFS · {mastering.compliance_passed ? 'COMPLIANT' : 'CHECK'}
                    </span>
                    <a href={`${API_BASE}/mixes/${selectedMix?.id}/mastered`} download className="text-[#ea580c] hover:underline">
                      Download master WAV
                    </a>
                  </>
                )}
              </span>
            ) : (
              <span className={isDark ? 'text-[#71717a]' : 'text-[#9ca3af]'}>No mastering job yet.</span>
            )}
          </div>
        </div>

        <div className={`border rounded-lg p-4 ${card}`}>
          <h4 className="text-xs font-bold uppercase tracking-widest text-[#ea580c] mb-2">Stem Separation</h4>
          <div className="flex gap-2 mb-3">
            <select value={stemModel} onChange={(e) => setStemModel(e.target.value)} data-testid="pipeline-stem-model" className={`flex-1 px-2.5 py-1.5 rounded border text-xs ${input}`}>
              <option value="htdemucs">htdemucs (4-stem)</option>
              <option value="htdemucs_ft">htdemucs_ft (fine-tuned)</option>
              <option value="hdemucs_mmi">hdemucs_mmi</option>
            </select>
            <button onClick={() => void triggerStems()} disabled={!selectedMix} className={btnPrimary} data-testid="pipeline-stem-trigger">
              Separate
            </button>
          </div>
          <div className="text-xs font-mono" data-testid="pipeline-stem-status">
            {stems ? (
              <span className="flex flex-wrap items-center gap-2">
                <span className={badge(stems.status, isDark)}>{stems.status}</span>
                {stems.status === 'completed' && stems.bassline_analysis && (
                  <span className={isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}>
                    {stems.bassline_analysis.bass_fundamental_hz} Hz · clash {stems.bassline_analysis.kick_sub_collision_score} · {stems.bassline_analysis.low_end_clarity}
                  </span>
                )}
                {stems.status === 'failed' && <span className="text-red-400">Demucs missing? Install the optional separation stack on the worker.</span>}
              </span>
            ) : (
              <span className={isDark ? 'text-[#71717a]' : 'text-[#9ca3af]'}>No stem job yet.</span>
            )}
          </div>
        </div>

        <div className={`border rounded-lg p-4 ${card}`}>
          <h4 className="text-xs font-bold uppercase tracking-widest text-[#ea580c] mb-2">Sidechain</h4>
          <p className={`text-[11px] mb-2 ${isDark ? 'text-[#71717a]' : 'text-[#9ca3af]'}`}>Requires completed stem separation.</p>
          <div className="flex gap-2 mb-3">
            <button onClick={() => void triggerSidechain()} disabled={!selectedMix} className={btnPrimary} data-testid="pipeline-sidechain-trigger">
              Run Ducking
            </button>
          </div>
          <div className="text-xs font-mono" data-testid="pipeline-sidechain-status">
            {sidechain ? (
              <span className="flex flex-wrap items-center gap-2">
                <span className={badge(sidechain.status, isDark)}>{sidechain.status}</span>
                {sidechain.status === 'completed' && (
                  <span className={isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}>
                    GR {sidechain.max_gain_reduction_db} dB · clarity {sidechain.low_end_clarity_score}
                    {sidechain.phase_inverted ? ' · phase flipped' : ''}
                  </span>
                )}
              </span>
            ) : (
              <span className={isDark ? 'text-[#71717a]' : 'text-[#9ca3af]'}>No sidechain job yet.</span>
            )}
          </div>
        </div>

        <div className={`border rounded-lg p-4 ${card}`}>
          <h4 className="text-xs font-bold uppercase tracking-widest text-[#ea580c] mb-2">Broadcast & Radio</h4>
          <div className="flex flex-col gap-2 mb-3">
            <input value={renderTitle} onChange={(e) => setRenderTitle(e.target.value)} placeholder="Stream title (optional)" data-testid="pipeline-render-title" className={`px-2.5 py-1.5 rounded border text-xs ${input}`} />
            <div className="flex gap-2">
              <button onClick={() => void triggerRender()} disabled={!selectedMix} className={btnPrimary} data-testid="pipeline-render-trigger">
                Render 1080p
              </button>
              <button onClick={() => void triggerSync()} disabled={!selectedMix} className={btnGhost} data-testid="pipeline-sync-trigger">
                Sync AzuraCast
              </button>
            </div>
            <div className="flex gap-2">
              <input value={syncStation} onChange={(e) => setSyncStation(e.target.value)} placeholder="Station ID" data-testid="pipeline-sync-station" className={`flex-1 px-2.5 py-1.5 rounded border text-xs ${input}`} />
              <input value={syncPlaylist} onChange={(e) => setSyncPlaylist(e.target.value)} placeholder="Playlist" data-testid="pipeline-sync-playlist" className={`flex-1 px-2.5 py-1.5 rounded border text-xs ${input}`} />
            </div>
          </div>
          <div className="text-xs font-mono space-y-1" data-testid="pipeline-broadcast-status">
            <div className="flex items-center gap-2">
              <span className={isDark ? 'text-[#71717a]' : 'text-[#9ca3af]'}>Render:</span>
              <span className={badge(broadcast?.status, isDark)}>{broadcast?.status || '—'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PipelinePanel;
