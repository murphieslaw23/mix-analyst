/** Typed same-origin API transport (Task 2). */

export interface ApiProblem {
  status: number;
  title: string;
  detail: string;
  retryable: boolean;
}

export const API_BASE_URL: string =
  (import.meta as unknown as { env?: Record<string, string | undefined> }).env
    ?.VITE_API_BASE_URL || '/api/v1';

function isRetryableStatus(status: number): boolean {
  return status === 0 || status === 408 || status === 429 || status >= 500;
}

export async function toApiProblem(response: Response): Promise<ApiProblem> {
  const status = response.status;
  let detail = response.statusText || `Request failed (${status})`;
  let title = `Request failed (${status})`;
  try {
    const data = (await response.clone().json()) as unknown;
    if (typeof data === 'object' && data !== null) {
      const record = data as Record<string, unknown>;
      if (typeof record.detail === 'string' && record.detail.length > 0) {
        detail = record.detail;
      } else if (typeof record.message === 'string' && record.message.length > 0) {
        detail = record.message;
      }
      if (typeof record.title === 'string' && record.title.length > 0) {
        title = record.title;
      }
    } else if (typeof data === 'string' && data.length > 0) {
      detail = data;
    }
  } catch {
    // Non-JSON error body — keep status-based detail.
  }
  return { status, title, detail, retryable: isRetryableStatus(status) };
}

/**
 * Minimal typed fetch wrapper. Uses the same-origin `/api/v1` default with
 * `VITE_API_BASE_URL` override and sends credentials (cookies) by default.
 */
export async function apiClient<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const hasBody = init.body !== undefined && init.body !== null;
  if (hasBody && !headers.has('Content-Type') && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
      credentials: init.credentials ?? 'include',
    });
  } catch (err) {
    throw {
      status: 0,
      title: 'Network error',
      detail: (err as Error)?.message || 'Backend unreachable.',
      retryable: true,
    } satisfies ApiProblem;
  }
  if (!response.ok) throw await toApiProblem(response);
  if (response.status === 204) return undefined as unknown as T;
  return (await response.json()) as T;
}
