import { createReadStream, existsSync } from "node:fs";
import { readFile, stat } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, join, normalize, resolve } from "node:path";

const port = Number(process.env.PWA_TEST_PORT ?? 4173);
const distDirectory = resolve("dist");
const testPrefix = "/__pwa-test__/";
const mimeTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".webmanifest": "application/manifest+json; charset=utf-8",
};

if (!existsSync(join(distDirectory, "index.html"))) {
  throw new Error("PWA test preview requires a freshly built web/dist directory.");
}

const state = {
  serveUpgrade: false,
  skipWaitingMessages: [],
};

function sendJson(response, payload) {
  response.writeHead(200, {
    "Cache-Control": "no-store",
    "Content-Type": "application/json; charset=utf-8",
  });
  response.end(JSON.stringify(payload));
}

async function readJson(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
}

function serviceWorkerTestProbe() {
  // This probe lives only in the deterministic test server response. It lets
  // the browser test observe the user-initiated message without inspecting
  // generated source or changing the production worker.
  return `\nself.addEventListener("message", (event) => {
    if (event.data?.type === "SKIP_WAITING") {
      event.waitUntil(fetch("${testPrefix}messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: event.data.type }),
      }));
    }
  });\n`;
}

const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", `http://${request.headers.host}`);

  if (url.pathname === `${testPrefix}reset` && request.method === "POST") {
    state.serveUpgrade = false;
    state.skipWaitingMessages = [];
    sendJson(response, { ok: true });
    return;
  }

  if (url.pathname === `${testPrefix}upgrade` && request.method === "POST") {
    state.serveUpgrade = true;
    sendJson(response, { ok: true });
    return;
  }

  if (url.pathname === `${testPrefix}messages`) {
    if (request.method === "POST") {
      const message = await readJson(request);
      if (message.type === "SKIP_WAITING") state.skipWaitingMessages.push(message.type);
      sendJson(response, { ok: true });
      return;
    }

    if (request.method === "GET") {
      sendJson(response, { skipWaitingMessages: state.skipWaitingMessages });
      return;
    }
  }

  const requestedPath = url.pathname === "/" ? "/index.html" : url.pathname;
  const candidatePath = normalize(join(distDirectory, requestedPath));
  const resolvedPath = candidatePath.startsWith(`${distDirectory}/`) || candidatePath === distDirectory
    ? candidatePath
    : "";
  const filePath = resolvedPath && existsSync(resolvedPath)
    ? resolvedPath
    : join(distDirectory, "index.html");

  try {
    const file = await stat(filePath);
    if (!file.isFile()) throw new Error("not a file");

    const headers = {
      "Content-Type": mimeTypes[extname(filePath)] ?? "application/octet-stream",
    };

    if (url.pathname === "/service-worker.js") {
      response.writeHead(200, {
        ...headers,
        "Cache-Control": "no-store, no-cache, must-revalidate",
      });
      const source = await readFile(filePath, "utf8");
      response.end(`${source}\n/* pwa-test-revision:${state.serveUpgrade ? "upgrade" : "base"} */${serviceWorkerTestProbe()}`);
      return;
    }

    response.writeHead(200, headers);
    createReadStream(filePath).pipe(response);
  } catch {
    response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("Not found");
  }
});

server.listen(port, "127.0.0.1");

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
