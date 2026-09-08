import { Link, Navigate, createBrowserRouter } from "react-router-dom";
import { BatchDetailPage } from "../features/batches/BatchDetailPage";
import { JobDetailPage } from "../features/jobs/JobDetailPage";
import { JobsPage } from "../features/jobs/JobsPage";
import { LibraryPage } from "../features/library/LibraryPage";
import { MixDetailPage } from "../features/library/MixDetailPage";
import { NotificationCenterPage } from "../features/notifications/NotificationCenterPage";
import { ProcessPage } from "../features/process/ProcessPage";
import { AppShell } from "./AppShell";
import { BATCHES_ROUTE, JOBS_ROUTE, LIBRARY_ROUTE, MORE_ROUTE, NOTIFICATIONS_ROUTE, PROCESS_ROUTE } from "./routes";

interface PlaceholderPageProps {
  eyebrow: string;
  title: string;
  description: string;
}

function PlaceholderPage({ eyebrow, title, description }: PlaceholderPageProps) {
  return (
    <section className="route-page" aria-labelledby="page-heading">
      <p className="eyebrow">{eyebrow}</p>
      <h1 id="page-heading" tabIndex={-1}>
        {title}
      </h1>
      <p className="route-page__description">{description}</p>
    </section>
  );
}

function MorePage() {
  return (
    <section className="route-page" aria-labelledby="page-heading">
      <p className="eyebrow">Operations</p>
      <h1 id="page-heading" tabIndex={-1}>More</h1>
      <p className="route-page__description">Review durable job results and operational controls that do not belong in the primary mastering flow.</p>
      <div className="resource-state">
        <h2>Notification center</h2>
        <p>Completed and failed jobs remain reviewable here until you dismiss them.</p>
        <Link className="button button--secondary" to={NOTIFICATIONS_ROUTE}>Open notifications</Link>
      </div>
    </section>
  );
}

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: PROCESS_ROUTE, element: <ProcessPage /> },
      { path: JOBS_ROUTE, element: <JobsPage /> },
      { path: `${JOBS_ROUTE}/:jobId`, element: <JobDetailPage /> },
      { path: `${BATCHES_ROUTE}/:batchId`, element: <BatchDetailPage /> },
      { path: LIBRARY_ROUTE, element: <LibraryPage /> },
      { path: `${LIBRARY_ROUTE}/:mixId`, element: <MixDetailPage /> },
      { path: MORE_ROUTE, element: <MorePage /> },
      { path: NOTIFICATIONS_ROUTE, element: <NotificationCenterPage /> },
    ],
  },
  { path: "*", element: <Navigate replace to={PROCESS_ROUTE} /> },
]);
