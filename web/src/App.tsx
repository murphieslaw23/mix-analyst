import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import {
  CheckCircle,
  ExternalLink,
  Volume2,
  Layers,
  Radio,
  Wrench,
} from 'lucide-react';
import { PipelinePanel } from './components/PipelinePanel';
import { WaveformDetail } from './components/WaveformDetail';
import { AnalysisPanel } from './components/AnalysisPanel';
import { MixLibrary } from './components/MixLibrary';
import { AppShell } from './app/AppShell';
import {
  JOBS_ANCHOR,
  PROCESS_ROUTE,
  getRouteForPath,
  navigate,
  usePathname,
} from './app/routes';
import { API_BASE } from './api';
import {
  normalizeAnalysis,
  normalizeMixDetail,
  normalizeMixListItem,
} from './api/mixAdapters';
import { normalizeMixListResponse } from './api/contracts';
import { clamp, formatTime } from './audio/format';
import type {
  AnalysisSummary,
  MixDetail,
  MixListItem,
  RegionSelection,
  ZoomWindow,
} from './types';

const FULL_ZOOM: ZoomWindow = { start: 0, end: 1 };
const PEAK_BUCKETS = 1200;

export const App: React.FC = () => {
  const [mixes, setMixes] = useState<MixListItem[]>([]);
  const [libraryLoading, setLibraryLoading] = useState<boolean>(true);
  const [libraryError, setLibraryError] = useState<string | null>(null);
  const [selectedMix, setSelectedMix] = useState<MixDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisSummary | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState<boolean>(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    try {
      return (localStorage.getItem('syco_theme') as 'dark' | 'light') || 'dark';
    } catch {
      return 'dark';
    }
  });
  const pathname = usePathname();
  const route = getRouteForPath(pathname);
  const [notification, setNotification] = useState<string | null>(null);
  const [installPrompt, setInstallPrompt] = useState<any>(null);
  const [zoom, setZoom] = useState<ZoomWindow>(FULL_ZOOM);
  const [selection, setSelection] = useState<RegionSelection>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [peaks, setPeaks] = useState<number[] | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem('syco_theme', theme);
    } catch {
      // storage unavailable — theme simply won't persist
    }
    if (theme === 'light') {
      document.documentElement.classList.add('light-mode');
    } else {
      document.documentElement.classList.remove('light-mode');
    }
  }, [theme]);

  useEffect(() => {
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setInstallPrompt(e);
    };
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    return () => window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
  }, []);

  const triggerInstall = async () => {
    if (!installPrompt) return;
    installPrompt.prompt();
    const { outcome } = await installPrompt.userChoice;
    if (outcome === 'accepted') {
      setInstallPrompt(null);
      setNotification('SYSTEM CORRUPT PWA installed successfully!');
      setTimeout(() => setNotification(null), 4000);
    }
  };

  const togglePlayback = useCallback(() => {
    // NB: use getAttribute, not the .src property — the property resolves
    // an empty src to the page URL (truthy), which breaks the no-source toggle.
    const audioSrc = audioRef.current?.getAttribute('src');
    if (audioRef.current && audioSrc) {
      if (audioRef.current.paused) {
        audioRef.current.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false));
      } else {
        audioRef.current.pause();
        setIsPlaying(false);
      }
    } else {
      setIsPlaying((prev) => !prev);
    }
  }, []);

  const seekTo = useCallback((time: number) => {
    const clamped = Math.max(0, time);
    setCurrentTime(clamped);
    if (audioRef.current) {
      try {
        audioRef.current.currentTime = clamped;
      } catch {
        // audio not yet seekable — position state still updates
      }
    }
  }, []);

  const jumpToCue = useCallback((direction: 'next' | 'prev') => {
    if (!selectedMix) return;
    const cues = (selectedMix.tracks || []).map((t) => t.start_time).sort((a, b) => a - b);
    if (cues.length === 0) return;
    // Read live position from the element when audio is present.
    const pos = audioRef.current?.getAttribute('src') ? audioRef.current.currentTime : currentTime;
    if (direction === 'next') {
      const target = cues.find((c) => c > pos + 1.0);
      seekTo(target !== undefined ? target : cues[0]);
    } else {
      const target = [...cues].reverse().find((c) => c < pos - 1.0);
      seekTo(target !== undefined ? target : 0);
    }
  }, [selectedMix, currentTime, seekTo]);

  const fetchMixes = useCallback(async () => {
    setLibraryLoading(true);
    setLibraryError(null);
    try {
      const res = await axios.get(`${API_BASE}/mixes`);
      const payload = res.data;
      const page = normalizeMixListResponse(payload);
      const items = page.items.map(normalizeMixListItem);
      setMixes(items);
      if (items.length > 0) {
        const stillThere = selectedMix && items.some((m: MixListItem) => m.id === selectedMix.id);
        if (!selectedMix || !stillThere) {
          void handleMixSelect(items[0].id);
        }
      } else {
        setSelectedMix(null);
      }
    } catch {
      setLibraryError('Backend unreachable. Check that the API is running, then retry.');
    } finally {
      setLibraryLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedMix?.id]);

  useEffect(() => {
    void fetchMixes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleMixSelect = async (mixId: string) => {
    setDetailLoading(true);
    setDetailError(null);
    setAnalysis(null);
    setAnalysisError(null);
    setPeaks(null);
    setZoom(FULL_ZOOM);
    setSelection(null);
    try {
      const res = await axios.get(`${API_BASE}/mixes/${mixId}`);
      setSelectedMix(normalizeMixDetail(res.data));
      setCurrentTime(0);
      setIsPlaying(false);
      if (audioRef.current) {
        audioRef.current.currentTime = 0;
        audioRef.current.pause();
      }
      void fetchPeaks(mixId);
      void fetchAnalysis(mixId);
    } catch {
      setDetailError('Could not load this mix. It may have been deleted — retry or pick another set.');
    } finally {
      setDetailLoading(false);
    }
  };

  const fetchPeaks = async (mixId: string) => {
    try {
      const res = await axios.get(`${API_BASE}/mixes/${mixId}/peaks?buckets=${PEAK_BUCKETS}`);
      if (Array.isArray(res.data?.peaks) && res.data.peaks.length > 0) {
        setPeaks(res.data.peaks);
      } else {
        setPeaks(null);
      }
    } catch {
      // Peaks are optional: the waveform stays interactive without them.
      setPeaks(null);
    }
  };

  const fetchAnalysis = async (mixId: string) => {
    setAnalysisLoading(true);
    setAnalysisError(null);
    try {
      const res = await axios.get(`${API_BASE}/mixes/${mixId}/analysis`);
      setAnalysis(normalizeAnalysis(res.data));
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 404) {
        setAnalysis(null);
      } else {
        setAnalysisError('Engine analysis could not be loaded for this mix.');
      }
    } finally {
      setAnalysisLoading(false);
    }
  };

  const copyYouTubeTimestamps = () => {
    if (!selectedMix || !selectedMix.tracks) return;
    const lines = selectedMix.tracks.map((t) => {
      const timeStr = formatTime(t.start_time);
      return `${timeStr} ${t.artist || 'Unknown'} - ${t.title || 'Untitled'} [${t.camelot_key || 'Key'}]`;
    });
    navigator.clipboard.writeText(lines.join('\n'));
    setNotification('YouTube timestamps copied to clipboard!');
    setTimeout(() => setNotification(null), 3000);
  };

  const isDark = theme === 'dark';
  const duration = selectedMix?.duration_seconds || 0;
  const tracks = selectedMix?.tracks ?? [];
  const transitions = selectedMix?.transitions ?? [];
  const qualityFindings = analysis?.quality_findings ?? [];

  const selectedQualityId = selection?.kind === 'quality' ? selection.id : null;

  const renderRegionInspector = () => {
    if (!selection || !selectedMix) return null;

    if (selection.kind === 'track') {
      const idx = tracks.findIndex((t, i) => (t.id ?? `track-${i}`) === selection.id);
      const tr = tracks[idx];
      if (!tr) return null;
      const end = tracks[idx + 1]?.start_time ?? duration;
      return (
        <div data-testid="region-inspector" className={`border rounded-lg p-4 ${isDark ? 'bg-[#1a1c24] border-[#dc2626]/50' : 'bg-red-50 border-[#fca5a5]'}`}>
          <p className={`text-[10px] font-bold uppercase tracking-widest ${isDark ? 'text-[#fca5a5]' : 'text-[#991b1b]'}`}>
            Track {idx + 1} — engine segment
          </p>
          <p className={`mt-1 font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>
            {tr.artist || 'Unknown Artist'} — {tr.title || 'Untitled'}
          </p>
          <p className={`text-xs font-mono mt-1 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
            {formatTime(tr.start_time)} → {formatTime(end)} · {tr.camelot_key || 'no key'}
            {tr.bpm ? ` · ${tr.bpm.toFixed(1)} BPM` : ''}
          </p>
          <button onClick={() => seekTo(tr.start_time)} className="mt-2 px-3 py-1.5 min-h-[44px] rounded bg-[#dc2626] text-white text-xs font-bold">
            Jump to cue
          </button>
        </div>
      );
    }

    if (selection.kind === 'transition') {
      const tr = transitions.find((t, i) => (t.id ?? `transition-${i}`) === selection.id);
      if (!tr) return null;
      return (
        <div data-testid="region-inspector" className={`border rounded-lg p-4 ${isDark ? 'bg-[#1a1c24] border-[#d97706]/60' : 'bg-amber-50 border-[#fcd34d]'}`}>
          <p className="text-[10px] font-bold uppercase tracking-widest text-[#d97706]">
            {tr.transition_type || 'Transition'} — engine blend zone
          </p>
          <p className={`text-xs font-mono mt-1 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
            {formatTime(tr.start_time)} → {formatTime(tr.end_time ?? tr.start_time + 30)} · {tr.from_key || '?'} → {tr.to_key || '?'}
          </p>
          <p className={`text-xs mt-1 ${isDark ? 'text-[#e0e2ec]' : 'text-gray-800'}`}>
            {tr.harmonic_compatibility || 'No compatibility rating'}
            {tr.confidence !== undefined ? ` · conf ${(tr.confidence * 100).toFixed(0)}%` : ''}
          </p>
          <button onClick={() => seekTo(tr.start_time)} className="mt-2 px-3 py-1.5 min-h-[44px] rounded bg-[#d97706] text-white text-xs font-bold">
            Jump to blend start
          </button>
        </div>
      );
    }

    const qIdx = Number.parseInt(selection.id.replace('q-', ''), 10);
    const q = qualityFindings[qIdx];
    if (!q) return null;
    const range = q.timestamp_range;
    return (
      <div data-testid="region-inspector" className={`border rounded-lg p-4 ${isDark ? 'bg-[#1a1c24] border-[#a855f7]/60' : 'bg-purple-50 border-[#d8b4fe]'}`}>
        <p className={`text-[10px] font-bold uppercase tracking-widest ${isDark ? 'text-[#d8b4fe]' : 'text-[#7e22ce]'}`}>
          [{q.severity}] {q.type} — engine quality flag
        </p>
        <p className={`text-xs mt-1 ${isDark ? 'text-[#e0e2ec]' : 'text-gray-800'}`}>{q.description}</p>
        {range && range.length >= 2 && (
          <>
            <p className={`text-xs font-mono mt-1 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
              {formatTime(range[0])} → {formatTime(range[1])}
            </p>
            <button onClick={() => seekTo(range[0])} className="mt-2 px-3 py-1.5 min-h-[44px] rounded bg-[#a855f7] text-white text-xs font-bold">
              Jump to flag
            </button>
          </>
        )}
      </div>
    );
  };

  return (
    <AppShell
      currentPath={pathname}
      theme={theme}
      onToggleTheme={() => setTheme(isDark ? 'light' : 'dark')}
      installPrompt={installPrompt}
      onInstall={() => void triggerInstall()}
    >
      <audio
        ref={audioRef}
        src={selectedMix?.audio_url || ''}
        onTimeUpdate={() => {
          if (audioRef.current) setCurrentTime(audioRef.current.currentTime);
        }}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
        data-testid="main-audio-player"
        className="hidden"
      />

      {notification && (
        <div className="fixed bottom-6 right-6 z-50 bg-[#ea580c] text-white px-5 py-3 rounded-lg shadow-xl font-medium text-xs flex items-center gap-2" role="status">
          <CheckCircle className="w-4 h-4" />
          {notification}
        </div>
      )}

        {route === 'process' && (
          <PipelinePanel
            selectedMix={selectedMix}
            isDark={isDark}
            onLibraryChanged={fetchMixes}
          />
        )}
        {route === 'jobs' && (
          <div className="space-y-6" data-testid="jobs-view">
            <div className={`border rounded-lg p-6 ${isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'}`}>
              <h2 className="text-xl font-bold text-[#ea580c] uppercase tracking-wide mb-2">
                Jobs
              </h2>
              <p className={`text-sm leading-relaxed ${isDark ? 'text-[#9ca3af]' : 'text-[#4b5563]'}`}>
                Job dispatch and live progress live in the Process surface. No jobs are
                fabricated here — open Pipeline &amp; Broadcast to dispatch and track real
                engine jobs for the selected mix.
              </p>
              <div className="flex flex-wrap gap-2 mt-4">
                <a
                  href={PROCESS_ROUTE}
                  onClick={(e) => {
                    e.preventDefault();
                    navigate(PROCESS_ROUTE);
                  }}
                  className="px-4 py-2 min-h-[44px] inline-flex items-center rounded bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold"
                >
                  Go to Pipeline &amp; Broadcast
                </a>
                <a
                  href={JOBS_ANCHOR}
                  onClick={(e) => {
                    e.preventDefault();
                    navigate(JOBS_ANCHOR);
                  }}
                  className={`px-4 py-2 min-h-[44px] inline-flex items-center text-xs font-semibold rounded border transition ${
                    isDark
                      ? 'bg-[#1f222c] hover:bg-[#282c38] border-[#374151] text-[#d1d5db]'
                      : 'bg-[#f3f4f6] hover:bg-[#e5e7eb] border-[#d1d5db] text-[#374151]'
                  }`}
                >
                  Analysis jobs anchor
                </a>
              </div>
            </div>
          </div>
        )}
        {route === 'library' && (
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 md:col-span-3">
              <MixLibrary
                mixes={mixes}
                selectedId={selectedMix?.id ?? null}
                loading={libraryLoading}
                error={libraryError}
                onSelect={handleMixSelect}
                onRetry={fetchMixes}
                isDark={isDark}
              />
            </div>

            <div className="col-span-12 md:col-span-9 space-y-6">
              {detailLoading && (
                <div className={`p-12 text-center rounded-lg border ${isDark ? 'bg-[#15171e] border-[#232630] text-[#71717a]' : 'bg-white border-[#e5e7eb] text-[#6b7280]'}`} aria-busy="true">
                  Loading mix detail…
                </div>
              )}
              {!detailLoading && detailError && (
                <div className={`p-8 rounded-lg border ${isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb]'}`} role="alert">
                  <p className="font-semibold text-red-400 text-sm">Mix detail unavailable</p>
                  <p className={`text-xs mt-1 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>{detailError}</p>
                  <button
                    onClick={() => selectedMix && handleMixSelect(selectedMix.id)}
                    className="mt-3 px-4 py-2 min-h-[44px] rounded bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold"
                  >
                    Retry
                  </button>
                </div>
              )}
              {!detailLoading && !detailError && selectedMix ? (
                <>
                  <div className={`border rounded-lg p-5 ${
                    isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'
                  }`}>
                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4">
                      <div>
                        <h3 className={`text-lg font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>
                          {selectedMix.title || selectedMix.original_filename}
                        </h3>
                        <p className={`text-xs font-mono mt-0.5 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
                          Position: {formatTime(currentTime)} / {formatTime(duration)}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <a
                          href={`${API_BASE}/mixes/${selectedMix.id}/export/cue`}
                          download
                          className={`px-3 py-1.5 min-h-[44px] inline-flex items-center text-xs font-semibold rounded border transition ${
                            isDark
                              ? 'bg-[#1f222c] hover:bg-[#282c38] border-[#374151] text-[#d1d5db]'
                              : 'bg-[#f3f4f6] hover:bg-[#e5e7eb] border-[#d1d5db] text-[#374151]'
                          }`}
                        >
                          Export .CUE
                        </a>
                        <a
                          href={`${API_BASE}/mixes/${selectedMix.id}/export/rekordbox`}
                          download
                          className={`px-3 py-1.5 min-h-[44px] inline-flex items-center text-xs font-semibold rounded border transition ${
                            isDark
                              ? 'bg-[#1f222c] hover:bg-[#282c38] border-[#374151] text-[#d1d5db]'
                              : 'bg-[#f3f4f6] hover:bg-[#e5e7eb] border-[#d1d5db] text-[#374151]'
                          }`}
                        >
                          Rekordbox XML
                        </a>
                        <a
                          href={`${API_BASE}/mixes/${selectedMix.id}/export/traktor`}
                          download
                          className={`px-3 py-1.5 min-h-[44px] inline-flex items-center text-xs font-semibold rounded border transition ${
                            isDark
                              ? 'bg-[#1f222c] hover:bg-[#282c38] border-[#374151] text-[#d1d5db]'
                              : 'bg-[#f3f4f6] hover:bg-[#e5e7eb] border-[#d1d5db] text-[#374151]'
                          }`}
                        >
                          Traktor NML
                        </a>
                        <button
                          onClick={copyYouTubeTimestamps}
                          className="px-3 py-1.5 min-h-[44px] bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-semibold rounded shadow-sm"
                        >
                          Copy YouTube Timestamps
                        </button>
                      </div>
                    </div>

                    <WaveformDetail
                      peaks={peaks}
                      duration={duration}
                      tracks={tracks}
                      transitions={transitions}
                      qualityFindings={qualityFindings}
                      currentTime={currentTime}
                      zoom={zoom}
                      onZoomChange={setZoom}
                      onSeek={seekTo}
                      selection={selection}
                      onSelectRegion={setSelection}
                      isDark={isDark}
                    />

                    <div className="mt-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          onClick={togglePlayback}
                          data-testid="play-pause-btn"
                          aria-pressed={isPlaying}
                          className={`px-4 py-1.5 min-h-[44px] rounded font-bold transition ${
                            isDark ? 'bg-[#252834] hover:bg-[#323646] text-white' : 'bg-[#e5e7eb] hover:bg-[#d1d5db] text-black'
                          }`}
                        >
                          {isPlaying ? 'PAUSE' : 'PLAY'}
                        </button>
                        <button
                          onClick={() => jumpToCue('prev')}
                          aria-label="Jump to previous track cue"
                          className={`px-3 py-1.5 min-h-[44px] rounded transition ${
                            isDark ? 'bg-[#1f222c] hover:bg-[#2a2e3c] text-white' : 'bg-[#f3f4f6] hover:bg-[#e5e7eb] text-black'
                          }`}
                        >
                          PREV CUE
                        </button>
                        <button
                          onClick={() => jumpToCue('next')}
                          aria-label="Jump to next track cue"
                          className={`px-3 py-1.5 min-h-[44px] rounded transition ${
                            isDark ? 'bg-[#1f222c] hover:bg-[#2a2e3c] text-white' : 'bg-[#f3f4f6] hover:bg-[#e5e7eb] text-black'
                          }`}
                        >
                          NEXT CUE
                        </button>
                        <button
                          onClick={() => seekTo(0)}
                          className={`px-3 py-1.5 min-h-[44px] rounded transition ${
                            isDark ? 'bg-[#1f222c] hover:bg-[#2a2e3c] text-white' : 'bg-[#f3f4f6] hover:bg-[#e5e7eb] text-black'
                          }`}
                        >
                          RESTART
                        </button>
                      </div>
                      <p className={`font-mono ${isDark ? 'text-[#71717a]' : 'text-[#9ca3af]'}`}>
                        {clamp(currentTime, 0, duration).toFixed(1)}s · {(peaks?.length ?? 0)} peak buckets
                      </p>
                    </div>
                  </div>

                  {renderRegionInspector()}

                  <AnalysisPanel
                    analysis={analysis}
                    loading={analysisLoading}
                    error={analysisError}
                    selectedQualityId={selectedQualityId}
                    onSelectQuality={(id) => setSelection(id ? { kind: 'quality', id } : null)}
                    isDark={isDark}
                  />

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className={`border rounded-lg p-4 ${
                      isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'
                    }`}>
                      <h4 className={`text-xs font-bold uppercase tracking-widest mb-3 ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>
                        Detected Tracks ({tracks.length})
                      </h4>
                      <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                        {tracks.map((t, idx) => {
                          const id = t.id ?? `track-${idx}`;
                          const selected = selection?.kind === 'track' && selection.id === id;
                          return (
                            <div
                              key={id}
                              data-testid="track-card"
                              onClick={() => {
                                setSelection({ kind: 'track', id });
                                seekTo(t.start_time);
                              }}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter' || e.key === ' ') {
                                  e.preventDefault();
                                  setSelection({ kind: 'track', id });
                                  seekTo(t.start_time);
                                }
                              }}
                              role="button"
                              tabIndex={0}
                              aria-pressed={selected}
                              className={`p-2.5 rounded flex items-center justify-between text-xs cursor-pointer border transition ${
                                selected
                                  ? 'border-[#ea580c] ring-1 ring-[#ea580c]'
                                  : isDark
                                    ? 'bg-[#1a1c24] hover:bg-[#20232e] border-[#292c38]'
                                    : 'bg-[#f9fafb] hover:bg-[#f3f4f6] border-[#e5e7eb]'
                              }`}
                            >
                              <div>
                                <div className={`font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>
                                  {idx + 1}. {t.title || 'Unknown Track'}
                                </div>
                                <div className={`text-[11px] ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>
                                  {t.artist || 'Unknown Artist'}
                                </div>
                              </div>
                              <div className="text-right">
                                <span className="px-1.5 py-0.5 bg-[#ea580c]/20 text-[#ea580c] rounded border border-[#ea580c]/30 text-[10px] font-mono font-bold">
                                  {t.camelot_key || 'KEY'}
                                </span>
                                <div className={`mt-1 font-mono text-[11px] ${isDark ? 'text-[#71717a]' : 'text-[#9ca3af]'}`}>
                                  {formatTime(t.start_time)}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    <div className={`border rounded-lg p-4 ${
                      isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'
                    }`}>
                      <h4 className={`text-xs font-bold uppercase tracking-widest mb-3 ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>
                        Harmonic Transitions ({transitions.length})
                      </h4>
                      <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                        {transitions.map((tr, idx) => {
                          const id = tr.id ?? `transition-${idx}`;
                          const selected = selection?.kind === 'transition' && selection.id === id;
                          return (
                            <div
                              key={id}
                              data-testid="transition-card"
                              onClick={() => {
                                setSelection({ kind: 'transition', id });
                                seekTo(tr.start_time);
                              }}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter' || e.key === ' ') {
                                  e.preventDefault();
                                  setSelection({ kind: 'transition', id });
                                  seekTo(tr.start_time);
                                }
                              }}
                              role="button"
                              tabIndex={0}
                              aria-pressed={selected}
                              className={`p-2.5 rounded text-xs cursor-pointer border transition ${
                                selected
                                  ? 'border-[#d97706] ring-1 ring-[#d97706]'
                                  : isDark
                                    ? 'bg-[#1a1c24] hover:bg-[#20232e] border-[#292c38]'
                                    : 'bg-[#f9fafb] hover:bg-[#f3f4f6] border-[#e5e7eb]'
                              }`}
                            >
                              <div className="flex justify-between items-center">
                                <span className="font-bold text-[#ea580c] uppercase">{tr.transition_type || 'MIX'}</span>
                                <span className={`font-mono ${isDark ? 'text-[#71717a]' : 'text-[#6b7280]'}`}>{formatTime(tr.start_time)}</span>
                              </div>
                              <div className={`flex justify-between items-center mt-2 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
                                <span>
                                  Key Shift: <span className={`font-mono font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{tr.from_key || '?'} → {tr.to_key || '?'}</span>
                                </span>
                                <span className="text-[10px] px-1.5 py-0.5 bg-[#0f766e]/20 text-[#14b8a6] rounded border border-[#0f766e]/40 font-mono">
                                  {tr.harmonic_compatibility || 'Harmonic'}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                !detailLoading && !detailError && (
                  <div className={`p-12 text-center rounded-lg border ${
                    isDark ? 'bg-[#15171e] border-[#232630] text-[#71717a]' : 'bg-white border-[#e5e7eb] text-[#6b7280]'
                  }`}>
                    Select a mix from the archive to inspect its waveform, engine transition zones and analysis.
                  </div>
                )
              )}
            </div>
          </div>
        )}

        {route === 'more' && (
          <div className="space-y-6" data-testid="more-view">
            <div className={`border rounded-lg p-6 ${isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'}`}>
              <h2 className="text-xl font-bold text-[#ea580c] uppercase tracking-wide flex items-center gap-2 mb-4">
                <Wrench className="w-5 h-5" /> Sound-System Engineering & Support
              </h2>
              <p className={`text-sm leading-relaxed mb-6 ${isDark ? 'text-[#9ca3af]' : 'text-[#4b5563]'}`}>
                Mix Analyst is tailored specifically for underground sound-system culture (freetekno, hardtek, jungle, acidcore). Below are operational guidelines and troubleshooting steps for continuous DJ mix analysis and hardware compliance.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className={`p-4 rounded-lg border ${isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]'}`}>
                  <h3 className="font-bold text-sm text-[#ea580c] mb-2 flex items-center gap-2">
                    <Volume2 className="w-4 h-4" /> EBU R128 Loudness Targets
                  </h3>
                  <p className={`text-xs leading-relaxed ${isDark ? 'text-[#9ca3af]' : 'text-[#4b5563]'}`}>
                    For outdoor freetekno speaker stacks, master target is <strong>-14.0 LUFS</strong> Integrated with True Peak capped at <strong>-0.5 dBTP</strong> to avoid DAC inter-sample clipping on high-powered amplifiers.
                  </p>
                </div>

                <div className={`p-4 rounded-lg border ${isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]'}`}>
                  <h3 className="font-bold text-sm text-[#14b8a6] mb-2 flex items-center gap-2">
                    <Layers className="w-4 h-4" /> Demucs 4-Stem GPU Processing
                  </h3>
                  <p className={`text-xs leading-relaxed ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
                    Stem separation requires CUDA or Apple Silicon acceleration. On CPU workers, 30-minute sets process in ~180s using multi-threaded PyTorch chunking.
                  </p>
                </div>

                <div className={`p-4 rounded-lg border ${isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]'}`}>
                  <h3 className="font-bold text-sm text-[#f59e0b] mb-2 flex items-center gap-2">
                    <Radio className="w-4 h-4" /> AzuraCast Sync Protocol
                  </h3>
                  <p className={`text-xs leading-relaxed ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
                    Dynamic cue sheets sync automatically over WebSocket/REST webhooks to inject upcoming artist tags and energy transitions to 24/7 web radio streams.
                  </p>
                </div>
              </div>
            </div>

            <div className={`border rounded-lg p-6 ${isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'}`}>
              <h3 className="text-base font-bold text-white mb-3">Community & Issue Reporting</h3>
              <p className={`text-xs ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'} mb-4`}>
                Need assistance with custom audio processing pipelines, container deployments, or station webhooks? Open an issue on GitHub:
              </p>
              <a
                href="https://github.com/murphieslaw23/mix-analyst/issues"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 min-h-[44px] bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold rounded"
              >
                GitHub Issue Tracker <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
            <div className={`border rounded-lg p-6 space-y-6 ${isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'}`}>
              <div>
                <h2 className="text-xl font-black text-[#ea580c] uppercase tracking-wide mb-1">
                  Impressum (Legal Notice)
                </h2>
                <p className={`text-xs font-mono ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>
                  Angaben gemäß § 5 TMG / Telemediengesetz
                </p>
              </div>

              <div className={`text-xs leading-relaxed space-y-3 ${isDark ? 'text-[#cbd5e1]' : 'text-[#374151]'}`}>
                <div>
                  <strong className="text-[#ea580c]">Betreiber & Verantwortlicher:</strong><br />
                  Erik Milach (Murphies Law)<br />
                  SYSTEM CORRUPT / SYCO23 Sound System<br />
                  Dresden, Saxony, Germany (DE)<br />
                  Email: emilach82@gmail.com
                </div>

                <div>
                  <strong className="text-[#ea580c]">Kultur- und Projekthinweis:</strong><br />
                  Dieses System dient der wissenschaftlichen, technischen und künstlerischen Erforschung von DSP-Audioanalyse, Stem-Separation und harmonischem Beatmatching im Rahmen der europäischen Sound-System- und Freetekno-Kultur. Es handelt sich um ein freies, nicht-kommerzielles Open-Source-Projekt.
                </div>

                <div>
                  <strong className="text-[#ea580c]">Datenschutzerklärung (DSGVO):</strong><br />
                  Es werden clientseitig keinerlei personenbezogene Tracking-Cookies oder Werbetracker gesetzt. Sämtliche Audioverarbeitungen, CUE-Exporte und FFT-Transientenanalysen verbleiben in der lokalen Applikationsumgebung bzw. im autorisierten Backend-Container.
                </div>
              </div>
            </div>
          </div>
        )}
    </AppShell>
  );
};

export default App;
