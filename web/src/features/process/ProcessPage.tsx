import React from 'react';
import { pipelinePath, navigate } from '../../app/routes';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LiveRegion } from '../../components/ui/LiveRegion';
import { Progress } from '../../components/ui/Progress';
import { useUpload } from './useUpload';

function formatBytes(bytes: number | null): string {
  if (bytes === null || Number.isNaN(bytes)) return 'unknown size';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const ACCEPT = 'audio/*,.wav,.flac,.mp3,.ogg,.m4a,.aac,.opus,.aiff,.aif';

interface ProcessPageProps {
  isDark?: boolean;
}

/**
 * Press Plate Process journey (Task 3): one primary action per upload state,
 * honest validation, and a hand-off to Pipeline & Broadcast once the backend
 * persists the mix. Job dispatch stays in PipelinePanel for now.
 */
export const ProcessPage: React.FC<ProcessPageProps> = ({ isDark = true }) => {
  const upload = useUpload();
  const { status } = upload;

  const card = isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm';
  const input = isDark
    ? 'bg-[#0d0e12] border-[#292c38] text-neutral-200'
    : 'bg-[#f9fafb] border-[#d1d5db] text-neutral-800';
  const btnPrimary =
    'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold rounded shadow-sm disabled:opacity-50';
  const btnGhost = isDark
    ? 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#1f222c] hover:bg-[#282c38] border border-[#374151] text-[#d1d5db] text-xs font-semibold rounded'
    : 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#f3f4f6] hover:bg-[#e5e7eb] border border-[#d1d5db] text-[#374151] text-xs font-semibold rounded';
  const muted = isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]';

  const busy = status === 'initializing' || status === 'uploading' || status === 'finalizing';

  return (
    <div className="space-y-6" data-testid="process-page">
      <LiveRegion message={upload.liveMessage} />
      <div className={`border rounded-lg p-5 sm:p-6 ${card}`}>
        <h2 className="text-xl font-bold text-[#ea580c] uppercase tracking-wide">
          Process audio
        </h2>
        <p className={`text-sm leading-relaxed mt-1 ${muted}`}>
          Upload a long set for engine analysis. Files travel in 5&nbsp;MB resumable
          chunks; the mix is handed to Pipeline &amp; Broadcast once the backend
          persists it.
        </p>

        {/* IDLE — the file choice is the single primary action. */}
        {status === 'idle' && (
          <div className="mt-4 space-y-3">
            <label htmlFor="process-file-input" className={`block text-xs font-bold uppercase tracking-widest ${muted}`}>
              Choose audio
            </label>
            <input
              id="process-file-input"
              type="file"
              accept={ACCEPT}
              onChange={(e) => upload.selectFile(e.target.files?.[0] ?? null)}
              data-testid="process-file-input"
              className={`block w-full text-xs file:mr-3 file:px-4 file:py-2 file:min-h-[44px] file:rounded file:border-0 file:bg-[#ea580c] file:text-white file:text-xs file:font-bold ${isDark ? 'text-neutral-300' : 'text-neutral-600'}`}
            />
            {upload.validationError && (
              <div role="alert" className="text-xs text-red-400">
                {upload.validationError}
              </div>
            )}
          </div>
        )}

        {/* SELECTED — one primary action: Start mastering. */}
        {status === 'selected' && (
          <div className="mt-4 space-y-3">
            <p className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>
              Ready to process
            </p>
            <p className={`text-xs font-mono ${muted}`} data-testid="process-file-summary">
              {upload.fileName} · {formatBytes(upload.fileSize)}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <label className="block">
                <span className={`block text-xs font-semibold mb-1 ${muted}`}>Title (optional)</span>
                <input
                  value={upload.title}
                  onChange={(e) => upload.setTitle(e.target.value)}
                  placeholder="Set title"
                  data-testid="process-title"
                  className={`w-full px-2.5 py-2 min-h-[44px] rounded border text-xs ${input}`}
                />
              </label>
              <label className="block">
                <span className={`block text-xs font-semibold mb-1 ${muted}`}>Artist (optional)</span>
                <input
                  value={upload.artist}
                  onChange={(e) => upload.setArtist(e.target.value)}
                  placeholder="Artist"
                  data-testid="process-artist"
                  className={`w-full px-2.5 py-2 min-h-[44px] rounded border text-xs ${input}`}
                />
              </label>
            </div>
            <div className="flex flex-wrap gap-2">
              <button onClick={upload.start} className={btnPrimary} data-testid="process-start">
                Start mastering
              </button>
              <button onClick={upload.clearSelection} className={btnGhost}>
                Choose a different file
              </button>
            </div>
          </div>
        )}

        {/* INITIALIZING / UPLOADING / FINALIZING — progress + cancel only. */}
        {busy && (
          <div className="mt-4 space-y-3">
            <p className={`text-sm font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>
              {status === 'initializing' && 'Initializing upload…'}
              {status === 'uploading' && `Uploading ${upload.fileName ?? 'audio'}…`}
              {status === 'finalizing' && 'Finalizing upload…'}
            </p>
            <Progress
              value={status === 'finalizing' ? 100 : upload.progress}
              label={`Upload progress for ${upload.fileName ?? 'audio'}`}
              testId="process-progress"
              isDark={isDark}
            />
            <div className="flex flex-wrap gap-2">
              <button onClick={upload.cancel} className={btnGhost} data-testid="process-cancel">
                Cancel upload
              </button>
            </div>
          </div>
        )}

        {/* READY — hand-off to the Pipeline surface (auto-navigates too). */}
        {status === 'ready' && (
          <div className="mt-4 space-y-3">
            <p className="text-sm font-semibold text-emerald-400" role="status">
              Upload complete — mix registered{upload.mixId ? ` (${upload.mixId})` : ''}.
            </p>
            <p className={`text-xs ${muted}`}>
              Continuing to Pipeline &amp; Broadcast, where analysis jobs are dispatched
              for the persisted mix.
            </p>
            <div className="flex flex-wrap gap-2">
              <a
                href={pipelinePath(upload.mixId ?? undefined)}
                onClick={(e) => {
                  e.preventDefault();
                  navigate(pipelinePath(upload.mixId ?? undefined));
                }}
                className={`${btnPrimary} no-underline`}
                data-testid="process-go-pipeline"
              >
                Go to Pipeline &amp; Broadcast
              </a>
            </div>
          </div>
        )}

        {/* ERROR — message + single recovery action. */}
        {status === 'error' && (
          <div className="mt-4 space-y-3">
            <ErrorState
              title="Upload failed"
              message={upload.error ?? 'The upload could not be completed.'}
              onRetry={upload.retry}
              retryLabel="Try again"
              isDark={isDark}
            />
            <div className="flex flex-wrap gap-2">
              <button onClick={upload.reset} className={btnGhost}>
                Choose a different file
              </button>
            </div>
          </div>
        )}

        {/* ABORTED — cancelled, nothing uploaded-or-kept hidden. */}
        {status === 'aborted' && (
          <div className="mt-4 space-y-3">
            <EmptyState
              title="Upload cancelled."
              description="No partial audio was kept. Choose a file to start over."
            />
            <div className="flex flex-wrap gap-2">
              <button onClick={upload.reset} className={btnPrimary} data-testid="process-restart">
                Choose a different file
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ProcessPage;
