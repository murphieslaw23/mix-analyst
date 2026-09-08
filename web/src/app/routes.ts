export const PROCESS_ROUTE = "/process";
export const JOBS_ROUTE = "/jobs";
export const BATCHES_ROUTE = "/batches";
export const LIBRARY_ROUTE = "/library";
export const MORE_ROUTE = "/more";
export const NOTIFICATIONS_ROUTE = `${MORE_ROUTE}/notifications`;

export const primaryRoutes = {
  process: PROCESS_ROUTE,
  jobs: JOBS_ROUTE,
  library: LIBRARY_ROUTE,
  more: MORE_ROUTE,
} as const;
