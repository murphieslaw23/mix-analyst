import React from 'react';
import { Sun, Moon, Download } from 'lucide-react';
import {
  APP_ROUTES,
  getRouteForPath,
  isActivePath,
  navigate,
} from './routes';
import { LiveRegion } from '../components/ui/LiveRegion';

interface AppShellProps {
  children: React.ReactNode;
  currentPath: string;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
  installPrompt: unknown;
  onInstall: () => void;
}

/**
 * Tokenized application shell: brand header, primary navigation
 * (mobile bottom bar -> desktop rail via CSS), and Outlet-style children.
 * Navigation uses history-API Links with aria-current on the active route.
 */
export const AppShell: React.FC<AppShellProps> = ({
  children,
  currentPath,
  theme,
  onToggleTheme,
  installPrompt,
  onInstall,
}) => {
  const isDark = theme === 'dark';
  // Neutral view names on purpose: the live message must not repeat visible
  // nav labels (e.g. "Pipeline & Broadcast"), otherwise text queries that
  // target the nav would also match this visually-hidden region.
  const viewName = (() => {
    switch (getRouteForPath(currentPath)) {
      case 'process':
        return 'Process';
      case 'intake':
        return 'Process audio';
      case 'jobs':
      case 'jobDetail':
        return 'Jobs';
      case 'batches':
      case 'batchDetail':
        return 'Batches';
      case 'more':
        return 'More';
      default:
        return 'Library';
    }
  })();

  return (
    <div className="app-shell app-shell-with-rail">
      <a href="#main-content" className="app-shell-skip">
        Skip to content
      </a>

      <header className="app-shell-header">
        <div className="app-shell-brand">
          <div className="app-shell-brand-badge" aria-hidden="true">
            23
          </div>
          <div>
            <h1 className="app-shell-brand-title">
              SYSTEM CORRUPT{' '}
              <span style={{ color: 'var(--text-fog)', fontWeight: 300 }}>| MIX ANALYST</span>
            </h1>
            <p className="app-shell-brand-subtitle">
              Long-Set Transition &amp; Mastering Engine
            </p>
          </div>
        </div>

        <div className="app-shell-header-actions">
          {installPrompt ? (
            <button onClick={onInstall} className="app-shell-install">
              <Download className="w-3.5 h-3.5" aria-hidden="true" /> Install App
            </button>
          ) : null}
          <button
            onClick={onToggleTheme}
            className="app-shell-theme-toggle"
            title={`Switch to ${isDark ? 'Light' : 'Dark'} Mode`}
            aria-label={`Switch to ${isDark ? 'Light' : 'Dark'} Mode`}
          >
            {isDark ? (
              <Sun className="w-4 h-4" aria-hidden="true" />
            ) : (
              <Moon className="w-4 h-4" aria-hidden="true" />
            )}
          </button>
        </div>
      </header>

      <nav aria-label="Primary" className="app-shell-nav">
        {APP_ROUTES.map((route) => {
          const active = isActivePath(currentPath, route.path);
          return (
            <a
              key={route.key}
              href={route.path}
              aria-current={active ? 'page' : undefined}
              onClick={(e) => {
                e.preventDefault();
                if (!active) navigate(route.path);
              }}
              className={`app-shell-nav-link${active ? ' app-shell-nav-link-active' : ''}`}
            >
              {route.label}
            </a>
          );
        })}
      </nav>

      <main id="main-content" className="app-shell-main">
        <LiveRegion message={`${viewName} view loaded`} />
        {children}
      </main>
    </div>
  );
};

export default AppShell;
