/**
 * Mix detail state (extracted from the former App god-component).
 *
 * Owns one mix's detail lifecycle: detail fetch, peaks, engine analysis,
 * transport (play/pause/seek/cue jumps over a caller-rendered <audio>
 * element), waveform zoom, and region selection. The selected mix id itself
 * lives in the URL (`/library?mix=:id`) — this hook only loads what it is
 * given, so detail views are deep-linkable and survive reloads.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { authHeaders } from '../../api';
import { apiClient } from '../../api/client';
import {
  normalizeAnalysis,
  normalizeMixDetail,
} from '../../api/mixAdapters';
import type {
  AnalysisSummary,
  MixDetail,
  RegionSelection,
  ZoomWindow,
} from '../../types';

export const FULL_ZOOM: ZoomWindow = { start: 0, end: 1 };
const PEAK_BUCKETS = 1200;

function mutationHeaders(): Record<string, string> {
  try {
    return authHeaders();
  } catch {
    return {};
  }
}

export interface UseMixDetailResult {
  mix: MixDetail | null;
  detailLoading: boolean;
  detailError: string | null;
  analysis: AnalysisSummary | null;
  analysisLoading: boolean;
  analysisError: string | null;
  peaks: number[] | null;
  isPlaying: boolean;
  currentTime: number;
  zoom: ZoomWindow;
  selection: RegionSelection;
  audioRef: React.RefObject<HTMLAudioElement>;
  setZoom: (zoom: ZoomWindow) => void;
  setSelection: (selection: RegionSelection) => void;
  setIsPlaying: (playing: boolean) => void;
  setCurrentTime: (time: number) => void;
  togglePlayback: () => void;
  seekTo: (time: number) => void;
  jumpToCue: (direction: 'next' | 'prev') => void;
  reload: () => void;
}

export function useMixDetail(mixId: string | null): UseMixDetailResult {
  const [mix, setMix] = useState<MixDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisSummary | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [peaks, setPeaks] = useState<number[] | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [zoom, setZoom] = useState<ZoomWindow>(FULL_ZOOM);
  const [selection, setSelection] = useState<RegionSelection>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!mixId) {
      setMix(null);
      setDetailError(null);
      setDetailLoading(false);
      setAnalysis(null);
      setPeaks(null);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    setDetailError(null);
    setAnalysis(null);
    setAnalysisLoading(true);
    setAnalysisError(null);
    setPeaks(null);
    setZoom(FULL_ZOOM);
    setSelection(null);
    setCurrentTime(0);
    setIsPlaying(false);

    void (async () => {
      try {
        const [detailRaw, peaksRaw, analysisRaw] = await Promise.all([
          apiClient<unknown>(`/mixes/${encodeURIComponent(mixId)}`, {
            headers: { ...mutationHeaders() },
          }),
          apiClient<{ peaks?: unknown }>(
            `/mixes/${encodeURIComponent(mixId)}/peaks?buckets=${PEAK_BUCKETS}`,
            { headers: { ...mutationHeaders() } },
          ).catch(() => null),
          apiClient<unknown>(`/mixes/${encodeURIComponent(mixId)}/analysis`, {
            headers: { ...mutationHeaders() },
          }).catch((err: unknown) => ({ __error: err })),
        ]);
        if (cancelled) return;
        setMix(normalizeMixDetail(detailRaw));
        if (audioRef.current) {
          try {
            audioRef.current.currentTime = 0;
            audioRef.current.pause();
          } catch {
            // audio not yet seekable — position state still updates
          }
        }
        const list = peaksRaw?.peaks;
        setPeaks(Array.isArray(list) && list.length > 0 ? (list as number[]) : null);
        if (
          analysisRaw &&
          typeof analysisRaw === 'object' &&
          '__error' in (analysisRaw as Record<string, unknown>)
        ) {
          const problem = (analysisRaw as { __error: { status?: number } }).__error;
          if (problem?.status === 404) {
            setAnalysis(null);
          } else {
            setAnalysisError('Engine analysis could not be loaded for this mix.');
          }
        } else {
          setAnalysis(normalizeAnalysis(analysisRaw));
        }
      } catch {
        if (!cancelled) {
          setDetailError(
            'Could not load this mix. It may have been deleted — retry or pick another set.',
          );
        }
      } finally {
        if (!cancelled) {
          setDetailLoading(false);
          setAnalysisLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [mixId, reloadToken]);

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

  const jumpToCue = useCallback(
    (direction: 'next' | 'prev') => {
      if (!mix) return;
      const cues = (mix.tracks || []).map((t) => t.start_time).sort((a, b) => a - b);
      if (cues.length === 0) return;
      // Read live position from the element when audio is present.
      const pos = audioRef.current?.getAttribute('src')
        ? audioRef.current.currentTime
        : currentTime;
      if (direction === 'next') {
        const target = cues.find((c) => c > pos + 1.0);
        seekTo(target !== undefined ? target : cues[0]);
      } else {
        const target = [...cues].reverse().find((c) => c < pos - 1.0);
        seekTo(target !== undefined ? target : 0);
      }
    },
    [mix, currentTime, seekTo],
  );

  const reload = useCallback(() => setReloadToken((t) => t + 1), []);

  return {
    mix,
    detailLoading,
    detailError,
    analysis,
    analysisLoading,
    analysisError,
    peaks,
    isPlaying,
    currentTime,
    zoom,
    selection,
    audioRef,
    setZoom,
    setSelection,
    setIsPlaying,
    setCurrentTime,
    togglePlayback,
    seekTo,
    jumpToCue,
    reload,
  };
}

export default useMixDetail;
