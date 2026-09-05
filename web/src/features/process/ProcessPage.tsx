import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { JOBS_ROUTE } from "../../app/routes";
import { ProcessForm } from "./ProcessForm";
import type { ProcessSettings } from "./types";
import { useUpload } from "./useUpload";

export function ProcessPage() {
  const navigate = useNavigate();
  const [settings, setSettings] = useState<ProcessSettings>({ presetId: "sound_system_heavy" });
  const { state, selectFile, startMastering, cancel, reset } = useUpload();

  const start = () => {
    void (async () => {
      const result = await startMastering(settings);
      // A URL change is deliberately downstream of the server-confirmed job.
      if (result?.jobId) navigate(`${JOBS_ROUTE}/${encodeURIComponent(result.jobId)}`);
    })();
  };

  return (
    <section className="route-page process-page" aria-labelledby="page-heading">
      <p className="eyebrow">Press plate intake</p>
      <h1 id="page-heading" tabIndex={-1}>Process audio</h1>
      <p className="route-page__description">Choose one finished mix, set its playback intent, and start when you are ready. Nothing uploads until you confirm.</p>
      <ProcessForm
        onCancel={cancel}
        onFileSelected={selectFile}
        onPresetChange={(presetId) => setSettings({ presetId })}
        onReset={reset}
        onStart={start}
        settings={settings}
        state={state}
      />
    </section>
  );
}
