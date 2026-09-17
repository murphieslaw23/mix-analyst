import React, { useState } from 'react';
import { getApiKey, setApiKey } from '../../api';

interface ApiKeySettingsProps {
  isDark?: boolean;
}

/**
 * Backend API key setting (moved here from the Pipeline panel: the key is
 * a global client setting, not a per-panel concern).
 */
export const ApiKeySettings: React.FC<ApiKeySettingsProps> = ({ isDark = true }) => {
  const [apiKey, setApiKeyState] = useState<string>(() => getApiKey());
  const [notice, setNotice] = useState<string | null>(null);

  const input = isDark
    ? 'bg-[#0d0e12] border-[#292c38] text-neutral-200'
    : 'bg-[#f9fafb] border-[#d1d5db] text-neutral-800';
  const muted = isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]';

  const saveKey = () => {
    setApiKey(apiKey.trim());
    setNotice(apiKey.trim() ? 'API key saved for mutation requests.' : 'API key cleared — open mode.');
    window.setTimeout(() => setNotice(null), 3000);
  };

  return (
    <div>
      <h3 className={`text-xs font-bold uppercase tracking-widest mb-1 ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>
        API key
      </h3>
      <p className={`text-xs leading-relaxed mb-3 ${muted}`}>
        Uploads, dispatches, triggers and sync require <span className="font-mono">X-API-Key</span> when
        the backend sets <span className="font-mono">API_KEYS</span>. Empty means open single-user mode.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="settings-api-key" className="sr-only">
          Backend API key
        </label>
        <input
          id="settings-api-key"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKeyState(e.target.value)}
          placeholder="X-API-Key (optional)"
          data-testid="settings-api-key"
          autoComplete="off"
          className={`px-2.5 py-2 min-h-[44px] rounded border text-xs font-mono w-56 ${input}`}
        />
        <button
          onClick={saveKey}
          className={`px-4 py-2 min-h-[44px] inline-flex items-center justify-center text-xs font-semibold rounded border ${
            isDark
              ? 'bg-[#1f222c] hover:bg-[#282c38] border-[#374151] text-[#d1d5db]'
              : 'bg-[#f3f4f6] hover:bg-[#e5e7eb] border-[#d1d5db] text-[#374151]'
          }`}
          data-testid="settings-api-key-save"
        >
          Save Key
        </button>
      </div>
      {notice && (
        <p className="text-xs text-emerald-400 mt-2" role="status">
          {notice}
        </p>
      )}
    </div>
  );
};

export default ApiKeySettings;
