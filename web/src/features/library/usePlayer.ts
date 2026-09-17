import { useCallback, useEffect, useRef, useState } from 'react';

export type PlayerSource = 'original' | 'mastered';

export interface UsePlayerOptions {
  originalUrl?: string | null;
  masteredUrl?: string | null;
  initial?: PlayerSource;
}

export interface UsePlayerResult {
  audioRef: React.RefObject<HTMLAudioElement>;
  active: PlayerSource;
  setActive: (source: PlayerSource) => void;
  activeUrl: string | null;
  playing: boolean;
  error: string | null;
  play: () => Promise<void>;
  pause: () => void;
  toggle: () => void;
}

const PLAYBACK_ERROR = 'Playback needs a browser gesture or supported audio';

/**
 * Honest audio transport (Product UI Task 5).
 * - Never autoplays; playing state is set ONLY after play() resolves.
 * - A rejected play() surfaces an honest error, never fake success.
 */
export function usePlayer({
  originalUrl,
  masteredUrl,
  initial = 'original',
}: UsePlayerOptions): UsePlayerResult {
  const [active, setActive] = useState<PlayerSource>(() => {
    if (initial === 'mastered' && masteredUrl) return 'mastered';
    if (initial === 'original' && originalUrl) return 'original';
    if (originalUrl) return 'original';
    if (masteredUrl) return 'mastered';
    return initial;
  });
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const activeUrl = active === 'mastered' ? (masteredUrl ?? null) : (originalUrl ?? null);

  // Switching sources stops playback and clears transient state honestly.
  useEffect(() => {
    const el = audioRef.current;
    if (el) {
      try {
        el.pause();
      } catch {
        // Element may not be seekable yet — state reset still applies.
      }
    }
    setPlaying(false);
    setError(null);
  }, [active, activeUrl]);

  const play = useCallback(async (): Promise<void> => {
    const el = audioRef.current;
    setError(null);
    if (!el) {
      setPlaying(false);
      setError(PLAYBACK_ERROR);
      return;
    }
    // Use getAttribute: the .src property resolves empty src to the page URL.
    const src = el.getAttribute('src');
    if (!src) {
      setPlaying(false);
      setError(PLAYBACK_ERROR);
      return;
    }
    try {
      await el.play();
      setPlaying(true);
    } catch {
      setPlaying(false);
      setError(PLAYBACK_ERROR);
    }
  }, []);

  const pause = useCallback((): void => {
    const el = audioRef.current;
    if (el) {
      try {
        el.pause();
      } catch {
        // Pause is best-effort; state still settles to paused.
      }
    }
    setPlaying(false);
  }, []);

  const toggle = useCallback((): void => {
    if (playing) {
      pause();
    } else {
      void play();
    }
  }, [playing, pause, play]);

  return { audioRef, active, setActive, activeUrl, playing, error, play, pause, toggle };
}

export const PLAYER_PLAYBACK_ERROR = PLAYBACK_ERROR;

export default usePlayer;
