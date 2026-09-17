import { useEffect } from 'react';
import { registerSW } from 'virtual:pwa-register';

interface ServiceWorkerCallbacks {
  onNeedRefresh?: () => void;
  onOfflineReady?: () => void;
}

/**
 * Register the generated precache worker. Update activation happens only
 * after the user confirms in <UpdateBanner /> (registerType: 'prompt').
 */
export function useServiceWorker({ onNeedRefresh, onOfflineReady }: ServiceWorkerCallbacks): void {
  useEffect(() => {
    const updateSW = registerSW({
      immediate: false,
      onNeedRefresh() {
        onNeedRefresh?.();
      },
      onOfflineReady() {
        onOfflineReady?.();
      },
    });
    void updateSW;
  }, [onNeedRefresh, onOfflineReady]);
}

/** Activate the waiting worker after explicit user confirmation. */
export async function applyUpdate(): Promise<void> {
  const { registerSW } = await import('virtual:pwa-register');
  const updateSW = registerSW({ immediate: true });
  await updateSW(true);
}
