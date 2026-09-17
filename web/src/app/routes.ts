/**
 * Product routes for the Press Plate Intake flow (Tasks 1-2).
 *
 * Mapping notes:
 * - LIBRARY_ROUTE ('/') renders the Mix Library & Detail analyzer surface
 *   (MixLibrary + WaveformDetail + AnalysisPanel) inside App.tsx.
 * - PROCESS_ROUTE ('/pipeline') renders the Process surface, which today is
 *   the existing PipelinePanel (ingestion, analysis jobs, mastering, stems,
 *   broadcast). PipelinePanel IS the Process surface until Task 3 builds a
 *   dedicated ProcessPage with the upload state machine.
 * - JOBS_ROUTE ('/jobs') is a deep-linkable placeholder for the forthcoming
 *   Jobs list/detail experience (Task 4). Until then it renders an honest
 *   empty view that links back to the Process surface. JOBS_ANCHOR
 *   ('/pipeline#jobs') points at the Analysis Jobs section inside the
 *   Process surface for in-page deep links.
 * - MORE_ROUTE ('/more') aggregates Support & Docs plus Imprint & Privacy
 *   content (previously tabs inside App.tsx).
 *
 * Routing is history-API based (no react-router dependency): navigation uses
 * pushState + popstate, and every route is served by index.html (vite dev
 * fallback + nginx fallback), so direct `page.goto(route)` works.
 */
import { useSyncExternalStore } from 'react';

export const LIBRARY_ROUTE = '/';
export const PROCESS_ROUTE = '/pipeline';
export const JOBS_ROUTE = '/jobs';
export const MORE_ROUTE = '/more';

/** In-page anchor for the Analysis Jobs section of the Process surface. */
export const JOBS_ANCHOR = `${PROCESS_ROUTE}#jobs`;

export type AppRouteKey = 'library' | 'process' | 'jobs' | 'more';

export interface AppRouteDef {
  key: AppRouteKey;
  path: string;
  label: string;
}

export const APP_ROUTES: AppRouteDef[] = [
  { key: 'library', path: LIBRARY_ROUTE, label: 'Mix Library & Detail' },
  { key: 'process', path: PROCESS_ROUTE, label: 'Pipeline & Broadcast' },
  { key: 'jobs', path: JOBS_ROUTE, label: 'Jobs' },
  { key: 'more', path: MORE_ROUTE, label: 'More' },
];

/** Strip query + hash and trailing slash (except root) for route matching. */
export function normalizePath(path: string): string {
  if (!path) return LIBRARY_ROUTE;
  const withoutQuery = path.split('#')[0].split('?')[0];
  if (withoutQuery.length > 1 && withoutQuery.endsWith('/')) {
    return withoutQuery.slice(0, -1);
  }
  return withoutQuery || LIBRARY_ROUTE;
}

/** Map a pathname to its route key; unknown paths fall back to library. */
export function getRouteForPath(pathname: string): AppRouteKey {
  const clean = normalizePath(pathname);
  if (clean === PROCESS_ROUTE) return 'process';
  if (clean === JOBS_ROUTE) return 'jobs';
  if (clean === MORE_ROUTE) return 'more';
  return 'library';
}

/** Human-readable title for the current pathname (for live announcements). */
export function routeTitle(pathname: string): string {
  switch (getRouteForPath(pathname)) {
    case 'process':
      return 'Pipeline & Broadcast';
    case 'jobs':
      return 'Jobs';
    case 'more':
      return 'More';
    default:
      return 'Mix Library & Detail';
  }
}

export function isActivePath(currentPathname: string, targetPath: string): boolean {
  return normalizePath(currentPathname) === normalizePath(targetPath);
}

/** SPA navigation: pushState + popstate so usePathname subscribers update. */
export function navigate(path: string): void {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

function subscribeToPathname(callback: () => void): () => void {
  window.addEventListener('popstate', callback);
  return () => window.removeEventListener('popstate', callback);
}

function pathnameSnapshot(): string {
  return window.location.pathname || LIBRARY_ROUTE;
}

/** Current pathname (no search/hash), updated on back/forward + navigate(). */
export function usePathname(): string {
  const full = useSyncExternalStore(
    subscribeToPathname,
    pathnameSnapshot,
    () => LIBRARY_ROUTE,
  );
  return normalizePath(full);
}
