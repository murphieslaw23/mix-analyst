import { authorizedFetch } from "../auth/session";

interface ArtifactTicketResponse {
  download_url: string;
  expires_in_seconds: number;
}

function ticketEndpoint(protectedUrl: string): URL {
  const url = new URL(protectedUrl, window.location.origin);
  if (!url.pathname.endsWith("/download")) throw new Error("Invalid protected artifact URL");
  url.pathname = `${url.pathname.slice(0, -"/download".length)}/download-ticket`;
  url.search = "";
  return url;
}

export async function resolveArtifactDownloadUrl(protectedUrl: string): Promise<string> {
  const endpoint = ticketEndpoint(protectedUrl);
  const response = await authorizedFetch(endpoint, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`Artifact access unavailable (${response.status})`);
  const payload = await response.json() as ArtifactTicketResponse;
  if (!payload.download_url || payload.expires_in_seconds <= 0) throw new Error("Invalid artifact access response");
  return new URL(payload.download_url, endpoint.origin).href;
}

export async function triggerArtifactDownload(protectedUrl: string): Promise<void> {
  const resolvedUrl = await resolveArtifactDownloadUrl(protectedUrl);
  const anchor = document.createElement("a");
  anchor.href = resolvedUrl;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}
