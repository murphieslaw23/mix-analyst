import { Navigate, createBrowserRouter } from "react-router-dom";
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

function ProcessPage() {
  return (
    <PlaceholderPage
      description="Choose audio, select a mastering preset, and begin when your file is ready. Nothing starts until you confirm it."
      eyebrow="Audio intake"
      title="Process audio"
    />
  );
}

function JobsPage() {
  return <PlaceholderPage description="Processing progress and recovery controls will appear here." eyebrow="Work queue" title="Jobs" />;
}

function LibraryPage() {
  return <PlaceholderPage description="Completed masters will appear here when they are available." eyebrow="Your results" title="Library" />;
}

function MorePage() {
  return <PlaceholderPage description="Install, notification, accessibility, support, and privacy options live here." eyebrow="Settings" title="More" />;
}

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: PROCESS_ROUTE, element: <ProcessPage /> },
      { path: JOBS_ROUTE, element: <JobsPage /> },
      { path: LIBRARY_ROUTE, element: <LibraryPage /> },
      { path: MORE_ROUTE, element: <MorePage /> },
    ],
  },
  { path: "*", element: <Navigate replace to={PROCESS_ROUTE} /> },
]);
