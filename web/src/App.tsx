import { RouterProvider } from "react-router-dom";
import { useEffect, useState } from "react";
import { router } from "./app/router";
import { UpdateBanner } from "./pwa/UpdateBanner";
import { useOnlineStatus } from "./pwa/offline";
import { registerServiceWorker } from "./pwa/registerServiceWorker";

function PwaStatus() {
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const [offlineReady, setOfflineReady] = useState(false);
  const [applyUpdate, setApplyUpdate] = useState<(() => Promise<void>) | null>(null);
  const isOffline = useOnlineStatus();

  useEffect(() => {
    const update = registerServiceWorker({
      onNeedRefresh: () => setUpdateAvailable(true),
      onOfflineReady: () => setOfflineReady(true),
    });
    setApplyUpdate(() => update);
  }, []);

  return (
    <>
      {isOffline ? <p className="connection-notice" role="status">You’re offline. Audio uploads and live job updates need a connection.</p> : null}
      {offlineReady ? <p className="visually-hidden" role="status">This app is ready for offline navigation.</p> : null}
      {updateAvailable && applyUpdate ? (
        <UpdateBanner
          applyUpdate={applyUpdate}
          onDismiss={() => setUpdateAvailable(false)}
        />
      ) : null}
    </>
  );
}

export function App() {
  return (
    <>
      <RouterProvider router={router} />
      <PwaStatus />
    </>
  );
}

export default App;
