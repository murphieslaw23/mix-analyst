const ACCESS_TOKEN_STORAGE_KEY = "syco23:api-access-token:v1";
const ACCESS_TOKEN_FRAGMENT_KEY = "access_token";
let originalFetch: typeof window.fetch | null = null;
let transportInstalled = false;

function looksLikeJwt(value: string): boolean {
  const parts = value.split(".");
  return parts.length === 3 && parts.every((part) => /^[A-Za-z0-9_-]+$/.test(part));
}

function apiBaseUrl(): URL {
  return new URL(import.meta.env.VITE_API_BASE_URL ?? "/api/v1", window.location.origin);
}

function isProtectedApiRequest(input: RequestInfo | URL): boolean {
  const raw = input instanceof Request ? input.url : String(input);
  const requestUrl = new URL(raw, window.location.origin);
  const base = apiBaseUrl();
  const prefix = base.pathname.replace(/\/$/, "");
  return requestUrl.origin === base.origin && (requestUrl.pathname === prefix || requestUrl.pathname.startsWith(`${prefix}/`));
}

function nativeFetch(): typeof window.fetch {
  if (originalFetch === null) originalFetch = window.fetch.bind(window);
  return originalFetch;
}

function authorizedInit(init: RequestInit = {}): RequestInit {
  const headers = new Headers(init.headers);
  const token = getApiAccessToken();
  if (token && !headers.has("Authorization")) headers.set("Authorization", `Bearer ${token}`);
  return { ...init, credentials: init.credentials ?? "include", headers };
}

/**
 * Install one transport boundary so JSON, SSE and resumable-upload fetches all
 * carry the same operator credential. Non-API requests are never decorated.
 */
export function installAuthorizedApiTransport(): void {
  if (typeof window === "undefined" || transportInstalled) return;
  const baseFetch = nativeFetch();
  window.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
    if (!isProtectedApiRequest(input)) return baseFetch(input, init);
    return baseFetch(input, authorizedInit(init));
  }) as typeof window.fetch;
  transportInstalled = true;
}

/**
 * Accept an externally issued API bearer token from the URL fragment exactly
 * once, keep it scoped to the current browser tab, then remove it from the URL.
 * Fragments are not sent in HTTP requests, so the bootstrap token does not
 * enter reverse-proxy or application request logs.
 */
export function bootstrapApiSession(): void {
  if (typeof window === "undefined") return;
  installAuthorizedApiTransport();

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

/** Explicit protected fetch for modules that want to make the contract visible. */
export async function authorizedFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  return nativeFetch()(input, authorizedInit(init));
}
