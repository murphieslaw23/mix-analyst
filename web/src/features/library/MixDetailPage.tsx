import React, { Suspense } from 'react';
import { clamp, formatTime } from '../../audio/format';
import {
  JOBS_ROUTE,
  navigate,
  pipelinePath,
} from '../../app/routes';
import { AnalysisPanel } from '../../components/AnalysisPanel';
import { WaveformDetail } from '../../components/WaveformDetail';
import { MixExports } from './MixExports';
import { useMixDetail } from './useMixDetail';

const MixResultPanel = React.lazy(() => import('./MixResultPanel'));

interface MixDetailPageProps {
  mixId: string;
  isDark?: boolean;
}

/**
 * One mix's analyzer surface: transport + zoomable engine-region waveform
 * with the region inspector directly beneath it, results & DJ exports,
 * engine analysis, and the track/transition cue lists.
 *
 * Rendered by the library route for `?mix=:id`, so every detail view is
 * deep-linkable. Pipeline ops and job history for the same mix are one
 * link away (same `?mix=` convention).
 */
export const MixDetailPage: React.FC<MixDetailPageProps> = ({ mixId, isDark = true }) => {
  const {
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
  } = useMixDetail(mixId);

  const muted = isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]';

  if (detailLoading) {
    return (
      <div
        className={`p-12 text-center rounded-lg border ${isDark ? 'bg-[#15171e] border-[#232630] text-[#71717a]' : 'bg-white border-[#e5e7eb] text-[#6b7280]'}`}
        aria-busy="true"
      >
        Loading mix detail…
      </div>
    );
  }

  if (detailError || !mix) {
    return (
      <div
        className={`p-8 rounded-lg border ${isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb]'}`}
        role="alert"
      >
        <p className="font-semibold text-red-400 text-sm">Mix detail unavailable</p>
        <p className={`text-xs mt-1 ${muted}`}>
          {detailError ?? 'This mix could not be loaded.'}
        </p>
        <button
          onClick={reload}
          className="mt-3 px-4 py-2 min-h-[44px] rounded bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold"
        >
          Retry
        </button>
      </div>
    );
  }

  const duration = mix.duration_seconds || 0;
  const tracks = mix.tracks ?? [];
  const transitions = mix.transitions ?? [];
  const qualityFindings = analysis?.quality_findings ?? [];
  const selectedQualityId = selection?.kind === 'quality' ? selection.id : null;

  const renderRegionInspector = () => {
    if (!selection) return null;

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
          <p className={`text-xs font-mono mt-1 ${muted}`}>
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
          <p className={`text-xs font-mono mt-1 ${muted}`}>
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
            <p className={`text-xs font-mono mt-1 ${muted}`}>
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

  const go = (path: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    navigate(path);
  };

  return (
    <div className="space-y-6" data-testid="mix-detail-view">
      <audio
        ref={audioRef}
        src={mix.audio_url || ''}
        onTimeUpdate={() => {
          if (audioRef.current) setCurrentTime(audioRef.current.currentTime);
        }}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
        data-testid="main-audio-player"
        className="hidden"
      />

      <div className={`border rounded-lg p-5 ${
        isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'
      }`}>
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4">
          <div>
            <h3 className={`text-lg font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>
              {mix.title || mix.original_filename}
            </h3>
            <p className={`text-xs font-mono mt-0.5 ${muted}`}>
              Position: {formatTime(currentTime)} / {formatTime(duration)}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <a
              href={pipelinePath(mix.id)}
              onClick={go(pipelinePath(mix.id))}
              className="px-3 py-1.5 min-h-[44px] inline-flex items-center bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-semibold rounded shadow-sm no-underline"
            >
              Pipeline &amp; Broadcast
            </a>
            <a
              href={`${JOBS_ROUTE}?mix=${encodeURIComponent(mix.id)}`}
              onClick={go(`${JOBS_ROUTE}?mix=${encodeURIComponent(mix.id)}`)}
              className={`px-3 py-1.5 min-h-[44px] inline-flex items-center text-xs font-semibold rounded border transition no-underline ${
                isDark
                  ? 'bg-[#1f222c] hover:bg-[#282c38] border-[#374151] text-[#d1d5db]'
                  : 'bg-[#f3f4f6] hover:bg-[#e5e7eb] border-[#d1d5db] text-[#374151]'
              }`}
            >
              Job history
            </a>
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

        {/* Region inspector sits directly under the waveform it annotates. */}
        {selection && <div className="mt-3">{renderRegionInspector()}</div>}

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

      {/* Results & DJ exports: every derived artifact of this mix in one place. */}
      <section
        aria-label="Results and exports"
        className={`border rounded-lg p-4 sm:p-5 space-y-4 ${
          isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'
        }`}
      >
        <h4 className={`text-xs font-bold uppercase tracking-widest ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>
          Results &amp; exports
        </h4>
        <MixExports mixId={mix.id} tracks={tracks} isDark={isDark} />
        <Suspense
          fallback={
            <div
              className={`p-6 text-center rounded-lg border ${isDark ? 'bg-[#1a1c24] border-[#292c38] text-[#71717a]' : 'bg-[#f9fafb] border-[#e5e7eb] text-[#6b7280]'}`}
              aria-busy="true"
              role="status"
            >
              Loading…
            </div>
          }
        >
          <MixResultPanel
            mixId={mix.id}
            originalUrl={mix.audio_url}
            isDark={isDark}
          />
        </Suspense>
      </section>

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
                <button
                  key={id}
                  type="button"
                  data-testid="track-card"
                  onClick={() => {
                    setSelection({ kind: 'track', id });
                    seekTo(t.start_time);
                  }}
                  aria-pressed={selected}
                  aria-label={`Track ${idx + 1}: ${t.title || 'Unknown Track'} by ${t.artist || 'Unknown Artist'} at ${formatTime(t.start_time)}`}
                  className={`w-full text-left p-2.5 rounded flex items-center justify-between text-xs cursor-pointer border transition min-h-[44px] ${
                    selected
                      ? 'border-[#ea580c] ring-1 ring-[#ea580c]'
                      : isDark
                        ? 'bg-[#1a1c24] hover:bg-[#20232e] border-[#292c38]'
                        : 'bg-[#f9fafb] hover:bg-[#f3f4f6] border-[#e5e7eb]'
                  }`}
                >
                  <span>
                    <span className={`block font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>
                      {idx + 1}. {t.title || 'Unknown Track'}
                    </span>
                    <span className={`block text-[11px] ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>
                      {t.artist || 'Unknown Artist'}
                    </span>
                  </span>
                  <span className="text-right shrink-0 ml-2">
                    <span className="px-1.5 py-0.5 bg-[#ea580c]/20 text-[#ea580c] rounded border border-[#ea580c]/30 text-[10px] font-mono font-bold">
                      {t.camelot_key || 'KEY'}
                    </span>
                    <span className={`block mt-1 font-mono text-[11px] ${isDark ? 'text-[#71717a]' : 'text-[#9ca3af]'}`}>
                      {formatTime(t.start_time)}
                    </span>
                  </span>
                </button>
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
                <button
                  key={id}
                  type="button"
                  data-testid="transition-card"
                  onClick={() => {
                    setSelection({ kind: 'transition', id });
                    seekTo(tr.start_time);
                  }}
                  aria-pressed={selected}
                  aria-label={`${tr.transition_type || 'Transition'} at ${formatTime(tr.start_time)}, key ${tr.from_key || '?'} to ${tr.to_key || '?'}`}
                  className={`w-full text-left p-2.5 rounded text-xs cursor-pointer border transition min-h-[44px] ${
                    selected
                      ? 'border-[#d97706] ring-1 ring-[#d97706]'
                      : isDark
                        ? 'bg-[#1a1c24] hover:bg-[#20232e] border-[#292c38]'
                        : 'bg-[#f9fafb] hover:bg-[#f3f4f6] border-[#e5e7eb]'
                  }`}
                >
                  <span className="flex justify-between items-center">
                    <span className="font-bold text-[#ea580c] uppercase">{tr.transition_type || 'MIX'}</span>
                    <span className={`font-mono ${isDark ? 'text-[#71717a]' : 'text-[#6b7280]'}`}>{formatTime(tr.start_time)}</span>
                  </span>
                  <span className={`flex justify-between items-center mt-2 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
                    <span>
                      Key Shift: <span className={`font-mono font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{tr.from_key || '?'} → {tr.to_key || '?'}</span>
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 bg-[#0f766e]/20 text-[#14b8a6] rounded border border-[#0f766e]/40 font-mono">
                      {tr.harmonic_compatibility || 'Harmonic'}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MixDetailPage;
