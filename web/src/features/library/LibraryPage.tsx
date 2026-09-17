import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { authHeaders } from '../../api';
import { apiClient } from '../../api/client';
import { normalizeMixListResponse } from '../../api/contracts';
import { normalizeMixListItem } from '../../api/mixAdapters';
import { libraryPath, replace, useQueryParam } from '../../app/routes';
import { MixLibrary } from '../../components/MixLibrary';
import { EmptyState } from '../../components/ui/EmptyState';
import { LiveRegion } from '../../components/ui/LiveRegion';
import type { MixListItem } from '../../types';
import { MixDetailPage } from './MixDetailPage';

interface LibraryPageProps {
  isDark?: boolean;
}

/**
 * Mix archive + detail route (`/library`, selection in `?mix=`).
 *
 * The list is searchable; picking a mix updates the URL so the detail view
 * is deep-linkable and survives reloads. First visit with a non-empty
 * archive selects the first mix (URL replace, no history spam) to preserve
 * the previous start-page behavior.
 */
export const LibraryPage: React.FC<LibraryPageProps> = ({ isDark = true }) => {
  const [mixes, setMixes] = useState<MixListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setLibraryError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [liveMessage, setLiveMessage] = useState('Mix library loading.');
  const mixParam = useQueryParam('mix');

  const card = isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm';
  const input = isDark
    ? 'bg-[#0d0e12] border-[#292c38] text-neutral-200 placeholder:text-[#71717a]'
    : 'bg-[#f9fafb] border-[#d1d5db] text-neutral-800 placeholder:text-[#9ca3af]';
  const muted = isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]';

  const fetchMixes = useCallback(async () => {
    setLoading(true);
    setLibraryError(null);
    try {
      const raw: unknown = await apiClient<unknown>('/mixes', {
        headers: (() => {
          try {
            return { ...authHeaders() };
          } catch {
            return {};
          }
        })(),
      });
      const page = normalizeMixListResponse(raw);
      const items = page.items.map(normalizeMixListItem);
      setMixes(items);
      setLiveMessage(`Mix library loaded. ${items.length} sets.`);
    } catch {
      setLibraryError('Backend unreachable. Check that the API is running, then retry.');
      setLiveMessage('Mix library could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchMixes();
  }, [fetchMixes]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return mixes;
    return mixes.filter((m) =>
      `${m.title || ''} ${m.original_filename}`.toLowerCase().includes(q),
    );
  }, [mixes, query]);

  // Resolve the selection from the URL; fall back to the first mix so a
  // bare `/library` visit still shows detail (replaced, not pushed).
  const selectedId = mixParam && mixes.some((m) => m.id === mixParam) ? mixParam : null;
  useEffect(() => {
    if (!loading && !error && mixes.length > 0 && !selectedId) {
      replace(libraryPath(mixes[0].id));
    }
  }, [loading, error, mixes, selectedId]);

  const handleSelect = useCallback((mixId: string) => {
    // Same-document navigation: update the query without refetching the list.
    replace(libraryPath(mixId));
    // `replace` dispatches popstate so useQueryParam subscribers update.
  }, []);

  return (
    <div className="space-y-6" data-testid="library-view">
      <LiveRegion message={liveMessage} />
      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 md:col-span-3 space-y-4">
          <div className={`border rounded-lg p-3 ${card}`}>
            <label htmlFor="library-search" className={`block text-[10px] font-bold uppercase tracking-widest mb-1.5 ${muted}`}>
              Filter sets
            </label>
            <input
              id="library-search"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Title or filename…"
              data-testid="library-search"
              className={`w-full px-2.5 py-2 min-h-[44px] rounded border text-xs ${input}`}
            />
            {query.trim() && (
              <p className={`text-[11px] font-mono mt-1.5 ${muted}`} role="status">
                {filtered.length} of {mixes.length} shown
              </p>
            )}
          </div>
          <MixLibrary
            mixes={filtered}
            selectedId={selectedId}
            loading={loading}
            error={error}
            onSelect={handleSelect}
            onRetry={fetchMixes}
            isDark={isDark}
          />
        </div>

        <div className="col-span-12 md:col-span-9">
          {!loading && !error && mixes.length > 0 && selectedId && (
            <MixDetailPage key={selectedId} mixId={selectedId} isDark={isDark} />
          )}
          {!loading && !error && mixes.length > 0 && !selectedId && (
            <div
              className={`p-12 text-center rounded-lg border ${isDark ? 'bg-[#15171e] border-[#232630] text-[#71717a]' : 'bg-white border-[#e5e7eb] text-[#6b7280]'}`}
            >
              Select a mix from the archive to inspect its waveform, engine transition zones and analysis.
            </div>
          )}
          {!loading && !error && mixes.length === 0 && (
            <div
              className={`p-12 text-center rounded-lg border ${isDark ? 'bg-[#15171e] border-[#232630] text-[#71717a]' : 'bg-white border-[#e5e7eb] text-[#6b7280]'}`}
            >
              <EmptyState
                title="No mixes yet."
                description="Upload a long set to start engine analysis."
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default LibraryPage;
