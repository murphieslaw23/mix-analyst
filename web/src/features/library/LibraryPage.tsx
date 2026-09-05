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
  const { status, mixes, total, problem, retry } = useLibraryMixes();

  return (
    <section className="route-page library-page" aria-labelledby="page-heading">
      <p className="eyebrow">Your results</p>
      <h1 id="page-heading" tabIndex={-1}>Library</h1>
      <p className="route-page__description">Completed masters appear here after the service has finished processing them.</p>
      {status === "loading" ? <Skeleton label="Loading completed masters" /> : null}
      {status === "error" && problem ? <ErrorState problem={problem} onRetry={retry} /> : null}
      {status === "ready" && total === 0 ? <EmptyState title="No completed masters yet">Process an audio file to add a server-confirmed master to your library.</EmptyState> : null}
      {status === "ready" && total > 0 ? (
        <ol className="library-list" aria-label={`${total} completed masters`}>
          {mixes.map((mix) => (
            <li className="library-list__item" key={mix.id}>
              <h2>{mix.title}</h2>
              <p>{mix.artist ?? mix.sourceFilename}</p>
              <dl>
                <div><dt>Status</dt><dd>{mix.status}</dd></div>
                <div><dt>Duration</dt><dd>{formatDuration(mix.durationSeconds)}</dd></div>
              </dl>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
