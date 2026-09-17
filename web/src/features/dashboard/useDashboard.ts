/**
 * Dashboard overview client: light aggregate reads only.
 *
 * The dashboard is the start page, so it must stay cheap: one mixes list,
 * one notifications list, and a bounded per-mix jobs fan-out (at most
 * DASHBOARD_MIX_FANOUT mixes — the backend exposes jobs per mix only).
 * Every source degrades independently: a failing source hides its section
 * instead of failing the whole view.
 */
import { useCallback, useEffect, useState } from 'react';
import { authHeaders } from '../../api';
import { apiClient } from '../../api/client';
import { normalizeMixListResponse } from '../../api/contracts';
import { normalizeMixListItem } from '../../api/mixAdapters';
import type { MixListItem } from '../../types';
import type { NotificationItem } from '../notifications/useNotifications';
import { jobProblemMessage, type JobViewModel } from '../jobs/useJobEvents';

const DASHBOARD_MIX_FANOUT = 5;

const TERMINAL_JOB = new Set(['SUCCEEDED', 'FAILED', 'CANCELLED']);

function mutationHeaders(): Record<string, string> {
  try {
    return authHeaders();
  } catch {
    return {};
  }
}

export type DashboardPhase = 'loading' | 'ready' | 'error';

export interface DashboardAttentionJob extends JobViewModel {
  mixLabel: string;
}

export interface UseDashboardResult {
  phase: DashboardPhase;
  error: string | null;
  mixes: MixListItem[];
  mixesTotal: number;
  activeJobs: DashboardAttentionJob[];
  failedJobs: DashboardAttentionJob[];
  unreadNotifications: NotificationItem[];
  unreadCount: number;
  liveMessage: string;
  refresh: () => void;
}

export function useDashboard(): UseDashboardResult {
  const [phase, setPhase] = useState<DashboardPhase>('loading');
  const [error, setError] = useState<string | null>(null);
  const [mixes, setMixes] = useState<MixListItem[]>([]);
  const [mixesTotal, setMixesTotal] = useState(0);
  const [activeJobs, setActiveJobs] = useState<DashboardAttentionJob[]>([]);
  const [failedJobs, setFailedJobs] = useState<DashboardAttentionJob[]>([]);
  const [unreadNotifications, setUnreadNotifications] = useState<NotificationItem[]>([]);
  const [liveMessage, setLiveMessage] = useState('Dashboard loading.');

  const load = useCallback(async () => {
    setPhase('loading');
    setError(null);
    try {
      const raw: unknown = await apiClient<unknown>('/mixes', {
        headers: { ...mutationHeaders() },
      });
      const page = normalizeMixListResponse(raw);
      const items = page.items.map(normalizeMixListItem);
      setMixes(items);
      setMixesTotal(page.total);

      // Independent secondary sources: never fail the dashboard.
      const [jobsSettled, notifSettled] = await Promise.all([
        Promise.allSettled(
          items.slice(0, DASHBOARD_MIX_FANOUT).map((mix) =>
            apiClient<JobViewModel[]>(`/mixes/${encodeURIComponent(mix.id)}/jobs`, {
              headers: { ...mutationHeaders() },
            }).then((jobs) => ({ mix, jobs: Array.isArray(jobs) ? jobs : [] })),
          ),
        ),
        Promise.allSettled([
          apiClient<NotificationItem[]>('/notifications', {
            headers: { ...mutationHeaders() },
          }),
        ]),
      ]);

      const active: DashboardAttentionJob[] = [];
      const failed: DashboardAttentionJob[] = [];
      for (const result of jobsSettled) {
        if (result.status !== 'fulfilled') continue;
        const { mix, jobs } = result.value;
        const mixLabel = mix.title || mix.original_filename;
        for (const job of jobs) {
          const status = (job.status || '').toUpperCase();
          if (TERMINAL_JOB.has(status)) {
            if (status === 'FAILED') failed.push({ ...job, mixLabel });
          } else {
            active.push({ ...job, mixLabel });
          }
        }
      }
      setActiveJobs(active);
      setFailedJobs(failed);

      const notifResult = notifSettled[0];
      if (notifResult.status === 'fulfilled' && Array.isArray(notifResult.value)) {
        const unread = notifResult.value.filter(
          (n) => !n.read_at && (n.status || '').toLowerCase() === 'unread',
        );
        setUnreadNotifications(unread);
      } else {
        setUnreadNotifications([]);
      }

      setPhase('ready');
      setLiveMessage(
        `Dashboard loaded. ${page.total} sets, ${active.length} active jobs, ${failed.length} failed jobs.`,
      );
    } catch (err) {
      setError(jobProblemMessage(err));
      setPhase('error');
      setLiveMessage('Dashboard could not be loaded.');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return {
    phase,
    error,
    mixes,
    mixesTotal,
    activeJobs,
    failedJobs,
    unreadNotifications,
    unreadCount: unreadNotifications.length,
    liveMessage,
    refresh: load,
  };
}

export default useDashboard;
