import type { ApiProblem } from "./contracts";

export type { ApiProblem } from "./contracts";

export class ApiProblemError extends Error implements ApiProblem {
  readonly status: number;
  readonly title: string;
  readonly detail: string;
  readonly retryable: boolean;

  constructor(problem: ApiProblem) {
    super(problem.detail);
    this.name = "ApiProblemError";
    this.status = problem.status;
    this.title = problem.title;
    this.detail = problem.detail;
    this.retryable = problem.retryable;
  }
}

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "/api/v1").replace(/\/$/, "");

function safeProblem(status: number): ApiProblem {
  if (status === 401 || status === 403) return { status, title: "Sign-in required", detail: "You do not have access to these mixes.", retryable: false };
  if (status === 404) return { status, title: "Not found", detail: "That mix is no longer available.", retryable: false };
  if (status === 408 || status === 429 || status >= 500) return { status, title: "Service temporarily unavailable", detail: "Please try again in a moment.", retryable: true };
  return { status, title: "Could not complete that request", detail: "Please review your request and try again.", retryable: false };
}

export function asApiProblem(error: unknown): ApiProblem {
  if (error instanceof ApiProblemError) return error;
  return { status: 0, title: "Could not reach Mix Master", detail: "Check your connection and try again.", retryable: true };
}

export async function apiClient<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, { ...init, credentials: "include", headers: { Accept: "application/json", ...init.headers } });
  } catch {
    throw new ApiProblemError(asApiProblem(undefined));
  }
  if (!response.ok) {
    // Do not expose backend error payloads or convert them into fake success.
    throw new ApiProblemError(safeProblem(response.status));
  }
  if (response.status === 204) return undefined as T;
  try { return (await response.json()) as T; } catch {
    throw new ApiProblemError({ status: response.status, title: "Unexpected response", detail: "The service sent a response we could not read. Please try again.", retryable: true });
  }
}
