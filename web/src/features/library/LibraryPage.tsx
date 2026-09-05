import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorState } from "../../components/ui/ErrorState";
import { Skeleton } from "../../components/ui/Skeleton";
import { useLibraryMixes } from "./useLibraryMixes";

function formatDuration(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.max(0, Math.floor(seconds % 60));
  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

export function LibraryPage() {
  const { status, mixes, total, unmasteredMixCount, problem, retry } = useLibraryMixes();
  const completedMasterLabel = `${total} completed master${total === 1 ? "" : "s"}`;
  const emptyDescription = unmasteredMixCount > 0
    ? "Your audio is still being processed. A downloadable master will appear here once mastering creates it."
    : "Process an audio file to add a server-confirmed, downloadable master to your library.";

  return (
    <section className="route-page library-page" aria-labelledby="page-heading">
      <p className="eyebrow">Your results</p>
      <h1 id="page-heading" tabIndex={-1}>Library</h1>
      <p className="route-page__description">Completed masters appear here after the service has finished processing them.</p>
      {status === "loading" ? <Skeleton label="Loading completed masters" /> : null}
      {status === "error" && problem ? <ErrorState problem={problem} onRetry={retry} /> : null}
      {status === "ready" && total === 0 ? <EmptyState title="No completed masters yet">{emptyDescription}</EmptyState> : null}
      {status === "ready" && total > 0 ? (
        <ol className="library-list" aria-label={completedMasterLabel}>
          {mixes.map((mix) => (
            <li className="library-list__item" key={mix.id}>
              <h2>{mix.title}</h2>
              <p>{mix.artist ?? mix.sourceFilename}</p>
              <dl>
                <div><dt>Status</dt><dd>Mastered</dd></div>
                <div><dt>Duration</dt><dd>{formatDuration(mix.durationSeconds)}</dd></div>
              </dl>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
