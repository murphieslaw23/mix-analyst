import { useState } from "react";

interface UpdateBannerProps {
  applyUpdate: () => Promise<void>;
  onDismiss: () => void;
}

/** A non-blocking, user-operated release handoff for the waiting service worker. */
export function UpdateBanner({ applyUpdate, onDismiss }: UpdateBannerProps) {
  const [isApplying, setIsApplying] = useState(false);

  async function handleApply() {
    setIsApplying(true);
    try {
      // registerSW sends SKIP_WAITING. Its controller-change listener reloads
      // only after the user has made this explicit choice.
      await applyUpdate();
    } catch {
      setIsApplying(false);
    }
  }

  return (
    <aside aria-label="Application update" className="update-banner" role="status">
      <div>
        <strong>A newer version is ready.</strong>
        <p>Apply it when you’re ready to refresh this page.</p>
      </div>
      <div className="update-banner__actions">
        <button className="button button--secondary" disabled={isApplying} onClick={onDismiss} type="button">Not now</button>
        <button className="button button--primary" disabled={isApplying} onClick={() => void handleApply()} type="button">
          {isApplying ? "Updating…" : "Update now"}
        </button>
      </div>
    </aside>
  );
}
