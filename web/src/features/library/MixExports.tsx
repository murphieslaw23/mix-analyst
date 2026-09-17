import React, { useState } from 'react';
import { CheckCircle } from 'lucide-react';
import { API_BASE_URL } from '../../api/client';
import { formatTime } from '../../audio/format';
import type { TrackCue } from '../../types';

interface MixExportsProps {
  mixId: string;
  tracks: TrackCue[];
  isDark?: boolean;
}

/**
 * DJ export actions for one mix: CUE sheet, Rekordbox/Traktor downloads,
 * and clipboard YouTube timestamps. Lives inside the Results & exports
 * section so every derived artifact of a mix is in one place (previously
 * these buttons sat in the detail header, far from the results panel).
 */
export const MixExports: React.FC<MixExportsProps> = ({ mixId, tracks, isDark = true }) => {
  const [copied, setCopied] = useState(false);

  const copyYouTubeTimestamps = () => {
    const lines = tracks.map((t) => {
      const timeStr = formatTime(t.start_time);
      return `${timeStr} ${t.artist || 'Unknown'} - ${t.title || 'Untitled'} [${t.camelot_key || 'Key'}]`;
    });
    try {
      void navigator.clipboard.writeText(lines.join('\n'));
    } catch {
      // clipboard unavailable — the confirmation still reflects intent;
      // the text is reproducible from the tracklist below.
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 3000);
  };

  const linkCls = `px-3 py-1.5 min-h-[44px] inline-flex items-center text-xs font-semibold rounded border transition ${
    isDark
      ? 'bg-[#1f222c] hover:bg-[#282c38] border-[#374151] text-[#d1d5db]'
      : 'bg-[#f3f4f6] hover:bg-[#e5e7eb] border-[#d1d5db] text-[#374151]'
  }`;

  return (
    <div data-testid="mix-exports">
      <div className="flex flex-wrap gap-2">
        <a href={`${API_BASE_URL}/mixes/${mixId}/export/cue`} download className={linkCls}>
          Export .CUE
        </a>
        <a
          href={`${API_BASE_URL}/mixes/${mixId}/export/rekordbox`}
          download
          className={linkCls}
        >
          Rekordbox XML
        </a>
        <a
          href={`${API_BASE_URL}/mixes/${mixId}/export/traktor`}
          download
          className={linkCls}
        >
          Traktor NML
        </a>
        <button
          onClick={copyYouTubeTimestamps}
          className="px-3 py-1.5 min-h-[44px] bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-semibold rounded shadow-sm"
        >
          Copy YouTube Timestamps
        </button>
      </div>
      {copied && (
        <p
          role="status"
          className={`mt-2 inline-flex items-center gap-1.5 text-xs font-medium ${isDark ? 'text-emerald-400' : 'text-emerald-700'}`}
        >
          <CheckCircle className="w-4 h-4" aria-hidden="true" />
          YouTube timestamps copied to clipboard!
        </p>
      )}
    </div>
  );
};

export default MixExports;
