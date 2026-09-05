import { useCallback, useEffect, useRef, useState } from "react";

export type PlayerState = "idle" | "starting" | "playing" | "error";

/**
 * A deliberately small native-audio wrapper. UI state is never optimistic:
 * `playing` is set only after the browser has resolved `audio.play()`.
 */
export function usePlayer() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const requestRef = useRef(0);
  const activePlaybackRef = useRef<{ request: number; url: string } | null>(null);
  const [state, setState] = useState<PlayerState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    const audio = new Audio();
    audio.preload = "metadata";
    audioRef.current = audio;
    const stop = () => {
      activePlaybackRef.current = null;
      setState("idle");
    };
    const fail = () => {
      const active = activePlaybackRef.current;
      if (!active || active.request !== requestRef.current || audio.src !== active.url) return;
      activePlaybackRef.current = null;
      setState("error");
      setError("Playback stopped because the audio file could not be loaded. Check the file and try again.");
    };
    audio.addEventListener("pause", stop);
    audio.addEventListener("ended", stop);
    audio.addEventListener("error", fail);
    return () => {
      requestRef.current += 1;
      audio.pause();
      audio.removeEventListener("pause", stop);
      audio.removeEventListener("ended", stop);
      audio.removeEventListener("error", fail);
      audio.src = "";
      audioRef.current = null;
    };
  }, []);

  const selectArtifact = useCallback((nextUrl: string) => {
    requestRef.current += 1;
    activePlaybackRef.current = null;
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      if (audio.src !== new URL(nextUrl, window.location.origin).href) {
        audio.src = nextUrl;
        audio.load();
      }
    }
    setUrl(nextUrl);
    setError(null);
    setState("idle");
  }, []);

  const playArtifact = useCallback(async (nextUrl: string): Promise<void> => {
    const audio = audioRef.current;
    if (!audio) return;
    const request = ++requestRef.current;
    activePlaybackRef.current = null;
    setError(null);
    setState("starting");
    if (audio.src !== new URL(nextUrl, window.location.origin).href) {
      audio.pause();
      audio.src = nextUrl;
      audio.load();
      setUrl(nextUrl);
    }
    try {
      await audio.play();
      if (request === requestRef.current) {
        activePlaybackRef.current = { request, url: audio.src };
        setState("playing");
      }
    } catch {
      if (request === requestRef.current) {
        activePlaybackRef.current = null;
        setState("error");
        setError("Playback needs a browser gesture or supported audio. Check the file and try again.");
      }
    }
  }, []);

  const pause = useCallback(() => {
    requestRef.current += 1;
    activePlaybackRef.current = null;
    audioRef.current?.pause();
    setState("idle");
  }, []);

  return { state, error, url, selectArtifact, playArtifact, pause };
}
