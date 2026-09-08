import { useState } from "react";

import { Button } from "../../components/ui/Button";
import { enableJobPushNotifications, PushEnrollmentError } from "../../pwa/push";

type EnrollmentState = "idle" | "enabling" | "enabled" | "error";

export function PushSettings() {
  const [state, setState] = useState<EnrollmentState>("idle");
  const [message, setMessage] = useState<string | null>(null);

  async function enable(): Promise<void> {
    setState("enabling");
    setMessage(null);
    try {
      await enableJobPushNotifications();
      setState("enabled");
      setMessage("Job completion notifications are enabled for this browser.");
    } catch (error) {
      setState("error");
      setMessage(
        error instanceof PushEnrollmentError
          ? error.message
          : "Could not enable notification delivery.",
      );
    }
  }

  return (
    <section className="resource-state" aria-labelledby="push-settings-heading">
      <h2 id="push-settings-heading">Job completion alerts</h2>
      <p>OS notifications are optional. Your durable results remain available in this notification center either way.</p>
      <Button
        disabled={state === "enabling" || state === "enabled"}
        onClick={() => void enable()}
        tone="secondary"
      >
        {state === "enabling" ? "Enabling notifications…" : state === "enabled" ? "Notifications enabled" : "Notify me when jobs finish"}
      </Button>
      {message ? <p aria-live="polite">{message}</p> : null}
    </section>
  );
}
