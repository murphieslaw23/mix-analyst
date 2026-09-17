import React, { useCallback, useEffect, useState } from 'react';
import { authHeaders } from '../../api';
import { API_BASE_URL, apiClient } from '../../api/client';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { Skeleton } from '../../components/ui/Skeleton';
import { ABPlayer } from './ABPlayer';

export interface MixArtifact {
  id: string;
  role: string;
  key: string;
  sha256: string;
  algorithm_version: string;
  media_type: string;
  byte_length: number;
  created_at: string;
}

interface MasteringMeasurements {
  integrated_lufs?: number | null;
  true_peak_db?: number | null;
}

interface MasteringReport {
  status: string;
  output_measurements?: MasteringMeasurements | null;
  input_measurements?: MasteringMeasurements | null;
}

interface MixResultPanelProps {
  mixId: string;
  originalUrl?: string | null;
  isDark?: boolean;
}

function mutationHeaders(): Record<string, string> {
  try {
    return authHeaders();
  } catch {
    return {};
  }
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return 'unknown size';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Results library panel (Product UI Task 5).
 * Mounted BELOW WaveformDetail in the mix detail route.
 * - Artifacts list from GET /mixes/:id/artifacts (honest empty/error/retry).
 * - Loudness summary slot from GET /mixes/:id/mastering-report (404 = no master yet).
 * - Honest A/B playback via ABPlayer; mastered download only when completed.
 */
export const MixResultPanel: React.FC<MixResultPanelProps> = ({
  mixId,
  originalUrl,
  isDark = true,
}) => {
  const [artifacts, setArtifacts] = useState<MixArtifact[] | null>(null);
  const [report, setReport] = useState<MasteringReport | null>(null);
  const [reportMissing, setReportMissing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const card = isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm';
  const muted = isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]';
  const row = isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]';

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await apiClient<MixArtifact[]>(`/mixes/${encodeURIComponent(mixId)}/artifacts`, {
        headers: { ...mutationHeaders() },
      });
      setArtifacts(Array.isArray(items) ? items : []);
    } catch (err) {
      const detail =
        (err as { detail?: string })?.detail ||
        (err as Error)?.message ||
        'Results could not be loaded.';
      setArtifacts(null);
      setError(detail);
      setLoading(false);
      return;
    }
    try {
      const rep = await apiClient<MasteringReport>(
        `/mixes/${encodeURIComponent(mixId)}/mastering-report`,
        { headers: { ...mutationHeaders() } },
      );
      setReport(rep);
      setReportMissing(false);
    } catch (err) {
      const status = (err as { status?: number })?.status;
      if (status === 404) {
        setReport(null);
        setReportMissing(true);
      } else {
        // Loudness is a slot: report failure never blocks the artifact list.
        setReport(null);
        setReportMissing(false);
      }
    } finally {
      setLoading(false);
    }
  }, [mixId]);

  useEffect(() => {
    setArtifacts(null);
    setReport(null);
    setReportMissing(false);
    void load();
  }, [load]);

  const masteredCompleted =
    report !== null && (report.status || '').toLowerCase() === 'completed';
  const masteredUrl = masteredCompleted
    ? `${API_BASE_URL}/mixes/${encodeURIComponent(mixId)}/mastered`
    : null;
  const output = report?.output_measurements ?? null;

  return (
    <section
      aria-label="Mastering results"
      data-testid="mix-result-panel"
      className={`border rounded-lg p-4 sm:p-5 ${card}`}
    >
      <h4 className={`text-xs font-bold uppercase tracking-widest ${muted}`}>
        Results
      </h4>

      {loading && (
        <div className="mt-3">
          <Skeleton lines={2} label="Loading results" isDark={isDark} />
        </div>
      )}

      {!loading && error && artifacts === null && (
        <div className="mt-3">
          <ErrorState
            title="Could not load results"
            message={error}
            onRetry={() => void load()}
            retryLabel="Retry results"
            isDark={isDark}
          />
        </div>
      )}

      {!loading && !error && (
        <div className="mt-3 space-y-4">
          <div
            data-testid="loudness-summary"
            className={`p-3 rounded border ${row}`}
          >
            {output &&
            (typeof output.integrated_lufs === 'number' ||
              typeof output.true_peak_db === 'number') ? (
              <p className={`text-xs font-mono ${isDark ? 'text-white' : 'text-gray-900'}`}>
                {typeof output.integrated_lufs === 'number'
                  ? `${output.integrated_lufs.toFixed(1)} LUFS`
                  : 'Loudness not measured yet.'}
                {typeof output.true_peak_db === 'number'
                  ? ` · ${output.true_peak_db.toFixed(1)} dBTP`
                  : ''}
              </p>
            ) : (
              <p className={`text-xs ${muted}`}>
                {reportMissing
                  ? 'Loudness not measured yet.'
                  : 'Loudness not measured yet.'}
              </p>
            )}
          </div>

          <ABPlayer
            originalUrl={originalUrl ?? null}
            masteredUrl={masteredUrl}
            mixId={mixId}
            isDark={isDark}
          />

          {(artifacts ?? []).length === 0 ? (
            <EmptyState
              title="No derived artifacts yet."
              description="Mastered audio and reports appear here once mastering completes."
            />
          ) : (
            <ul className="space-y-2" data-testid="artifact-list" aria-label="Derived artifacts">
              {(artifacts ?? []).map((artifact) => {
                const isMaster = /master/i.test(artifact.role || '');
                return (
                  <li
                    key={artifact.id}
                    data-testid="artifact-row"
                    className={`p-3 rounded border ${row}`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span
                        className={`text-xs font-bold font-mono ${isDark ? 'text-white' : 'text-gray-900'}`}
                      >
                        {artifact.role || 'artifact'}
                      </span>
                      <span className={`text-[11px] font-mono ${muted}`}>
                        {formatBytes(artifact.byte_length)} · {artifact.algorithm_version || 'v?'}
                      </span>
                    </div>
                    <p className={`text-[11px] font-mono mt-1 truncate ${muted}`} title={artifact.sha256}>
                      sha {String(artifact.sha256 || '').slice(0, 16)}…
                    </p>
                    {isMaster && masteredUrl ? (
                      <a
                        href={masteredUrl}
                        download
                        className="mt-2 px-3 py-1.5 min-h-[44px] inline-flex items-center text-xs font-bold rounded bg-[#ea580c] hover:bg-[#c2410c] text-white"
                      >
                        Download mastered audio
                      </a>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}

          {masteredUrl && (artifacts ?? []).length > 0 ? null : null}
          {!masteredUrl && (
            <p className={`text-xs ${muted}`} data-testid="master-empty-hint">
              No completed master found for this mix.
            </p>
          )}
        </div>
      )}
    </section>
  );
};

export default MixResultPanel;
