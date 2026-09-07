const ACCESS_TOKEN_STORAGE_KEY = "syco23:api-access-token:v1";
const ACCESS_TOKEN_FRAGMENT_KEY = "access_token";

function looksLikeJwt(value: string): boolean {
  const parts = value.split(".");
  return parts.length === 3 && parts.every((part) => /^[A-Za-z0-9_-]+$/.test(part));
}

/**
 * Accept an externally issued API bearer token from the URL fragment exactly
 * once, keep it scoped to the current browser tab, then remove it from the URL.
 * Fragments are not sent in HTTP requests, so the bootstrap token does not
 * enter reverse-proxy or application request logs.
 */
export function bootstrapApiSession(): void {
  if (typeof window === "undefined") return;
  const rawHash = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : window.location.hash;
  if (!rawHash) return;

  const params = new URLSearchParams(rawHash);
  const candidate = params.get(ACCESS_TOKEN_FRAGMENT_KEY);
  if (candidate !== null) {
    if (looksLikeJwt(candidate)) window.sessionStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, candidate);
    else window.sessionStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);

    params.delete(ACCESS_TOKEN_FRAGMENT_KEY);
    const remainingHash = params.toString();
    const cleanUrl = `${window.location.pathname}${window.location.search}${remainingHash ? `#${remainingHash}` : ""}`;
    window.history.replaceState(window.history.state, "", cleanUrl);
  }
}

export function getApiAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  const token = window.sessionStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
  return token && looksLikeJwt(token) ? token : null;
}

export function clearApiSession(): void {
  if (typeof window !== "undefined") window.sessionStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
}

/** Attach the current tab-scoped bearer credential to every protected request. */
export async function authorizedFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getApiAccessToken();
  if (token && !headers.has("Authorization")) headers.set("Authorization", `Bearer ${token}`);
  return fetch(input, {
    ...init,
    credentials: init.credentials ?? "include",
    headers,
  });
}
