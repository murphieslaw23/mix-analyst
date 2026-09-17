import React from 'react';
import { usePlayer, type PlayerSource } from './usePlayer';

interface ABPlayerProps {
  originalUrl?: string | null;
  masteredUrl?: string | null;
  mixId: string;
  isDark?: boolean;
}

/**
 * Honest A/B comparison transport (Product UI Task 5).
 * - Explicit Original/Mastered selection with aria-pressed.
 * - REAL <audio> element; playing state only after play() resolves.
 * - Symbol visible labels with full accessible names so legacy
 *   `button:has-text("PLAY")` queries keep targeting the main transport.
 * - Keyboard-operable native buttons, 44px targets, no autoplay.
 */
export const ABPlayer: React.FC<ABPlayerProps> = ({
  originalUrl,
  masteredUrl,
  mixId,
  isDark = true,
}) => {
  const { audioRef, active, setActive, activeUrl, playing, error, play, pause } = usePlayer({
    originalUrl,
    masteredUrl,
    initial: masteredUrl ? 'mastered' : 'original',
  });

  const card = isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm';
  const muted = isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]';
  const switchBase =
    'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded text-xs font-bold border transition disabled:opacity-40';
  const switchActive = 'bg-[#ea580c] border-[#ea580c] text-white';
  const switchIdle = isDark
    ? 'bg-[#1f222c] border-[#374151] text-[#d1d5db] hover:bg-[#282c38]'
    : 'bg-[#f3f4f6] border-[#d1d5db] text-[#374151] hover:bg-[#e5e7eb]';
  const transport =
    'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded bg-[#ea580c] hover:bg-[#c2410c] text-white text-sm font-bold disabled:opacity-40';

  const hasOriginal = Boolean(originalUrl);
  const hasMastered = Boolean(masteredUrl);

  const select = (source: PlayerSource) => () => {
    setActive(source);
  };

  return (
    <section
      aria-label="Mastered comparison player"
      data-testid="ab-player"
      data-mix-id={mixId}
      className={`border rounded-lg p-4 ${card}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className={`text-xs font-bold uppercase tracking-widest ${muted}`}>
          A/B comparison
        </h4>
        <p className={`text-[11px] font-mono ${muted}`} data-testid="ab-current">
          {active === 'mastered' ? 'Mastered' : 'Original'}
        </p>
      </div>

      <div role="group" aria-label="Choose audio source" className="flex flex-wrap gap-2 mt-3">
        <button
          type="button"
          aria-pressed={active === 'original'}
          disabled={!hasOriginal}
          onClick={select('original')}
          className={`${switchBase} ${active === 'original' ? switchActive : switchIdle}`}
        >
          Original
        </button>
        <button
          type="button"
          aria-pressed={active === 'mastered'}
          disabled={!hasMastered}
          onClick={select('mastered')}
          className={`${switchBase} ${active === 'mastered' ? switchActive : switchIdle}`}
        >
          Mastered
        </button>
      </div>

      {!hasMastered && (
        <p className={`text-xs mt-3 ${muted}`} data-testid="ab-no-master">
          No mastered audio yet. Mastering output appears here once a completed master exists.
        </p>
      )}
      {!hasOriginal && !hasMastered && (
        <p className={`text-xs mt-2 ${muted}`}>No audio available yet.</p>
      )}

      <audio
        ref={audioRef}
        src={activeUrl ?? ''}
        preload="none"
        data-testid="ab-audio"
        data-active={active}
        onPause={() => {
          // Native pause (e.g. headset controls) settles honest state.
          // Playing is only ever set true from a resolved play().
        }}
        className="hidden"
      />

      <div className="flex flex-wrap items-center gap-2 mt-3">
        {playing ? (
          <button
            type="button"
            aria-label="Pause"
            onClick={pause}
            disabled={!activeUrl}
            className={transport}
            data-testid="ab-pause"
            title="Pause"
          >
            <span aria-hidden="true">❚❚</span>
          </button>
        ) : (
          <button
            type="button"
            aria-label={`Play ${active} audio`}
            onClick={() => void play()}
            disabled={!activeUrl}
            className={transport}
            data-testid="ab-play"
            title={`Play ${active} audio`}
          >
            <span aria-hidden="true">▶</span>
          </button>
        )}
        <p className={`text-[11px] font-mono ${muted}`} data-testid="ab-state">
          {playing ? `Playing ${active}` : `Paused ${active}`}
        </p>
      </div>

      {error && (
        <p role="alert" data-testid="ab-error" className="text-xs text-red-400 mt-2">
          {error}
        </p>
      )}
    </section>
  );
};

export default ABPlayer;
