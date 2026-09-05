import { useEffect } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Archive, CircleHelp, Disc3, SlidersHorizontal } from "lucide-react";
import { JOBS_ROUTE, LIBRARY_ROUTE, MORE_ROUTE, PROCESS_ROUTE } from "./routes";

const primaryNavigation = [
  { label: "Process", path: PROCESS_ROUTE, icon: Disc3 },
  { label: "Jobs", path: JOBS_ROUTE, icon: SlidersHorizontal },
  { label: "Library", path: LIBRARY_ROUTE, icon: Archive },
  { label: "More", path: MORE_ROUTE, icon: CircleHelp },
];

function RouteFocus() {
  const location = useLocation();

  useEffect(() => {
    document.getElementById("page-heading")?.focus();
  }, [location.pathname]);

  return null;
}

function PrimaryNavigation({ className }: { className: string }) {
  return (
    <nav aria-label="Primary" className={className}>
      {primaryNavigation.map(({ label, path, icon: Icon }) => (
        <NavLink
          className={({ isActive }) => `primary-nav__link${isActive ? " primary-nav__link--active" : ""}`}
          end
          key={path}
          to={path}
        >
          <Icon aria-hidden="true" size={20} strokeWidth={1.8} />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

export function AppShell() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <aside className="side-rail">
        <Link aria-label="SYCO23 Mix Master — Process" className="wordmark" to={PROCESS_ROUTE}>
          <span className="wordmark__name">SYCO23</span>
          <span className="wordmark__sub">Mix Master</span>
        </Link>
        <PrimaryNavigation className="primary-nav primary-nav--rail" />
        <p className="side-rail__privacy">Audio stays private until you choose to process it.</p>
      </aside>
      <main className="app-main" id="main-content" tabIndex={-1}>
        <RouteFocus />
        <Outlet />
      </main>
      <PrimaryNavigation className="primary-nav primary-nav--bottom" />
    </div>
  );
}
