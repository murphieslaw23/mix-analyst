import React, { useEffect, useState } from 'react';
import { authHeaders } from '../../api';
import { apiClient } from '../../api/client';

const PUSH_SUB_ID_KEY = 'syco_push_subscription_id';
const VAPID_KEY_STORAGE = 'syco_push_vapid_key';

function mutationHeaders(): Record<string, string> {
  try {
    return authHeaders();
  } catch {
    return {};
  }
}

function base64ToBytes(base64: string): Uint8Array {
  const normalized = base64.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized + '='.repeat((4 - (normalized.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function readStoredSubscriptionId(): string | null {
  try {
    return localStorage.getItem(PUSH_SUB_ID_KEY);
  } catch {
    return null;
  }
}

function readStoredVapidKey(): string {
  try {
    return localStorage.getItem(VAPID_KEY_STORAGE) ?? '';
  } catch {
    return '';
  }
}

interface PushSettingsProps {
  isDark?: boolean;
}

/**
 * Explicit opt-in Web Push enrollment (PWA plan Task 4 frontend).
 * - Notification.requestPermission is called ONLY inside the opt-in click
 *   handler, never on mount/render.
 * - VAPID public key is pasted by the user; subscription goes through
 *   PushManager then POST /push/subscriptions.
 */
export const PushSettings: React.FC<PushSettingsProps> = ({ isDark = true }) => {
  const [vapidKey, setVapidKey] = useState<string>(() => readStoredVapidKey());
  const [permission, setPermission] = useState<string>(() => {
    try {
      return typeof Notification !== 'undefined' ? Notification.permission : 'unsupported';
    } catch {
      return 'unsupported';
    }
  });
  const [subscriptionId, setSubscriptionId] = useState<string | null>(() =>
    readStoredSubscriptionId(),
  );
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const card = isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]';
  const muted = isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]';
  const inputCls = isDark
    ? 'bg-[#0d0e12] border-[#292c38] text-neutral-200'
    : 'bg-white border-[#d1d5db] text-neutral-800';
  const btnPrimary =
    'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold rounded shadow-sm disabled:opacity-50';
  const btnGhost = isDark
    ? 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#1f222c] hover:bg-[#282c38] border border-[#374151] text-[#d1d5db] text-xs font-semibold rounded disabled:opacity-50'
    : 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center bg-[#f3f4f6] hover:bg-[#e5e7eb] border border-[#d1d5db] text-[#374151] text-xs font-semibold rounded disabled:opacity-50';

  // Keep the displayed permission state fresh without ever requesting it.
  useEffect(() => {
    const sync = () => {
      try {
        if (typeof Notification !== 'undefined') {
          setPermission(Notification.permission);
        }
      } catch {
        // Read-only sync — never request permission here.
      }
    };
    sync();
    document.addEventListener('visibilitychange', sync);
    return () => document.removeEventListener('visibilitychange', sync);
  }, []);

  const persistVapidKey = (value: string) => {
    setVapidKey(value);
    try {
      localStorage.setItem(VAPID_KEY_STORAGE, value);
    } catch {
      // Key persistence is convenience-only.
    }
  };

  const handleOptIn = () => {
    void (async () => {
      setPending(true);
      setNotice(null);
      setError(null);
      try {
        const key = vapidKey.trim();
        if (!key) {
          setError('Paste your VAPID public key first.');
          return;
        }
        if (typeof Notification === 'undefined') {
          setError('Push notifications are not supported in this browser.');
          return;
        }
        // THE only place permission is ever requested: explicit opt-in click.
        const result = await Notification.requestPermission();
        setPermission(result);
        if (result !== 'granted') {
          setError(`Notification permission ${result}. Job alerts stay off.`);
          return;
        }
        if (
          typeof navigator === 'undefined' ||
          !('serviceWorker' in navigator) ||
          !('PushManager' in window)
        ) {
          setError('Push is not supported in this browser yet. In-app notifications still work.');
          return;
        }
        let applicationServerKey: Uint8Array;
        try {
          applicationServerKey = base64ToBytes(key);
        } catch {
          setError('That VAPID key could not be decoded. Check the pasted value.');
          return;
        }
        const registration = await navigator.serviceWorker.ready;
        const sub = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: applicationServerKey as unknown as ArrayBuffer,
        });
        const json = typeof sub.toJSON === 'function' ? sub.toJSON() : {};
        const endpoint = (json as { endpoint?: string }).endpoint ?? '';
        const keys = ((json as { keys?: Record<string, string> }).keys ?? {}) as Record<
          string,
          string
        >;
        if (!endpoint) {
          setError('The browser did not return a push endpoint. Try again.');
          return;
        }
        const created = await apiClient<{ id: string }>('/push/subscriptions', {
          method: 'POST',
          headers: { ...mutationHeaders() },
          body: JSON.stringify({ endpoint, keys }),
        });
        try {
          localStorage.setItem(PUSH_SUB_ID_KEY, created.id);
        } catch {
          // Subscription id persistence is convenience-only.
        }
        setSubscriptionId(created.id);
        setNotice('Job notifications enabled for this device.');
      } catch (err) {
        setError(
          (err as Error)?.message || 'Push enrollment failed. In-app notifications still work.',
        );
      } finally {
        setPending(false);
      }
    })();
  };

  const handleUnsubscribe = () => {
    void (async () => {
      setPending(true);
      setNotice(null);
      setError(null);
      try {
        const id = subscriptionId ?? readStoredSubscriptionId();
        if (id) {
          await apiClient<unknown>(`/push/subscriptions/${encodeURIComponent(id)}`, {
            method: 'DELETE',
            headers: { ...mutationHeaders() },
          });
        }
        try {
          const registration = await navigator.serviceWorker?.ready;
          const existing = await registration?.pushManager?.getSubscription();
          await existing?.unsubscribe();
        } catch {
          // Browser-side cleanup is best-effort; server state is authoritative.
        }
        try {
          localStorage.removeItem(PUSH_SUB_ID_KEY);
        } catch {
          // Removal is best-effort.
        }
        setSubscriptionId(null);
        setNotice('Job notifications turned off for this device.');
      } catch (err) {
        setError((err as Error)?.message || 'Unsubscribe failed. Try again.');
      } finally {
        setPending(false);
      }
    })();
  };

  return (
    <section
      aria-label="Push notification settings"
      data-testid="push-settings"
      className={`border rounded-lg p-4 ${card}`}
    >
      <h3 className="text-sm font-bold text-[#ea580c] uppercase tracking-wide">
        Push settings
      </h3>
      <p className={`text-xs leading-relaxed mt-1 ${muted}`}>
        In-app job outcomes are always listed above. Browser push is strictly opt-in and
        never prompts until you choose it.
      </p>

      <p className={`text-xs font-mono mt-3 ${muted}`} data-testid="push-permission">
        Permission: {permission}
      </p>

      <label className="block mt-3">
        <span className={`block text-xs font-semibold mb-1 ${muted}`}>
          VAPID public key
        </span>
        <input
          value={vapidKey}
          onChange={(e) => persistVapidKey(e.target.value)}
          placeholder="Paste VAPID public key"
          autoComplete="off"
          spellCheck={false}
          data-testid="push-vapid-key"
          aria-label="VAPID public key"
          className={`w-full px-2.5 py-2 min-h-[44px] rounded border text-xs font-mono ${inputCls}`}
        />
      </label>

      <div className="flex flex-wrap gap-2 mt-3">
        <button
          type="button"
          onClick={handleOptIn}
          disabled={pending}
          className={btnPrimary}
          data-testid="push-opt-in"
        >
          {pending ? 'Enabling…' : 'Notify me when jobs finish'}
        </button>
        {subscriptionId && (
          <button
            type="button"
            onClick={handleUnsubscribe}
            disabled={pending}
            className={btnGhost}
            data-testid="push-unsubscribe"
          >
            Unsubscribe from job notifications
          </button>
        )}
      </div>

      {notice && (
        <p className="text-xs text-emerald-400 mt-2" role="status">
          {notice}
        </p>
      )}
      {error && (
        <p className="text-xs text-red-400 mt-2" role="alert">
          {error}
        </p>
      )}
    </section>
  );
};

export default PushSettings;
