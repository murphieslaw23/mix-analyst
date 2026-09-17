import React from 'react';
import { formatBpm } from '../audio/format';
import type { AnalysisSummary } from '../types';

interface AnalysisPanelProps {
  analysis: AnalysisSummary | null;
  loading: boolean;
  error: string | null;
  selectedQualityId: string | null;
  onSelectQuality: (id: string | null) => void;
  isDark: boolean;
}

function Metric({
  label,
  value,
  sub,
  isDark,
}: {
  label: string;
  value: string;
  sub?: string;
  isDark: boolean;
}) {
  return (
    <div
      className={`p-3 rounded-lg border ${
        isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]'
      }`}
    >
      <div className={`text-[10px] font-bold uppercase tracking-widest ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>
        {label}
      </div>
      <div className={`mt-1 text-lg font-bold font-mono ${isDark ? 'text-white' : 'text-gray-900'}`}>{value}</div>
      {sub && <div className={`text-[11px] font-mono ${isDark ? 'text-[#71717a]' : 'text-[#9ca3af]'}`}>{sub}</div>}
    </div>
  );
}

/** Engine analysis results: tempo/key/loudness estimates plus quality flags. */
export const AnalysisPanel: React.FC<AnalysisPanelProps> = ({
  analysis,
  loading,
  error,
  selectedQualityId,
  onSelectQuality,
  isDark,
}) => {
  if (loading) {
    return (
      <div
        className={`border rounded-lg p-4 ${isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb]'}`}
        aria-busy="true"
      >
        <p className={`text-xs font-mono ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>Loading engine analysis…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div
        className={`border rounded-lg p-4 ${isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb]'}`}
        role="alert"
      >
        <p className="text-xs font-semibold text-red-400">Analysis unavailable</p>
        <p className={`text-xs mt-1 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>{error}</p>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div
        className={`border rounded-lg p-4 ${isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb]'}`}
      >
        <h4 className={`text-xs font-bold uppercase tracking-widest ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>
          Engine Analysis
        </h4>
        <p className={`text-xs mt-2 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
          No analysis published for this mix yet. Dispatch an analysis job from Pipeline &amp; Broadcast.
        </p>
      </div>
    );
  }

  const findings = analysis.quality_findings ?? [];

  return (
    <div
      className={`border rounded-lg p-4 ${isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'}`}
    >
      <h4 className={`text-xs font-bold uppercase tracking-widest mb-3 ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>
        Engine Analysis
      </h4>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-2">
        <Metric label="Tempo" value={formatBpm(analysis.primary_bpm)} sub={analysis.bpm_confidence !== undefined ? `conf ${(analysis.bpm_confidence * 100).toFixed(0)}%` : undefined} isDark={isDark} />
        <Metric
          label="Key / Camelot"
          value={analysis.camelot_code ?? analysis.detected_key ?? '—'}
          sub={analysis.key_confidence !== undefined ? `conf ${(analysis.key_confidence * 100).toFixed(0)}%` : analysis.detected_key}
          isDark={isDark}
        />
        <Metric
          label="Integrated LUFS"
          value={analysis.integrated_lufs !== undefined ? analysis.integrated_lufs.toFixed(1) : '—'}
          sub={analysis.loudness_range_lra !== undefined ? `LRA ${analysis.loudness_range_lra.toFixed(1)} LU` : undefined}
          isDark={isDark}
        />
        <Metric
          label="True Peak"
          value={analysis.true_peak_db !== undefined ? `${analysis.true_peak_db.toFixed(1)} dBTP` : '—'}
          isDark={isDark}
        />
        <Metric label="BPM Candidates" value={String(analysis.bpm_candidates?.length ?? 0)} isDark={isDark} />
        <Metric label="Quality Flags" value={String(findings.length)} isDark={isDark} />
      </div>

      {(analysis.bpm_candidates?.length ?? 0) > 0 && (
        <div className="mt-3">
          <h5 className={`text-[10px] font-bold uppercase tracking-widest mb-1 ${isDark ? 'text-[#71717a]' : 'text-[#9ca3af]'}`}>
            Tempo candidates
          </h5>
          <ul className="flex flex-wrap gap-1.5">
            {analysis.bpm_candidates!.slice(0, 5).map((c, i) => (
              <li
                key={i}
                className="text-[11px] font-mono px-2 py-0.5 rounded border border-[#ea580c]/30 bg-[#ea580c]/10 text-[#ea580c]"
              >
                {c.bpm.toFixed(1)} ({(c.confidence * 100).toFixed(0)}%)
              </li>
            ))}
          </ul>
        </div>
      )}

      {findings.length > 0 && (
        <div className="mt-3">
          <h5 className={`text-[10px] font-bold uppercase tracking-widest mb-1 ${isDark ? 'text-[#71717a]' : 'text-[#9ca3af]'}`}>
            Quality flags — select to highlight on waveform
          </h5>
          <ul className="space-y-1.5">
            {findings.map((q, i) => {
              const id = `q-${i}`;
              const selected = selectedQualityId === id;
              return (
                <li key={id}>
                  <button
                    onClick={() => onSelectQuality(selected ? null : id)}
                    aria-pressed={selected}
                    className={`w-full text-left p-2 rounded border text-xs transition ${
                      selected
                        ? 'border-[#a855f7] bg-[#a855f7]/10'
                        : isDark
                          ? 'bg-[#1a1c24] border-[#292c38] hover:border-[#4b5563]'
                          : 'bg-[#f9fafb] border-[#e5e7eb] hover:border-[#cbd5e1]'
                    }`}
                  >
                    <span className={`font-mono font-bold ${isDark ? 'text-[#d8b4fe]' : 'text-[#7e22ce]'}`}>
                      [{q.severity}] {q.type}
                    </span>
                    <span className={`block mt-0.5 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>{q.description}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
};
