import { authorizedFetch } from "../auth/session";

interface PushConfigResponse {
  enabled: boolean;
  vapid_public_key: string | null;
}

export class PushEnrollmentError extends Error {}

function applicationServerKey(value: string): ArrayBuffer {
  const padding = "=".repeat((4 - (value.length % 4)) % 4);
  const base64 = (value + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  const buffer = new ArrayBuffer(raw.length);
  const output = new Uint8Array(buffer);
  for (let index = 0; index < raw.length; index += 1) {
    output[index] = raw.charCodeAt(index);
  }
  return buffer;
}

export async function subscribeToPush(
  registration: ServiceWorkerRegistration,
  vapidPublicKey: string,
): Promise<PushSubscriptionJSON> {
  const existing = await registration.pushManager.getSubscription();
  const subscription = existing ?? await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: applicationServerKey(vapidPublicKey),
  });
  return subscription.toJSON();
}

export async function enableJobPushNotifications(): Promise<void> {
  if (typeof Notification === "undefined") {
    throw new PushEnrollmentError("Notification permission is not supported in this browser.");
  }

  // This call intentionally happens only inside the user-operated enrollment action.
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new PushEnrollmentError("Notification permission was not granted.");
  }
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    throw new PushEnrollmentError("Push notifications are not supported in this browser.");
  }

  const configResponse = await authorizedFetch("/api/v1/push/config");
  if (!configResponse.ok) throw new PushEnrollmentError("Could not load Push configuration.");
  const config = await configResponse.json() as PushConfigResponse;
  if (!config.enabled || !config.vapid_public_key) {
    throw new PushEnrollmentError("Push delivery is not configured on this server.");
  }

  const registration = await navigator.serviceWorker.ready;
  const subscription = await subscribeToPush(registration, config.vapid_public_key);
  const response = await authorizedFetch("/api/v1/push/subscriptions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(subscription),
  });
  if (!response.ok) throw new PushEnrollmentError("Could not save the Push subscription.");
}
