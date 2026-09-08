import { lazy, Suspense, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { hasMasteredArtifact, toAnalysisSummary } from "../../api/mixAdapters";
import { Button } from "../../components/ui/Button";
import { ErrorState } from "../../components/ui/ErrorState";
import { Skeleton } from "../../components/ui/Skeleton";
import { LIBRARY_ROUTE } from "../../app/routes";
import { ABPlayer } from "./ABPlayer";
import { useMixDetail } from "./useMixDetail";

const LazyRigPanel = lazy(() => import("../rig/RigPanel"));

function formatDuration(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(Math.max(0, Math.floor(seconds % 60))).padStart(2, "0")}`;
}

export function MixDetailPage() {
  const { mixId } = useParams();
  const { status, mix, problem, retry } = useMixDetail(mixId);
  const [rigOpen, setRigOpen] = useState(false);
  const rigButtonRef = useRef<HTMLButtonElement>(null);
  const closeRig = () => {
    setRigOpen(false);
    window.setTimeout(() => rigButtonRef.current?.focus(), 0);
  };

  if (status === "loading") return <section className="route-page mix-detail-page" aria-labelledby="page-heading"><p className="eyebrow">Your result</p><h1 id="page-heading" tabIndex={-1}>Result</h1><Skeleton label="Loading mastered result" /></section>;
  if (status === "error" || !mix) return <section className="route-page mix-detail-page" aria-labelledby="page-heading"><p className="eyebrow">Your result</p><h1 id="page-heading" tabIndex={-1}>Result unavailable</h1>{problem ? <ErrorState onRetry={retry} problem={problem} /> : null}</section>;

  const masterReady = hasMasteredArtifact(mix);
  const analysis = mix.analysisResult ? toAnalysisSummary(mix.analysisResult) : null;
  return (
    <section className="route-page mix-detail-page" aria-labelledby="page-heading">
      <Link className="back-link" to={LIBRARY_ROUTE}>Back to Library</Link>
      <p className="eyebrow">{masterReady ? "Completed master" : "Result not ready"}</p>
      <h1 id="page-heading" tabIndex={-1}>{mix.title}</h1>
      <p className="route-page__description">{mix.artist ?? mix.sourceFilename} · {formatDuration(mix.durationSeconds)} · {mix.status}</p>
      {masterReady ? <ABPlayer artifacts={mix.artifacts} sourceFilename={mix.sourceFilename} suggestedDownloadName={mix.suggestedDownloadName} /> : <section className="resource-state" aria-labelledby="master-not-ready-heading"><h2 id="master-not-ready-heading">Master not ready</h2><p>This owned audio is still waiting for a protected mastered artifact. Return to Jobs to check processing progress; playback and downloads will appear only when that artifact is available.</p><Link className="button button--secondary" to="/jobs">View Jobs</Link></section>}
      <section className="mix-metadata" aria-labelledby="mix-metadata-heading">
        <h2 id="mix-metadata-heading">Result information</h2>
        <dl>
          <div><dt>Source</dt><dd>{mix.sourceFilename}</dd></div>
          <div><dt>Duration</dt><dd>{formatDuration(mix.durationSeconds)}</dd></div>
          {analysis ? <><div><dt>Integrated loudness</dt><dd>{analysis.integratedLufs} LUFS</dd></div><div><dt>True peak</dt><dd>{analysis.truePeakDb} dBTP</dd></div><div><dt>Tempo</dt><dd>{analysis.bpm} BPM</dd></div><div><dt>Key</dt><dd>{analysis.key} · {analysis.camelotCode}</dd></div></> : <div><dt>Analysis</dt><dd>No analysis report was returned for this result.</dd></div>}
        </dl>
      </section>
      {masterReady ? <><section className="rig-launch" aria-labelledby="rig-launch-heading"><div><h2 id="rig-launch-heading">Listening rig</h2><p>Open an optional, non-strobing visual reference. Your playback is unchanged.</p></div><Button onClick={() => setRigOpen(true)} ref={rigButtonRef} tone="secondary">Open listening rig</Button></section>
      {rigOpen ? <Suspense fallback={<p className="rig-loading" role="status">Opening listening rig…</p>}><LazyRigPanel mixId={mix.id} onClose={closeRig} /></Suspense> : null}</> : null}
    </section>
  );
}
