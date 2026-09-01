import React from 'react';
import {
  MidiDevice,
  MidiMapping,
  MidiLogMessage,
  MidiParamKey,
  DEFAULT_PRESETS,
} from '../midi/WebMidiService';

interface MidiControllerModalProps {
  isOpen: boolean;
  onClose: () => void;
  isSupported: boolean;
  devices: MidiDevice[];
  selectedDeviceId: string | null;
  onSelectDevice: (id: string | null) => void;
  mapping: MidiMapping;
  learningParam: MidiParamKey | null;
  onStartLearning: (param: MidiParamKey) => void;
  onCancelLearning: () => void;
  onApplyPreset: (key: keyof typeof DEFAULT_PRESETS) => void;
  lastMessage: MidiLogMessage | null;
}

const PARAM_LABELS: Record<MidiParamKey, { title: string; type: 'cc' | 'note' }> = {
  masterVolume: { title: 'Master Volume', type: 'cc' },
  subBassExcursion: { title: 'Sub-Bass Excursion Depth', type: 'cc' },
  filterCutoff: { title: 'DSP Filter Cutoff', type: 'cc' },
  strobeSensitivity: { title: 'Strobe Trigger Level', type: 'cc' },
  cameraOrbit: { title: '3D Orbit Speed', type: 'cc' },
  playPause: { title: 'Play / Pause Trigger', type: 'note' },
  cueJumpPrev: { title: 'Cue Jump Previous', type: 'note' },
  cueJumpNext: { title: 'Cue Jump Next', type: 'note' },
};

export const MidiControllerModal: React.FC<MidiControllerModalProps> = ({
  isOpen,
  onClose,
  isSupported,
  devices,
  selectedDeviceId,
  onSelectDevice,
  mapping,
  learningParam,
  onStartLearning,
  onCancelLearning,
  onApplyPreset,
  lastMessage,
}) => {
  if (!isOpen) return null;

  return (
    <div
      data-testid="midi-modal-overlay"
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
    >
      <div className="bg-neutral-900 border border-neutral-700 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 shadow-2xl text-neutral-200 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-neutral-800 pb-4">
          <div>
            <h2 className="text-lg font-bold uppercase tracking-wider text-orange-500 font-mono">
              Web MIDI Hardware Configuration
            </h2>
            <p className="text-xs text-neutral-400 mt-0.5">
              Connect external DJ controllers, mixers, or pads for live tactile modulation.
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-white px-2.5 py-1 bg-neutral-800 rounded font-mono text-xs"
          >
            ESC / CLOSE
          </button>
        </div>

        {/* Support Alert */}
        {!isSupported && (
          <div className="bg-amber-950/50 border border-amber-800 p-3 rounded text-xs text-amber-200">
            Web MIDI API is not natively available in this browser. Please use Chrome, Edge, or Opera with MIDI permissions enabled.
          </div>
        )}

        {/* Device Selector */}
        <div className="space-y-2">
          <label className="block text-xs font-mono text-neutral-400">DETECTED MIDI HARDWARE</label>
          <select
            value={selectedDeviceId || ''}
            onChange={(e) => onSelectDevice(e.target.value ? e.target.value : null)}
            className="w-full bg-neutral-950 border border-neutral-700 rounded px-3 py-2 text-xs text-neutral-200 focus:border-orange-500 outline-none"
          >
            <option value="">All Connected MIDI Devices (Listen on All)</option>
            {devices.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.manufacturer}) - {d.state}
              </option>
            ))}
          </select>
        </div>

        {/* Controller Presets */}
        <div className="space-y-2">
          <label className="block text-xs font-mono text-neutral-400">HARDWARE MAPPING PRESETS</label>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => onApplyPreset('pioneer_ddj')}
              className="px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 rounded text-xs font-mono"
            >
              Pioneer DDJ-400 / FLX4
            </button>
            <button
              onClick={() => onApplyPreset('traktor_kontrol')}
              className="px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 rounded text-xs font-mono"
            >
              Traktor Kontrol S2 / S4
            </button>
            <button
              onClick={() => onApplyPreset('akai_apc')}
              className="px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 rounded text-xs font-mono"
            >
              Akai APC Mini / MPK
            </button>
            <button
              onClick={() => onApplyPreset('generic_8knob')}
              className="px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 rounded text-xs font-mono"
            >
              Generic 8-Knob USB
            </button>
          </div>
        </div>

        {/* Live MIDI Monitor */}
        <div className="bg-neutral-950 border border-neutral-800 p-3 rounded font-mono text-xs space-y-1">
          <div className="text-neutral-500 text-[10px] uppercase tracking-wider">LIVE MIDI SIGNAL MONITOR</div>
          {lastMessage ? (
            <div className="flex items-center space-x-4 text-emerald-400">
              <span>TYPE: {lastMessage.type.toUpperCase()}</span>
              <span>CH: {lastMessage.channel}</span>
              <span>NUM: {lastMessage.number}</span>
              <span>VAL: {lastMessage.value} ({(lastMessage.normalized * 100).toFixed(0)}%)</span>
            </div>
          ) : (
            <div className="text-neutral-600 italic">Waiting for MIDI hardware signals...</div>
          )}
        </div>

        {/* Interactive Mapping Table */}
        <div className="space-y-2">
          <label className="block text-xs font-mono text-neutral-400">PARAMETER ASSIGNMENTS</label>
          <div className="border border-neutral-800 rounded divide-y divide-neutral-800 overflow-hidden text-xs">
            {(Object.keys(PARAM_LABELS) as MidiParamKey[]).map((param) => {
              const info = PARAM_LABELS[param];
              const isLearning = learningParam === param;
              const mappedValue =
                info.type === 'cc'
                  ? (mapping as any)[`${param}Cc`]
                  : (mapping as any)[`${param}Note`];

              return (
                <div key={param} className="p-2.5 flex items-center justify-between hover:bg-neutral-800/40">
                  <div>
                    <div className="font-semibold text-neutral-200">{info.title}</div>
                    <div className="text-[10px] font-mono text-neutral-500">
                      Target: {info.type.toUpperCase()} | Current: {mappedValue !== undefined ? `${info.type.toUpperCase()} #${mappedValue}` : 'Unassigned'}
                    </div>
                  </div>

                  <div>
                    {isLearning ? (
                      <button
                        onClick={onCancelLearning}
                        className="px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded font-mono text-xs animate-pulse"
                      >
                        PRESS KNOB/PAD...
                      </button>
                    ) : (
                      <button
                        onClick={() => onStartLearning(param)}
                        className="px-3 py-1 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 rounded font-mono text-xs text-neutral-300"
                      >
                        MIDI LEARN
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end pt-2 border-t border-neutral-800">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-orange-600 hover:bg-orange-500 text-white font-mono text-xs font-semibold rounded"
          >
            DONE / SAVE
          </button>
        </div>
      </div>
    </div>
  );
};
