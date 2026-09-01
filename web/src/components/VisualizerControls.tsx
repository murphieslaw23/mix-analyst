import React from 'react';
import {
  VisualizerSettings,
  StackArchitecture,
  VisualizerTheme,
} from '../visualizer/SpeakerStackVisualizer';

interface VisualizerControlsProps {
  settings: VisualizerSettings;
  onUpdateSettings: (newSettings: Partial<VisualizerSettings>) => void;
  onOpenMidiModal: () => void;
  isMidiConnected: boolean;
}

export const VisualizerControls: React.FC<VisualizerControlsProps> = ({
  settings,
  onUpdateSettings,
  onOpenMidiModal,
  isMidiConnected,
}) => {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-4 text-sm text-neutral-200">
      <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
        <div className="flex items-center space-x-2">
          <span className="font-bold tracking-wide uppercase text-xs text-orange-500 font-mono">
            3D Speaker Stack Controller
          </span>
        </div>
        <button
          onClick={onOpenMidiModal}
          data-testid="open-midi-modal-btn"
          className="flex items-center space-x-2 px-3 py-1 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 rounded text-xs font-mono transition-colors"
        >
          <span
            className={`inline-block w-2 h-2 rounded-full ${
              isMidiConnected ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]' : 'bg-neutral-500'
            }`}
          />
          <span>MIDI HARDWARE</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Stack Preset */}
        <div>
          <label className="block text-xs font-mono text-neutral-400 mb-1">RIG ARCHITECTURE</label>
          <select
            value={settings.architecture}
            onChange={(e) => onUpdateSettings({ architecture: e.target.value as StackArchitecture })}
            data-testid="rig-preset-select"
            className="w-full bg-neutral-950 border border-neutral-700 rounded px-2.5 py-1.5 text-xs text-neutral-200 focus:border-orange-500 outline-none"
          >
            <option value="wall_of_sound">Wall of Sound 23 (4x3 Scoop Array)</option>
            <option value="mechanical_totem">Mechanical Totem (Vertical Monolith)</option>
            <option value="underground_rig">Underground Rig (Split Twin Stack)</option>
          </select>
        </div>

        {/* Visualizer Theme */}
        <div>
          <label className="block text-xs font-mono text-neutral-400 mb-1">COLOR THEME</label>
          <select
            value={settings.theme}
            onChange={(e) => onUpdateSettings({ theme: e.target.value as VisualizerTheme })}
            data-testid="theme-select"
            className="w-full bg-neutral-950 border border-neutral-700 rounded px-2.5 py-1.5 text-xs text-neutral-200 focus:border-orange-500 outline-none"
          >
            <option value="rust">Rust Orange (#c84b14)</option>
            <option value="crimson">Deep Crimson (#8c1d1d)</option>
            <option value="amber">Dull Amber (#d97706)</option>
            <option value="copper">Oxidized Copper (#0d9488)</option>
            <option value="ochre">Burnt Ochre (#b45309)</option>
          </select>
        </div>

        {/* Excursion Sensitivity */}
        <div>
          <div className="flex justify-between text-xs font-mono text-neutral-400 mb-1">
            <span>SUB EXCURSION SCALE</span>
            <span>{settings.excursionScale.toFixed(1)}x</span>
          </div>
          <input
            type="range"
            min="0.5"
            max="2.5"
            step="0.1"
            value={settings.excursionScale}
            onChange={(e) => onUpdateSettings({ excursionScale: parseFloat(e.target.value) })}
            data-testid="excursion-slider"
            className="w-full accent-orange-500"
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-neutral-800 text-xs">
        <div className="flex items-center space-x-4">
          <label className="flex items-center space-x-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.wireframe}
              onChange={(e) => onUpdateSettings({ wireframe: e.target.checked })}
              className="accent-orange-500 rounded"
            />
            <span className="font-mono text-neutral-300">Wireframe Grille</span>
          </label>
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-neutral-400 font-mono">Orbit Speed:</span>
          <input
            type="range"
            min="0"
            max="1.5"
            step="0.1"
            value={settings.orbitSpeed}
            onChange={(e) => onUpdateSettings({ orbitSpeed: parseFloat(e.target.value) })}
            className="w-24 accent-orange-500"
          />
        </div>
      </div>
    </div>
  );
};
