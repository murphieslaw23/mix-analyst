import { useEffect, useMemo, useState } from "react";
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
  const defaultRole: ArtifactRole = mastered ? "mastered" : "source";
  const [activeRole, setActiveRole] = useStateWithReset(defaultRole, `${source?.id ?? ""}:${mastered?.id ?? ""}`);
  const activeArtifact = activeRole === "mastered" ? mastered : source;
  const { state, error, selectArtifact, playArtifact, pause } = usePlayer();

  useEffect(() => {
    if (activeArtifact) selectArtifact(activeArtifact.download_url);
  }, [activeArtifact, selectArtifact]);

  if (!source && !mastered) {
    return <section className="ab-player resource-state" aria-labelledby="player-heading"><h2 id="player-heading">Playback unavailable</h2><p>This completed result has no protected audio artifact to play or download yet.</p></section>;
  }

  const activeLabel = labelFor(activeRole);
  const downloadName = activeRole === "mastered" ? suggestedDownloadName ?? `mastered-${activeArtifact?.sha256.slice(0, 12) ?? "audio"}` : sourceFilename;
  const choose = (role: ArtifactRole) => {
    const artifact = role === "mastered" ? mastered : source;
    if (!artifact) return;
    setActiveRole(role);
    selectArtifact(artifact.download_url);
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
        {activeArtifact ? <a className="button button--secondary" download={downloadName} href={activeArtifact.download_url}>Download {activeLabel} audio</a> : null}
      </div>
      {error ? <p className="ab-player__error" role="alert">{error}</p> : <p className="ab-player__hint">Playback and download use the protected {activeLabel} artifact returned by the service.</p>}
    </section>
  );
}

/** Reset selection only when the server changes the actual artifacts. */
function useStateWithReset(initial: ArtifactRole, key: string) {
  const [value, setValue] = useState(initial);
  useEffect(() => setValue(initial), [initial, key]);
  return [value, setValue] as const;
}
