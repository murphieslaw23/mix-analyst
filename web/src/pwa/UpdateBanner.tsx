import React, { useCallback, useState } from 'react';
import { useServiceWorker, applyUpdate } from './registerServiceWorker';

/**
 * User-visible update decision: appears only when a new precache bundle
 * is waiting. Accepting sends SKIP_WAITING and reloads on controllerchange;
 * dismissing keeps the coherent running version.
 */
export const UpdateBanner: React.FC = () => {
  const [waiting, setWaiting] = useState<boolean>(false);
  const [offlineReady, setOfflineReady] = useState<boolean>(false);
  const [updating, setUpdating] = useState<boolean>(false);

  const needRefresh = useCallback(() => setWaiting(true), []);
  const ready = useCallback(() => setOfflineReady(true), []);
  useServiceWorker({ onNeedRefresh: needRefresh, onOfflineReady: ready });

  const accept = useCallback(async () => {
    setUpdating(true);
    const onController = () => window.location.reload();
    navigator.serviceWorker?.addEventListener('controllerchange', onController, { once: true });
    try {
      await applyUpdate();
    } finally {
      window.setTimeout(() => {
        navigator.serviceWorker?.removeEventListener('controllerchange', onController);
        setUpdating(false);
      }, 10000);
    }
  }, []);

  if (!waiting && !offlineReady) return null;

  return (
    <div
      role="status"
      className="fixed bottom-6 left-6 z-50 max-w-sm rounded-lg border border-[#292c38] bg-[#15171e] p-4 shadow-xl"
    >
      {waiting ? (
        <>
          <p className="text-xs font-bold text-white">A new version is ready</p>
          <p className="mt-1 text-xs text-[#9ca3af]">
            Apply it now, or keep using the current version.
          </p>
          <div className="mt-3 flex gap-2">
            <button
              onClick={() => void accept()}
              disabled={updating}
              className="px-4 py-2 min-h-[44px] rounded bg-[#ea580c] text-xs font-bold text-white disabled:opacity-60"
            >
              {updating ? 'Updating…' : 'Apply update'}
            </button>
            <button
              onClick={() => setWaiting(false)}
              className="px-4 py-2 min-h-[44px] rounded border border-[#374151] text-xs font-semibold text-[#d1d5db]"
            >
              Later
            </button>
          </div>
        </>
      ) : (
        <p className="text-xs text-[#9ca3af]">App shell cached — navigation works offline.</p>
      )}
    </div>
  );
};
