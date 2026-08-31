import { useEffect, useState } from "react";
import { Activity } from "lucide-react";

function App() {
  const [apiStatus, setApiStatus] = useState<string>("checking...");

  useEffect(() => {
    fetch("/api/v1/health/live")
      .then((res) => res.json())
      .then((data) => setApiStatus(data.status || "unknown"))
      .catch(() => setApiStatus("unreachable"));
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6">
      <div className="max-w-xl w-full space-y-6">
        <div className="flex items-center gap-3">
          <Activity className="w-8 h-8 text-emerald-400" />
          <h1 className="text-2xl font-bold">Mix Analyst</h1>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
          <h2 className="text-sm font-medium text-slate-400 mb-2">API Status</h2>
          <div className="flex items-center gap-2">
            <div
              className={`w-2.5 h-2.5 rounded-full ${
                apiStatus === "ok" ? "bg-emerald-400" : "bg-amber-400"
              }`}
            />
            <span className="text-slate-200">{apiStatus}</span>
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4 space-y-3">
          <h2 className="text-sm font-medium text-slate-400">Phase 0 Roadmap</h2>
          <ul className="text-sm text-slate-300 space-y-1.5 list-disc list-inside">
            <li>FastAPI backend with health endpoints</li>
            <li>React + Vite frontend with Tailwind</li>
            <li>Docker Compose (api, worker, web, db, redis)</li>
            <li>Acoustic fingerprinting foundation (shazamio, pyacoustid)</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default App;
