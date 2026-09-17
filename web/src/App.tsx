import React, { useState, useEffect, Suspense } from 'react';
import { CheckCircle } from 'lucide-react';
import { AppShell } from './app/AppShell';
import {
  getRouteForPath,
  parseBatchDetailId,
  parseJobDetailId,
  usePathname,
} from './app/routes';

// The dashboard is the start page and stays in the initial bundle; every
// workflow surface loads lazily so first paint stays lean.
import { DashboardPage } from './features/dashboard/DashboardPage';
const LibraryPage = React.lazy(() => import('./features/library/LibraryPage'));
const PipelinePage = React.lazy(() => import('./features/pipeline/PipelinePage'));
const ProcessPage = React.lazy(() => import('./features/process/ProcessPage'));
const JobsPage = React.lazy(() => import('./features/jobs/JobsPage'));
const JobDetailPage = React.lazy(() => import('./features/jobs/JobDetailPage'));
const BatchReviewPage = React.lazy(() => import('./features/batches/BatchReviewPage'));
const BatchDetailPage = React.lazy(() => import('./features/batches/BatchDetailPage'));
const MorePage = React.lazy(() => import('./features/more/MorePage'));
const NotificationCenterPage = React.lazy(
  () => import('./features/notifications/NotificationCenterPage'),
);

/**
 * Thin application shell: theme + PWA install state live here. All route
 * data (library, mix detail, pipeline, jobs, batches, notifications) is
 * owned by the route pages and their hooks — nothing is shared through
 * hidden cross-route component state anymore.
 */
export const App: React.FC = () => {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    try {
      return (localStorage.getItem('syco_theme') as 'dark' | 'light') || 'dark';
    } catch {
      return 'dark';
    }
  });
  const pathname = usePathname();
  const route = getRouteForPath(pathname);
  const [notification, setNotification] = useState<string | null>(null);
  const [installPrompt, setInstallPrompt] = useState<any>(null);

  useEffect(() => {
    try {
      localStorage.setItem('syco_theme', theme);
    } catch {
      // storage unavailable — theme simply won't persist
    }
    if (theme === 'light') {
      document.documentElement.classList.add('light-mode');
    } else {
      document.documentElement.classList.remove('light-mode');
    }
  }, [theme]);

  useEffect(() => {
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setInstallPrompt(e);
    };
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    return () => window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
  }, []);

  const triggerInstall = async () => {
    if (!installPrompt) return;
    installPrompt.prompt();
    const { outcome } = await installPrompt.userChoice;
    if (outcome === 'accepted') {
      setInstallPrompt(null);
      setNotification('SYSTEM CORRUPT PWA installed successfully!');
      setTimeout(() => setNotification(null), 4000);
    }
  };

  const isDark = theme === 'dark';
  const routeFallback = (
    <div
      className={`p-12 text-center rounded-lg border ${isDark ? 'bg-[#15171e] border-[#232630] text-[#71717a]' : 'bg-white border-[#e5e7eb] text-[#6b7280]'}`}
      aria-busy="true"
      role="status"
    >
      Loading…
    </div>
  );
  const jobDetailId = route === 'jobDetail' ? parseJobDetailId(pathname) : null;
  const batchDetailId = route === 'batchDetail' ? parseBatchDetailId(pathname) : null;

  return (
    <AppShell
      currentPath={pathname}
      theme={theme}
      onToggleTheme={() => setTheme(isDark ? 'light' : 'dark')}
      installPrompt={installPrompt}
      onInstall={() => void triggerInstall()}
    >
      {notification && (
        <div className="fixed bottom-6 right-6 z-50 bg-[#ea580c] text-white px-5 py-3 rounded-lg shadow-xl font-medium text-xs flex items-center gap-2" role="status">
          <CheckCircle className="w-4 h-4" />
          {notification}
        </div>
      )}

      {route === 'dashboard' && <DashboardPage isDark={isDark} />}

      {route === 'library' && (
        <Suspense fallback={routeFallback}>
          <LibraryPage isDark={isDark} />
        </Suspense>
      )}

      {route === 'process' && (
        <Suspense fallback={routeFallback}>
          <PipelinePage isDark={isDark} />
        </Suspense>
      )}

      {route === 'intake' && (
        <Suspense fallback={routeFallback}>
          <ProcessPage isDark={isDark} />
        </Suspense>
      )}

      {route === 'jobs' && (
        <Suspense fallback={routeFallback}>
          <JobsPage isDark={isDark} />
        </Suspense>
      )}
      {route === 'jobDetail' && jobDetailId && (
        <Suspense fallback={routeFallback}>
          <JobDetailPage jobId={jobDetailId} isDark={isDark} />
        </Suspense>
      )}
      {route === 'batches' && (
        <Suspense fallback={routeFallback}>
          <BatchReviewPage isDark={isDark} />
        </Suspense>
      )}
      {route === 'batchDetail' && batchDetailId && (
        <Suspense fallback={routeFallback}>
          <BatchDetailPage batchId={batchDetailId} isDark={isDark} />
        </Suspense>
      )}

      {route === 'more' && (
        <Suspense fallback={routeFallback}>
          <MorePage isDark={isDark} />
        </Suspense>
      )}

      {route === 'notifications' && (
        <Suspense fallback={routeFallback}>
          <NotificationCenterPage isDark={isDark} />
        </Suspense>
      )}
    </AppShell>
  );
};

export default App;
