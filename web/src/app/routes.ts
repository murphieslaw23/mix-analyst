/**
 * Product routes for the Mix Analyst PWA.
 *
 * Information architecture:
 * - DASHBOARD_ROUTE ('/') is the start page: engine status, quick actions,
 *   recent sets, and items needing attention. It never fetches heavy detail.
 * - LIBRARY_ROUTE ('/library') is the mix archive + detail analyzer surface
 *   (MixLibrary + WaveformDetail + AnalysisPanel). The selected mix lives in
 *   the `?mix=` query param so detail views are deep-linkable, shareable,
 *   and survive reloads/back-button (previously selection was hidden
 *   component state on `/`).
 * - PROCESS_INTAKE_ROUTE ('/process') is the single guided upload journey
 *   (reducer-first upload state machine). It is the ONLY upload
 *   implementation; the Pipeline surface links here instead of duplicating
 *   the chunked-upload form.
 * - PROCESS_ROUTE ('/pipeline') is per-mix pipeline & broadcast operations
 *   (jobs, mastering, stems, sidechain, broadcast). The target mix also
 *   lives in `?mix=` with a picker fallback — previously it depended on
 *   hidden selection state owned by the `/` route, so direct visits showed
 *   a dead "select a mix first" panel.
 * - JOBS_ROUTE ('/jobs') lists engine jobs per mix (`?mix=`) with a picker
 *   fallback; detail routes are matched by prefix.
 * - MORE_ROUTE ('/more') aggregates secondary destinations: notification
 *   center entry, settings (API key), support docs, and legal.
 *
 * Routing is history-API based (no react-router dependency): navigation uses
 * pushState + popstate, and every route is served by index.html (vite dev
 * fallback + nginx fallback), so direct `page.goto(route)` works.
 */
import { useSyncExternalStore } from 'react';

export const DASHBOARD_ROUTE = '/';
export const LIBRARY_ROUTE = '/library';
export const PROCESS_ROUTE = '/pipeline';
export const JOBS_ROUTE = '/jobs';
export const MORE_ROUTE = '/more';

/** In-page anchor for the Analysis Jobs section of the Pipeline surface. */
export const JOBS_ANCHOR = `${PROCESS_ROUTE}#jobs`;

/**
 * Upload journey (reducer-first) + batch review (deep-linkable workflow
 * surfaces). Detail routes are matched by prefix — see parseJobDetailId /
 * parseBatchDetailId.
 */
export const PROCESS_INTAKE_ROUTE = '/process';
export const BATCHES_ROUTE = '/batches';

/** Notification center route (PWA plan Tasks 3-4 frontend). */
export const NOTIFICATIONS_ROUTE = '/more/notifications';

export type AppRouteKey =
  | 'dashboard'
  | 'library'
  | 'process'
  | 'jobs'
  | 'more'
  | 'notifications'
  | 'intake'
  | 'jobDetail'
  | 'batches'
  | 'batchDetail';

export interface AppRouteDef {
  key: AppRouteKey;
  path: string;
  label: string;
}

/**
 * Primary navigation. Labels stay short on purpose: the bar is a mobile
 * bottom nav (thumb reach, 44px targets) that becomes a desktop rail.
 * Batches and Notifications stay one tap away via the Dashboard quick
 * actions, the Jobs page, and the More section — they are workflow
 * destinations, not top-level tabs.
 */
export const APP_ROUTES: AppRouteDef[] = [
  { key: 'dashboard', path: DASHBOARD_ROUTE, label: 'Dashboard' },
  { key: 'library', path: LIBRARY_ROUTE, label: 'Library' },
  { key: 'intake', path: PROCESS_INTAKE_ROUTE, label: 'Process' },
  { key: 'process', path: PROCESS_ROUTE, label: 'Pipeline' },
  { key: 'jobs', path: JOBS_ROUTE, label: 'Jobs' },
  { key: 'more', path: MORE_ROUTE, label: 'More' },
];

/** Strip query + hash and trailing slash (except root) for route matching. */
export function normalizePath(path: string): string {
  if (!path) return DASHBOARD_ROUTE;
  const withoutQuery = path.split('#')[0].split('?')[0];
  if (withoutQuery.length > 1 && withoutQuery.endsWith('/')) {
    return withoutQuery.slice(0, -1);
  }
  return withoutQuery || DASHBOARD_ROUTE;
}

/** Map a pathname to its route key; unknown paths fall back to dashboard. */
export function getRouteForPath(pathname: string): AppRouteKey {
  const clean = normalizePath(pathname);
  if (clean === NOTIFICATIONS_ROUTE) return 'notifications';
  if (clean === PROCESS_ROUTE) return 'process';
  if (clean === JOBS_ROUTE) return 'jobs';
  if (clean === MORE_ROUTE) return 'more';
  if (clean === PROCESS_INTAKE_ROUTE) return 'intake';
  if (clean === BATCHES_ROUTE) return 'batches';
  if (clean === LIBRARY_ROUTE) return 'library';
  if (parseJobDetailId(clean) !== null) return 'jobDetail';
  if (parseBatchDetailId(clean) !== null) return 'batchDetail';
  return 'dashboard';
}

/** Deep link for one job's progress/recovery view. */
export function jobDetailPath(jobId: string): string {
  return `${JOBS_ROUTE}/${jobId}`;
}

/** Deep link for one batch aggregate view. */
export function batchDetailPath(batchId: string): string {
  return `${BATCHES_ROUTE}/${batchId}`;
}

/** Deep link for the library, optionally with a mix selected. */
export function libraryPath(mixId?: string): string {
  return mixId ? `${LIBRARY_ROUTE}?mix=${encodeURIComponent(mixId)}` : LIBRARY_ROUTE;
}

/** Deep link for pipeline ops, optionally scoped to a mix. */
export function pipelinePath(mixId?: string): string {
  return mixId ? `${PROCESS_ROUTE}?mix=${encodeURIComponent(mixId)}` : PROCESS_ROUTE;
}

/** Extract the job id from `/jobs/:jobId`; null for anything else. */
export function parseJobDetailId(pathname: string): string | null {
  const clean = normalizePath(pathname);
  const prefix = `${JOBS_ROUTE}/`;
  if (!clean.startsWith(prefix) || clean.length <= prefix.length) return null;
  const rest = clean.slice(prefix.length);
  if (rest.includes('/') || rest.length === 0) return null;
  try {
    return decodeURIComponent(rest);
  } catch {
    return rest;
  }
}

/** Extract the batch id from `/batches/:batchId`; null for anything else. */
export function parseBatchDetailId(pathname: string): string | null {
  const clean = normalizePath(pathname);
  const prefix = `${BATCHES_ROUTE}/`;
  if (!clean.startsWith(prefix) || clean.length <= prefix.length) return null;
  const rest = clean.slice(prefix.length);
  if (rest.includes('/') || rest.length === 0) return null;
  try {
    return decodeURIComponent(rest);
  } catch {
    return rest;
  }
}

/** Human-readable title for the current pathname (for live announcements). */
export function routeTitle(pathname: string): string {
  switch (getRouteForPath(pathname)) {
    case 'dashboard':
      return 'Dashboard';
    case 'library':
      return 'Mix Library & Detail';
    case 'process':
      return 'Pipeline & Broadcast';
    case 'jobs':
      return 'Jobs';
    case 'jobDetail':
      return 'Job detail';
    case 'intake':
      return 'Process audio';
    case 'batches':
      return 'Batch review';
    case 'batchDetail':
      return 'Batch detail';
    case 'more':
      return 'More';
    case 'notifications':
      return 'Notifications';
    default:
      return 'Dashboard';
  }
}

export function isActivePath(currentPathname: string, targetPath: string): boolean {
  const current = normalizePath(currentPathname);
  const target = normalizePath(targetPath);
  if (current === target) return true;
  // Detail views keep their section nav highlighted (e.g. /jobs/:id -> Jobs).
  if (target === JOBS_ROUTE && current.startsWith(`${JOBS_ROUTE}/`)) return true;
  if (target === BATCHES_ROUTE && current.startsWith(`${BATCHES_ROUTE}/`)) return true;
  // Notification center keeps the More section highlighted.
  if (target === MORE_ROUTE && current === NOTIFICATIONS_ROUTE) return true;
  return false;
}

/** SPA navigation: pushState + popstate so usePathname subscribers update. */
export function navigate(path: string): void {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

/**
 * Same as navigate but replaces the entry (no history spam for derived
 * state such as auto-selecting the first mix in the library).
 */
export function replace(path: string): void {
  window.history.replaceState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

function subscribeToPathname(callback: () => void): () => void {
  window.addEventListener('popstate', callback);
  return () => window.removeEventListener('popstate', callback);
}

function pathnameSnapshot(): string {
  return window.location.pathname || DASHBOARD_ROUTE;
}

/** Current pathname (no search/hash), updated on back/forward + navigate(). */
export function usePathname(): string {
  const full = useSyncExternalStore(
    subscribeToPathname,
    pathnameSnapshot,
    () => DASHBOARD_ROUTE,
  );
  return normalizePath(full);
}

function searchSnapshot(): string {
  return typeof window === 'undefined' ? '' : window.location.search || '';
}

/** Current query string, updated on back/forward + navigate(). */
export function useSearchString(): string {
  return useSyncExternalStore(subscribeToPathname, searchSnapshot, () => '');
}

/** Single query param (e.g. `mix` on /library?mix=:id); null when absent. */
export function useQueryParam(name: string): string | null {
  const search = useSearchString();
  try {
    return new URLSearchParams(search).get(name);
  } catch {
    return null;
  }
}
