import { Navigate, createBrowserRouter } from "react-router-dom";
import { LibraryPage } from "../features/library/LibraryPage";
import { ProcessPage } from "../features/process/ProcessPage";
import { AppShell } from "./AppShell";
import { JOBS_ROUTE, LIBRARY_ROUTE, MORE_ROUTE, PROCESS_ROUTE } from "./routes";

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

function JobsPage() {
  return <PlaceholderPage description="Processing progress and recovery controls will appear here." eyebrow="Work queue" title="Jobs" />;
}

function JobStartPage() {
  return <PlaceholderPage description="Your mastering job was saved. Live progress will appear here shortly." eyebrow="Work queue" title="Job queued" />;
}

function MorePage() {
  return <PlaceholderPage description="Install controls, notification preferences, accessibility support, and privacy settings are planned for a future update." eyebrow="Coming next" title="More" />;
}

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: PROCESS_ROUTE, element: <ProcessPage /> },
      { path: JOBS_ROUTE, element: <JobsPage /> },
      { path: `${JOBS_ROUTE}/:jobId`, element: <JobStartPage /> },
      { path: LIBRARY_ROUTE, element: <LibraryPage /> },
      { path: MORE_ROUTE, element: <MorePage /> },
    ],
  },
  { path: "*", element: <Navigate replace to={PROCESS_ROUTE} /> },
]);
