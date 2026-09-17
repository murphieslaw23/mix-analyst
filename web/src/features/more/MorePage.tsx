import React from 'react';
import { CheckCircle, ExternalLink, Layers, Radio, Volume2, Wrench } from 'lucide-react';
import {
  BATCHES_ROUTE,
  JOBS_ROUTE,
  NOTIFICATIONS_ROUTE,
  PROCESS_INTAKE_ROUTE,
  PROCESS_ROUTE,
  navigate,
} from '../../app/routes';
import { ApiKeySettings } from './ApiKeySettings';
import { useNotifications } from '../notifications/useNotifications';

interface MorePageProps {
  isDark?: boolean;
}

/**
 * Secondary destinations: workflow shortcuts (notifications with unread
 * badge, batches), client settings (API key), support docs, and legal.
 * Previously notifications were buried at /more/notifications with no entry
 * point, and the API key lived inside the Pipeline panel.
 */
export const MorePage: React.FC<MorePageProps> = ({ isDark = true }) => {
  const { unreadCount } = useNotifications();

  const card = isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm';
  const muted = isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]';
  const row = isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]';
  const btnGhost = isDark
    ? 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center gap-2 bg-[#1f222c] hover:bg-[#282c38] border border-[#374151] text-[#d1d5db] text-xs font-semibold rounded no-underline'
    : 'px-4 py-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center gap-2 bg-[#f3f4f6] hover:bg-[#e5e7eb] border border-[#d1d5db] text-[#374151] text-xs font-semibold rounded no-underline';

  const linkTo = (path: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    navigate(path);
  };

  return (
    <div className="space-y-6" data-testid="more-view">
      <div className={`border rounded-lg p-5 sm:p-6 ${card}`}>
        <h2 className="text-xl font-bold text-[#ea580c] uppercase tracking-wide">More</h2>
        <p className={`text-sm leading-relaxed mt-1 ${muted}`}>
          Shortcuts, settings, and support for the engine room.
        </p>
        <nav aria-label="Secondary" className="flex flex-wrap gap-2 mt-4">
          <a href={NOTIFICATIONS_ROUTE} onClick={linkTo(NOTIFICATIONS_ROUTE)} className={btnGhost}>
            Notifications
            <span
              data-testid="more-unread-count"
              aria-label={`${unreadCount} unread notifications`}
              className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-[#ea580c]/20 text-[#ea580c] border border-[#ea580c]/30"
            >
              {unreadCount === 0 ? 'No unread' : `${unreadCount} unread`}
            </span>
          </a>
          <a href={PROCESS_INTAKE_ROUTE} onClick={linkTo(PROCESS_INTAKE_ROUTE)} className={btnGhost}>
            Process audio
          </a>
          <a href={PROCESS_ROUTE} onClick={linkTo(PROCESS_ROUTE)} className={btnGhost}>
            Pipeline &amp; Broadcast
          </a>
          <a href={JOBS_ROUTE} onClick={linkTo(JOBS_ROUTE)} className={btnGhost}>
            Jobs
          </a>
          <a href={BATCHES_ROUTE} onClick={linkTo(BATCHES_ROUTE)} className={btnGhost}>
            Batch review
          </a>
        </nav>
      </div>

      <div className={`border rounded-lg p-5 sm:p-6 ${card}`}>
        <h2 className={`text-base font-bold mb-4 ${isDark ? 'text-white' : 'text-gray-900'}`}>
          Settings
        </h2>
        <ApiKeySettings isDark={isDark} />
      </div>

      <div className={`border rounded-lg p-6 ${card}`}>
        <h2 className="text-xl font-bold text-[#ea580c] uppercase tracking-wide flex items-center gap-2 mb-4">
          <Wrench className="w-5 h-5" /> Sound-System Engineering & Support
        </h2>
        <p className={`text-sm leading-relaxed mb-6 ${isDark ? 'text-[#9ca3af]' : 'text-[#4b5563]'}`}>
          Mix Analyst is tailored specifically for underground sound-system culture (freetekno, hardtek, jungle, acidcore). Below are operational guidelines and troubleshooting steps for continuous DJ mix analysis and hardware compliance.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className={`p-4 rounded-lg border ${row}`}>
            <h3 className="font-bold text-sm text-[#ea580c] mb-2 flex items-center gap-2">
              <Volume2 className="w-4 h-4" /> EBU R128 Loudness Targets
            </h3>
            <p className={`text-xs leading-relaxed ${isDark ? 'text-[#9ca3af]' : 'text-[#4b5563]'}`}>
              For outdoor freetekno speaker stacks, master target is <strong>-14.0 LUFS</strong> Integrated with True Peak capped at <strong>-0.5 dBTP</strong> to avoid DAC inter-sample clipping on high-powered amplifiers.
            </p>
          </div>

          <div className={`p-4 rounded-lg border ${row}`}>
            <h3 className="font-bold text-sm text-[#14b8a6] mb-2 flex items-center gap-2">
              <Layers className="w-4 h-4" /> Demucs 4-Stem GPU Processing
            </h3>
            <p className={`text-xs leading-relaxed ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
              Stem separation requires CUDA or Apple Silicon acceleration. On CPU workers, 30-minute sets process in ~180s using multi-threaded PyTorch chunking.
            </p>
          </div>

          <div className={`p-4 rounded-lg border ${row}`}>
            <h3 className="font-bold text-sm text-[#f59e0b] mb-2 flex items-center gap-2">
              <Radio className="w-4 h-4" /> AzuraCast Sync Protocol
            </h3>
            <p className={`text-xs leading-relaxed ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
              Dynamic cue sheets sync automatically over WebSocket/REST webhooks to inject upcoming artist tags and energy transitions to 24/7 web radio streams.
            </p>
          </div>
        </div>
      </div>

      <div className={`border rounded-lg p-6 ${card}`}>
        <h3 className={`text-base font-bold mb-3 ${isDark ? 'text-white' : 'text-gray-900'}`}>Community & Issue Reporting</h3>
        <p className={`text-xs ${muted} mb-4`}>
          Need assistance with custom audio processing pipelines, container deployments, or station webhooks? Open an issue on GitHub:
        </p>
        <a
          href="https://github.com/murphieslaw23/mix-analyst/issues"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 px-4 py-2 min-h-[44px] bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold rounded"
        >
          GitHub Issue Tracker <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>

      <div className={`border rounded-lg p-6 space-y-6 ${card}`}>
        <div>
          <h2 className="text-xl font-black text-[#ea580c] uppercase tracking-wide mb-1">
            Impressum (Legal Notice)
          </h2>
          <p className={`text-xs font-mono ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>
            Angaben gemäß § 5 TMG / Telemediengesetz
          </p>
        </div>

        <div className={`text-xs leading-relaxed space-y-3 ${isDark ? 'text-[#cbd5e1]' : 'text-[#374151]'}`}>
          <div>
            <strong className="text-[#ea580c]">Betreiber & Verantwortlicher:</strong><br />
            Erik Milach (Murphies Law)<br />
            SYSTEM CORRUPT / SYCO23 Sound System<br />
            Dresden, Saxony, Germany (DE)<br />
            Email: emilach82@gmail.com
          </div>

          <div>
            <strong className="text-[#ea580c]">Kultur- und Projekthinweis:</strong><br />
            Dieses System dient der wissenschaftlichen, technischen und künstlerischen Erforschung von DSP-Audioanalyse, Stem-Separation und harmonischem Beatmatching im Rahmen der europäischen Sound-System- und Freetekno-Kultur. Es handelt sich um ein freies, nicht-kommerzielles Open-Source-Projekt.
          </div>

          <div>
            <strong className="text-[#ea580c]">Datenschutzerklärung (DSGVO):</strong><br />
            Es werden clientseitig keinerlei personenbezogene Tracking-Cookies oder Werbetracker gesetzt. Sämtliche Audioverarbeitungen, CUE-Exporte und FFT-Transientenanalysen verbleiben in der lokalen Applikationsumgebung bzw. im autorisierten Backend-Container.
          </div>
        </div>

        <p className={`text-[11px] font-mono inline-flex items-center gap-1.5 ${muted}`}>
          <CheckCircle className="w-3.5 h-3.5" aria-hidden="true" />
          No tracking cookies · local-first audio processing
        </p>
      </div>
    </div>
  );
};

export default MorePage;
