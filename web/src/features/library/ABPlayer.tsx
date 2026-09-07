import { useEffect, useMemo, useState } from "react";
import { triggerArtifactDownload } from "../../api/artifacts";
import type { ArtifactDto } from "../../api/contracts";
import { Button } from "../../components/ui/Button";
import { usePlayer } from "./usePlayer";

type ArtifactRole = "source" | "mastered";

interface ABPlayerProps {
  artifacts: ArtifactDto[];
  sourceFilename: string;
  suggestedDownloadName: string | null;
}

function artifactFor(artifacts: ArtifactDto[], role: ArtifactRole) {
  return artifacts.find((artifact) => artifact.role === role) ?? null;
}

function labelFor(role: ArtifactRole) {
  return role === "mastered" ? "mastered" : "original";
}

export function ABPlayer({ artifacts, sourceFilename, suggestedDownloadName }: ABPlayerProps) {
  const source = useMemo(() => artifactFor(artifacts, "source"), [artifacts]);
  const mastered = useMemo(() => artifactFor(artifacts, "mastered"), [artifacts]);
  const defaultRole: ArtifactRole = "mastered";
  const [activeRole, setActiveRole] = useStateWithReset(defaultRole, `${source?.id ?? ""}:${mastered?.id ?? ""}`);
  const [downloadPending, setDownloadPending] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const activeArtifact = activeRole === "mastered" ? mastered : source;
  const { state, error, selectArtifact, playArtifact, pause } = usePlayer();

  useEffect(() => {
    if (activeArtifact) selectArtifact(activeArtifact.download_url);
  }, [activeArtifact, selectArtifact]);

  if (!mastered) {
    return <section className="ab-player resource-state" aria-labelledby="player-heading"><h2 id="player-heading">Master not ready</h2><p>This audio has not produced a protected mastered artifact yet, so it cannot be played or downloaded from the Library.</p></section>;
  }

  const activeLabel = labelFor(activeRole);
  const downloadName = activeRole === "mastered" ? suggestedDownloadName ?? `mastered-${activeArtifact?.sha256.slice(0, 12) ?? "audio"}` : sourceFilename;
  const choose = (role: ArtifactRole) => {
    const artifact = role === "mastered" ? mastered : source;
    if (!artifact) return;
    setActiveRole(role);
    setDownloadError(null);
    selectArtifact(artifact.download_url);
  };
  const download = async () => {
    if (!activeArtifact || downloadPending) return;
    setDownloadPending(true);
    setDownloadError(null);
    try {
      await triggerArtifactDownload(activeArtifact.download_url);
    } catch {
      setDownloadError(`Could not authorize the ${activeLabel} download. Reopen the operator session and try again.`);
    } finally {
      setDownloadPending(false);
    }
  };

  return (
    <section className="ab-player" aria-labelledby="player-heading">
      <div className="ab-player__heading"><div><p className="eyebrow">A/B listening</p><h2 id="player-heading">Compare the real artifacts</h2></div><span className="ab-player__status">{state === "playing" ? "Playing" : "Ready"}</span></div>
      <div className="ab-player__choices" aria-label="Audio version">
        <Button aria-pressed={activeRole === "mastered"} disabled={!mastered} onClick={() => choose("mastered")} tone="secondary">Mastered</Button>
        <Button aria-pressed={activeRole === "source"} disabled={!source} onClick={() => choose("source")} tone="secondary">Original</Button>
      </div>
      <div className="ab-player__transport">
        {state === "playing" ? <Button onClick={pause}>Pause {activeLabel} audio</Button> : <Button disabled={!activeArtifact || state === "starting"} onClick={() => activeArtifact && void playArtifact(activeArtifact.download_url)}>Play {activeLabel} audio</Button>}
        <Button disabled={!activeArtifact || downloadPending} onClick={() => void download()} tone="secondary">{downloadPending ? "Authorizing…" : `Download ${activeLabel} audio`}</Button>
      </div>
      <span className="visually-hidden">Suggested filename: {downloadName}</span>
      {error || downloadError ? <p className="ab-player__error" role="alert">{error ?? downloadError}</p> : <p className="ab-player__hint">Playback and download use a scoped media capability minted from your operator session.</p>}
    </section>
  );
}

/** Reset selection only when the server changes the actual artifacts. */
function useStateWithReset(initial: ArtifactRole, key: string) {
  const [value, setValue] = useState(initial);
  useEffect(() => setValue(initial), [initial, key]);
  return [value, setValue] as const;
}
