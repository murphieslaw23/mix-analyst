import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { 
  Sun, 
  Moon, 
  ShieldCheck, 
  HelpCircle, 
  Download, 
  Radio, 
  Layers, 
  Wrench, 
  CheckCircle,
  ExternalLink,
  Volume2,
  Sliders
} from 'lucide-react';
import { 
  SpeakerStackVisualizer, 
  VisualizerSettings 
} from './visualizer/SpeakerStackVisualizer';
import { VisualizerControls } from './components/VisualizerControls';
import { MidiControllerModal } from './components/MidiControllerModal';
import { useWebMidi } from './midi/useWebMidi';

const API_BASE = (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface MixData {
  id: string;
  original_filename: string;
  title?: string;
  duration_seconds?: number;
  bpm?: number;
  audio_url?: string;
  tracks?: Array<{
    id?: string;
    title?: string;
    artist?: string;
    start_time: number;
    end_time?: number;
    bpm?: number;
    camelot_key?: string;
  }>;
  transitions?: Array<{
    id?: string;
    start_time: number;
    end_time?: number;
    transition_type?: string;
    from_key?: string;
    to_key?: string;
    harmonic_compatibility?: string;
  }>;
}

export const App: React.FC = () => {
  const [mixes, setMixes] = useState<MixData[]>([]);
  const [selectedMix, setSelectedMix] = useState<MixData | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return (localStorage.getItem('syco_theme') as 'dark' | 'light') || 'dark';
  });
  const [activeTab, setActiveTab] = useState<'analyzer' | 'imprint' | 'support'>('analyzer');
  const [viewMode, setViewMode] = useState<'waveform' | 'stack3d' | 'dual'>('dual');
  const [notification, setNotification] = useState<string | null>(null);
  const [installPrompt, setInstallPrompt] = useState<any>(null);
  const [isMidiModalOpen, setIsMidiModalOpen] = useState<boolean>(false);

  const [visualizerSettings, setVisualizerSettings] = useState<VisualizerSettings>({
    architecture: 'wall_of_sound',
    theme: 'rust',
    excursionScale: 1.0,
    strobeSensitivity: 0.6,
    orbitSpeed: 0.2,
    wireframe: false,
    atmosphericHaze: true,
  });

  const {
    isSupported: isMidiSupported,
    isConnected: isMidiConnected,
    devices: midiDevices,
    selectedDeviceId: selectedMidiDevice,
    mapping: midiMapping,
    learningParam: midiLearningParam,
    lastMessage: lastMidiMessage,
    paramValues: midiParamValues,
    selectDevice: selectMidiDevice,
    startLearning: startMidiLearning,
    cancelLearning: cancelMidiLearning,
    applyPreset: applyMidiPreset,
  } = useWebMidi();

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceNodeRef = useRef<MediaElementAudioSourceNode | null>(null);
  const lastNoteActionTimeRef = useRef<number>(0);

  useEffect(() => {
    localStorage.setItem('syco_theme', theme);
    if (theme === 'light') {
      document.documentElement.classList.add('light-mode');
    } else {
      document.documentElement.classList.remove('light-mode');
    }
  }, [theme]);

  useEffect(() => {
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setInstallPrompt(e);
    };
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    return () => window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
  }, []);

  const triggerInstall = async () => {
    if (!installPrompt) return;
    installPrompt.prompt();
    const { outcome } = await installPrompt.userChoice;
    if (outcome === 'accepted') {
      setInstallPrompt(null);
      setNotification('SYSTEM CORRUPT PWA installed successfully!');
      setTimeout(() => setNotification(null), 4000);
    }
  };

  const setupAudioGraph = useCallback(() => {
    if (!audioCtxRef.current) {
      const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioCtxClass) {
        const ctx = new AudioCtxClass();
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.8;
        audioCtxRef.current = ctx;
        analyserRef.current = analyser;

        if (audioRef.current && !sourceNodeRef.current) {
          try {
            const src = ctx.createMediaElementSource(audioRef.current);
            src.connect(analyser);
            analyser.connect(ctx.destination);
            sourceNodeRef.current = src;
          } catch {
            // MediaElementSource fallback
          }
        }
      }
    }
    if (audioCtxRef.current && audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume();
    }
  }, []);

  const togglePlayback = useCallback(() => {
    setupAudioGraph();
    if (audioRef.current && audioRef.current.src) {
      if (audioRef.current.paused) {
        audioRef.current.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(true));
      } else {
        audioRef.current.pause();
        setIsPlaying(false);
      }
    } else {
      setIsPlaying((prev) => !prev);
    }
  }, [setupAudioGraph]);

  const jumpToCue = useCallback((direction: 'next' | 'prev') => {
    if (!selectedMix) return;
    const cues = (selectedMix.tracks || []).map((t) => t.start_time).sort((a, b) => a - b);
    if (cues.length === 0) return;

    if (direction === 'next') {
      const target = cues.find((c) => c > currentTime + 1.0);
      const newPos = target !== undefined ? target : cues[0];
      setCurrentTime(newPos);
      if (audioRef.current) audioRef.current.currentTime = newPos;
    } else {
      const target = [...cues].reverse().find((c) => c < currentTime - 1.0);
      const newPos = target !== undefined ? target : 0;
      setCurrentTime(newPos);
      if (audioRef.current) audioRef.current.currentTime = newPos;
    }
  }, [selectedMix, currentTime]);

  useEffect(() => {
    if (!midiParamValues) return;

    setVisualizerSettings((prev) => ({
      ...prev,
      excursionScale: Math.max(0.5, Math.min(2.5, midiParamValues.subBassExcursion * 2.5)),
      strobeSensitivity: Math.max(0.1, Math.min(1.0, midiParamValues.strobeSensitivity)),
      orbitSpeed: Math.max(0, Math.min(1.5, midiParamValues.cameraOrbit * 1.5)),
    }));

    if (audioRef.current && midiParamValues.masterVolume !== undefined) {
      audioRef.current.volume = Math.max(0, Math.min(1, midiParamValues.masterVolume));
    }
  }, [midiParamValues]);

  useEffect(() => {
    if (!lastMidiMessage || lastMidiMessage.type !== 'note_on' || lastMidiMessage.value === 0) return;
    const now = Date.now();
    if (now - lastNoteActionTimeRef.current < 250) return;

    if (lastMidiMessage.number === midiMapping.playPauseNote) {
      lastNoteActionTimeRef.current = now;
      togglePlayback();
    } else if (lastMidiMessage.number === midiMapping.cueJumpNextNote) {
      lastNoteActionTimeRef.current = now;
      jumpToCue('next');
    } else if (lastMidiMessage.number === midiMapping.cueJumpPrevNote) {
      lastNoteActionTimeRef.current = now;
      jumpToCue('prev');
    }
  }, [lastMidiMessage, midiMapping, togglePlayback, jumpToCue]);

  const fetchMixes = async () => {
    try {
      const res = await axios.get(`${API_BASE}/mixes`);
      setMixes(res.data || []);
      if (res.data && res.data.length > 0 && !selectedMix) {
        handleMixSelect(res.data[0].id);
      }
    } catch {
      setMixes([
        {
          id: 'demo-set-1',
          original_filename: 'SYCO23_Live_Tekno_Totem_Set.wav',
          title: 'SYCO23 — Live Sound-System Transmission 23',
          duration_seconds: 1800,
          bpm: 178.5,
          tracks: [
            { id: '1', title: 'Monolith Kick Intro', artist: 'System Corrupt', start_time: 0, camelot_key: '8A' },
            { id: '2', title: 'Acid Generator 303', artist: 'Murphies Law', start_time: 420, camelot_key: '9A' },
            { id: '3', title: 'Turbosound Excursion', artist: 'SYCO Sound', start_time: 980, camelot_key: '10A' },
            { id: '4', title: 'Tribe Pressure Wall', artist: 'Freetek 23', start_time: 1420, camelot_key: '11A' },
          ],
          transitions: [
            { id: 't1', start_time: 390, end_time: 435, transition_type: 'BASS_SWAP', from_key: '8A', to_key: '9A', harmonic_compatibility: 'Perfect Harmonic (+1)' },
            { id: 't2', start_time: 950, end_time: 1010, transition_type: 'CUT_DROP', from_key: '9A', to_key: '10A', harmonic_compatibility: 'Energy Boost (+1)' },
            { id: 't3', start_time: 1390, end_time: 1450, transition_type: 'CROSSFADE', from_key: '10A', to_key: '11A', harmonic_compatibility: 'Harmonic Flow' },
          ]
        }
      ]);
    }
  };

  useEffect(() => {
    fetchMixes();
  }, []);

  const handleMixSelect = async (mixId: string) => {
    try {
      const res = await axios.get(`${API_BASE}/mixes/${mixId}`);
      setSelectedMix(res.data);
      setCurrentTime(0);
      setIsPlaying(false);
      if (audioRef.current) {
        audioRef.current.currentTime = 0;
        audioRef.current.pause();
      }
    } catch {
      const found = mixes.find((m) => m.id === mixId);
      if (found) {
        setSelectedMix(found);
        setCurrentTime(0);
        setIsPlaying(false);
      }
    }
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !selectedMix || activeTab !== 'analyzer' || viewMode === 'stack3d') return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    const duration = selectedMix.duration_seconds || 1800;

    ctx.clearRect(0, 0, width, height);

    const bgGrad = ctx.createLinearGradient(0, 0, 0, height);
    if (theme === 'dark') {
      bgGrad.addColorStop(0, '#14161d');
      bgGrad.addColorStop(1, '#090a0d');
    } else {
      bgGrad.addColorStop(0, '#e5e7eb');
      bgGrad.addColorStop(1, '#d1d5db');
    }
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, width, height);

    const numBars = 180;
    const barWidth = width / numBars;
    for (let i = 0; i < numBars; i++) {
      const x = i * barWidth;
      const waveHeight = Math.sin(i * 0.15) * 0.3 + Math.cos(i * 0.08) * 0.4 + 0.3;
      const h = Math.max(8, waveHeight * (height * 0.7));
      const y = (height - h) / 2;

      ctx.fillStyle = theme === 'dark' ? '#ea580c' : '#c2410c';
      ctx.fillRect(x, y, barWidth - 1, h);
    }

    if (selectedMix.transitions) {
      selectedMix.transitions.forEach((trans) => {
        const startX = (trans.start_time / duration) * width;
        const endX = ((trans.end_time || trans.start_time + 30) / duration) * width;
        const zoneWidth = Math.max(6, endX - startX);

        ctx.fillStyle = theme === 'dark' ? 'rgba(217, 119, 6, 0.4)' : 'rgba(245, 158, 11, 0.45)';
        ctx.fillRect(startX, 0, zoneWidth, height);

        ctx.strokeStyle = '#d97706';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(startX, 0, zoneWidth, height);
      });
    }

    if (selectedMix.tracks) {
      selectedMix.tracks.forEach((tr, idx) => {
        const trX = (tr.start_time / duration) * width;
        ctx.strokeStyle = '#dc2626';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(trX, 0);
        ctx.lineTo(trX, height);
        ctx.stroke();

        ctx.fillStyle = theme === 'dark' ? '#fca5a5' : '#991b1b';
        ctx.font = '10px "JetBrains Mono", monospace';
        ctx.fillText(`T${idx + 1}: ${tr.camelot_key || ''}`, trX + 4, 14);
      });
    }

    const playheadX = (currentTime / duration) * width;
    ctx.strokeStyle = theme === 'dark' ? '#ffffff' : '#111827';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(playheadX, 0);
    ctx.lineTo(playheadX, height);
    ctx.stroke();

  }, [selectedMix, currentTime, theme, activeTab, viewMode]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current || !selectedMix) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const percentage = clickX / rect.width;
    const newTime = percentage * (selectedMix.duration_seconds || 1800);
    const clampedTime = Math.max(0, Math.min(newTime, selectedMix.duration_seconds || 1800));
    setCurrentTime(clampedTime);
    if (audioRef.current) audioRef.current.currentTime = clampedTime;
  };

  const copyYouTubeTimestamps = () => {
    if (!selectedMix || !selectedMix.tracks) return;
    const lines = selectedMix.tracks.map((t) => {
      const timeStr = formatTime(t.start_time);
      return `${timeStr} ${t.artist || 'Unknown'} - ${t.title || 'Untitled'} [${t.camelot_key || 'Key'}]`;
    });
    navigator.clipboard.writeText(lines.join('\n'));
    setNotification('YouTube timestamps copied to clipboard!');
    setTimeout(() => setNotification(null), 3000);
  };

  const formatTime = (secs: number) => {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = Math.floor(secs % 60);
    if (h > 0) {
      return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const isDark = theme === 'dark';

  return (
    <div className={`min-h-screen font-sans antialiased transition-colors duration-200 ${
      isDark ? 'bg-[#0d0e12] text-[#e0e2ec]' : 'bg-[#f3f4f6] text-[#1f2937]'
    }`}>
      <audio
        ref={audioRef}
        src={selectedMix?.audio_url || ''}
        onTimeUpdate={() => {
          if (audioRef.current) setCurrentTime(audioRef.current.currentTime);
        }}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
        data-testid="main-audio-player"
        className="hidden"
      />

      <header className={`px-6 py-4 border-b flex flex-wrap items-center justify-between gap-4 sticky top-0 z-20 backdrop-blur ${
        isDark ? 'bg-[#0d0e12]/90 border-[#232630]' : 'bg-[#ffffff]/90 border-[#e5e7eb]'
      }`}>
        <div className="flex items-center gap-4">
          <div className="w-9 h-9 rounded-md bg-[#ea580c] flex items-center justify-center font-black text-white shadow-lg shadow-orange-900/30">
            23
          </div>
          <div>
            <h1 className="text-xl font-black uppercase tracking-wider text-[#ea580c] flex items-center gap-2">
              SYSTEM CORRUPT <span className={isDark ? 'text-[#888] font-light' : 'text-[#6b7280] font-light'}>| MIX ANALYST</span>
            </h1>
            <p className={`text-[10px] uppercase tracking-widest font-mono ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>
              Sound-System Transition & 3D Speaker Stack Engine
            </p>
          </div>
        </div>

        <div className={`flex items-center p-1 rounded-lg border text-xs font-semibold ${
          isDark ? 'bg-[#15171e] border-[#292c38]' : 'bg-[#e5e7eb] border-[#d1d5db]'
        }`}>
          <button
            onClick={() => setActiveTab('analyzer')}
            className={`px-3 py-1.5 rounded transition ${
              activeTab === 'analyzer'
                ? 'bg-[#ea580c] text-white shadow-sm'
                : isDark ? 'text-[#9ca3af] hover:text-white' : 'text-[#4b5563] hover:text-black'
            }`}
          >
            Mix Analyzer & 3D Rig
          </button>
          <button
            onClick={() => setActiveTab('support')}
            className={`px-3 py-1.5 rounded transition flex items-center gap-1.5 ${
              activeTab === 'support'
                ? 'bg-[#ea580c] text-white shadow-sm'
                : isDark ? 'text-[#9ca3af] hover:text-white' : 'text-[#4b5563] hover:text-black'
            }`}
          >
            <HelpCircle className="w-3.5 h-3.5" /> Support & Docs
          </button>
          <button
            onClick={() => setActiveTab('imprint')}
            className={`px-3 py-1.5 rounded transition flex items-center gap-1.5 ${
              activeTab === 'imprint'
                ? 'bg-[#ea580c] text-white shadow-sm'
                : isDark ? 'text-[#9ca3af] hover:text-white' : 'text-[#4b5563] hover:text-black'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" /> Imprint & Privacy
          </button>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsMidiModalOpen(true)}
            data-testid="header-midi-btn"
            className={`px-3 py-1.5 rounded-lg border text-xs font-mono flex items-center gap-2 transition ${
              isDark ? 'bg-[#15171e] border-[#292c38] text-neutral-300' : 'bg-white border-[#d1d5db] text-neutral-800'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isMidiConnected ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]' : 'bg-neutral-500'
              }`}
            />
            <span>MIDI {isMidiConnected ? 'ONLINE' : 'OFFLINE'}</span>
          </button>

          {installPrompt && (
            <button
              onClick={triggerInstall}
              className="px-3 py-1.5 bg-[#ea580c] hover:bg-[#c2410c] text-white rounded text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 shadow-md shadow-orange-950/40"
            >
              <Download className="w-3.5 h-3.5" /> Install App
            </button>
          )}

          <button
            onClick={() => setTheme(isDark ? 'light' : 'dark')}
            className={`p-2 rounded-lg border transition ${
              isDark ? 'bg-[#15171e] border-[#292c38] text-amber-400 hover:bg-[#1f222d]' : 'bg-[#ffffff] border-[#d1d5db] text-slate-700 hover:bg-[#f3f4f6]'
            }`}
            title={`Switch to ${isDark ? 'Light' : 'Dark'} Mode`}
          >
            {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
        </div>
      </header>

      {notification && (
        <div className="fixed bottom-6 right-6 z-50 bg-[#ea580c] text-white px-5 py-3 rounded-lg shadow-xl font-medium text-xs flex items-center gap-2 animate-bounce">
          <CheckCircle className="w-4 h-4" />
          {notification}
        </div>
      )}

      <main className="p-6 max-w-7xl mx-auto">
        {activeTab === 'analyzer' && (
          <div className="grid grid-cols-12 gap-6">
            <div className={`col-span-12 md:col-span-3 border rounded-lg p-4 ${
              isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'
            }`}>
              <div className="flex justify-between items-center mb-3">
                <h2 className={`text-xs font-bold uppercase tracking-widest ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>
                  Mix Archive
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#ea580c]/20 text-[#ea580c]">
                  {mixes.length} Sets
                </span>
              </div>
              <div className="space-y-2">
                {mixes.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => handleMixSelect(m.id)}
                    className={`w-full text-left p-3 rounded text-sm transition-all border ${
                      selectedMix?.id === m.id
                        ? isDark
                          ? 'bg-[#241a18] border-[#ea580c] text-white shadow'
                          : 'bg-orange-50 border-[#ea580c] text-[#c2410c] font-bold shadow-sm'
                        : isDark
                          ? 'bg-[#1a1c24] border-[#292c38] text-[#9ca3af] hover:border-[#4b5563]'
                          : 'bg-[#f9fafb] border-[#e5e7eb] text-[#4b5563] hover:border-[#cbd5e1]'
                    }`}
                  >
                    <div className="font-semibold truncate">{m.title || m.original_filename}</div>
                    <div className={`text-xs mt-1 flex justify-between font-mono ${isDark ? 'text-[#71717a]' : 'text-[#6b7280]'}`}>
                      <span>{formatTime(m.duration_seconds || 0)}</span>
                      <span>{m.bpm ? `${m.bpm.toFixed(1)} BPM` : 'Analyzed'}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="col-span-12 md:col-span-9 space-y-6">
              {selectedMix ? (
                <>
                  <div className={`flex items-center justify-between p-2 rounded-lg border ${
                    isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb]'
                  }`}>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setViewMode('dual')}
                        className={`px-3 py-1.5 rounded text-xs font-mono transition ${
                          viewMode === 'dual'
                            ? 'bg-[#ea580c] text-white font-bold'
                            : isDark ? 'text-neutral-400 hover:text-white' : 'text-neutral-600 hover:text-black'
                        }`}
                      >
                        DUAL VIEW
                      </button>
                      <button
                        onClick={() => setViewMode('stack3d')}
                        className={`px-3 py-1.5 rounded text-xs font-mono transition ${
                          viewMode === 'stack3d'
                            ? 'bg-[#ea580c] text-white font-bold'
                            : isDark ? 'text-neutral-400 hover:text-white' : 'text-neutral-600 hover:text-black'
                        }`}
                      >
                        3D SPEAKER RIG
                      </button>
                      <button
                        onClick={() => setViewMode('waveform')}
                        className={`px-3 py-1.5 rounded text-xs font-mono transition ${
                          viewMode === 'waveform'
                            ? 'bg-[#ea580c] text-white font-bold'
                            : isDark ? 'text-neutral-400 hover:text-white' : 'text-neutral-600 hover:text-black'
                        }`}
                      >
                        WAVEFORM TIMELINE
                      </button>
                    </div>

                    <button
                      onClick={() => setIsMidiModalOpen(true)}
                      className="text-xs font-mono text-orange-500 hover:underline flex items-center gap-1.5"
                    >
                      <Sliders className="w-3.5 h-3.5" /> MIDI Hardware Settings
                    </button>
                  </div>

                  {(viewMode === 'stack3d' || viewMode === 'dual') && (
                    <div className="space-y-3">
                      <SpeakerStackVisualizer
                        analyserNode={analyserRef.current}
                        settings={visualizerSettings}
                        isPlaying={isPlaying}
                      />
                      <VisualizerControls
                        settings={visualizerSettings}
                        onUpdateSettings={(newVals) =>
                          setVisualizerSettings((prev) => ({ ...prev, ...newVals }))
                        }
                        onOpenMidiModal={() => setIsMidiModalOpen(true)}
                        isMidiConnected={isMidiConnected}
                      />
                    </div>
                  )}

                  {(viewMode === 'waveform' || viewMode === 'dual') && (
                    <div className={`border rounded-lg p-5 ${
                      isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'
                    }`}>
                      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4">
                        <div>
                          <h3 className={`text-lg font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>
                            {selectedMix.title || selectedMix.original_filename}
                          </h3>
                          <p className={`text-xs font-mono mt-0.5 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
                            Position: {formatTime(currentTime)} / {formatTime(selectedMix.duration_seconds || 0)}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <a
                            href={`${API_BASE}/mixes/${selectedMix.id}/export/cue`}
                            download
                            className={`px-3 py-1.5 text-xs font-semibold rounded border transition ${
                              isDark
                                ? 'bg-[#1f222c] hover:bg-[#282c38] border-[#374151] text-[#d1d5db]'
                                : 'bg-[#f3f4f6] hover:bg-[#e5e7eb] border-[#d1d5db] text-[#374151]'
                            }`}
                          >
                            Export .CUE
                          </a>
                          <a
                            href={`${API_BASE}/mixes/${selectedMix.id}/export/rekordbox`}
                            download
                            className={`px-3 py-1.5 text-xs font-semibold rounded border transition ${
                              isDark
                                ? 'bg-[#1f222c] hover:bg-[#282c38] border-[#374151] text-[#d1d5db]'
                                : 'bg-[#f3f4f6] hover:bg-[#e5e7eb] border-[#d1d5db] text-[#374151]'
                            }`}
                          >
                            Rekordbox XML
                          </a>
                          <a
                            href={`${API_BASE}/mixes/${selectedMix.id}/export/traktor`}
                            download
                            className={`px-3 py-1.5 text-xs font-semibold rounded border transition ${
                              isDark
                                ? 'bg-[#1f222c] hover:bg-[#282c38] border-[#374151] text-[#d1d5db]'
                                : 'bg-[#f3f4f6] hover:bg-[#e5e7eb] border-[#d1d5db] text-[#374151]'
                            }`}
                          >
                            Traktor NML
                          </a>
                          <button
                            onClick={copyYouTubeTimestamps}
                            className="px-3 py-1.5 bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-semibold rounded shadow-sm"
                          >
                            Copy YouTube Timestamps
                          </button>
                        </div>
                      </div>

                      <div className="relative border rounded overflow-hidden cursor-crosshair border-[#374151]/40">
                        <canvas
                          ref={canvasRef}
                          width={900}
                          height={160}
                          onClick={handleCanvasClick}
                          className="w-full h-[160px] block"
                        />
                      </div>

                      <div className="mt-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
                        <div className="flex items-center gap-3">
                          <button
                            onClick={togglePlayback}
                            className={`px-4 py-1.5 rounded font-bold transition ${
                              isDark ? 'bg-[#252834] hover:bg-[#323646] text-white' : 'bg-[#e5e7eb] hover:bg-[#d1d5db] text-black'
                            }`}
                          >
                            {isPlaying ? 'PAUSE' : 'PLAY'}
                          </button>
                          <button
                            onClick={() => {
                              setCurrentTime(0);
                              if (audioRef.current) audioRef.current.currentTime = 0;
                            }}
                            className={`px-3 py-1.5 rounded transition ${
                              isDark ? 'bg-[#1f222c] hover:bg-[#2a2e3c] text-white' : 'bg-[#f3f4f6] hover:bg-[#e5e7eb] text-black'
                            }`}
                          >
                            RESTART
                          </button>
                        </div>
                        <div className={`flex gap-4 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
                          <span className="flex items-center gap-1.5">
                            <span className="w-2.5 h-2.5 bg-[#dc2626] rounded-sm inline-block"></span> Track Cues
                          </span>
                          <span className="flex items-center gap-1.5">
                            <span className="w-2.5 h-2.5 bg-[#d97706] rounded-sm inline-block"></span> Transition Zones
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className={`border rounded-lg p-4 ${
                      isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'
                    }`}>
                      <h4 className={`text-xs font-bold uppercase tracking-widest mb-3 ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>
                        Detected Tracks ({selectedMix.tracks?.length || 0})
                      </h4>
                      <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                        {selectedMix.tracks?.map((t, idx) => (
                          <div
                            key={t.id || idx}
                            onClick={() => {
                              setCurrentTime(t.start_time);
                              if (audioRef.current) audioRef.current.currentTime = t.start_time;
                            }}
                            className={`p-2.5 rounded flex items-center justify-between text-xs cursor-pointer border transition ${
                              isDark
                                ? 'bg-[#1a1c24] hover:bg-[#20232e] border-[#292c38]'
                                : 'bg-[#f9fafb] hover:bg-[#f3f4f6] border-[#e5e7eb]'
                            }`}
                          >
                            <div>
                              <div className={`font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>
                                {idx + 1}. {t.title || 'Unknown Track'}
                              </div>
                              <div className={`text-[11px] ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>
                                {t.artist || 'Unknown Artist'}
                              </div>
                            </div>
                            <div className="text-right">
                              <span className="px-1.5 py-0.5 bg-[#ea580c]/20 text-[#ea580c] rounded border border-[#ea580c]/30 text-[10px] font-mono font-bold">
                                {t.camelot_key || 'KEY'}
                              </span>
                              <div className={`mt-1 font-mono text-[11px] ${isDark ? 'text-[#71717a]' : 'text-[#9ca3af]'}`}>
                                {formatTime(t.start_time)}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className={`border rounded-lg p-4 ${
                      isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'
                    }`}>
                      <h4 className={`text-xs font-bold uppercase tracking-widest mb-3 ${isDark ? 'text-[#8c909e]' : 'text-[#6b7280]'}`}>
                        Harmonic Transitions ({selectedMix.transitions?.length || 0})
                      </h4>
                      <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                        {selectedMix.transitions?.map((tr, idx) => (
                          <div
                            key={tr.id || idx}
                            onClick={() => {
                              setCurrentTime(tr.start_time);
                              if (audioRef.current) audioRef.current.currentTime = tr.start_time;
                            }}
                            className={`p-2.5 rounded text-xs cursor-pointer border transition ${
                              isDark
                                ? 'bg-[#1a1c24] hover:bg-[#20232e] border-[#292c38]'
                                : 'bg-[#f9fafb] hover:bg-[#f3f4f6] border-[#e5e7eb]'
                            }`}
                          >
                            <div className="flex justify-between items-center">
                              <span className="font-bold text-[#ea580c] uppercase">{tr.transition_type || 'MIX'}</span>
                              <span className={`font-mono ${isDark ? 'text-[#71717a]' : 'text-[#6b7280]'}`}>{formatTime(tr.start_time)}</span>
                            </div>
                            <div className={`flex justify-between items-center mt-2 ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
                              <span>
                                Key Shift: <span className={`font-mono font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{tr.from_key || '?'} → {tr.to_key || '?'}</span>
                              </span>
                              <span className="text-[10px] px-1.5 py-0.5 bg-[#0f766e]/20 text-[#14b8a6] rounded border border-[#0f766e]/40 font-mono">
                                {tr.harmonic_compatibility || 'Harmonic'}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <div className={`p-12 text-center rounded-lg border ${
                  isDark ? 'bg-[#15171e] border-[#232630] text-[#71717a]' : 'bg-white border-[#e5e7eb] text-[#6b7280]'
                }`}>
                  Select a mix from the archive to view waveform and transition analytics.
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'support' && (
          <div className="space-y-6">
            <div className={`border rounded-lg p-6 ${isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'}`}>
              <h2 className="text-xl font-bold text-[#ea580c] uppercase tracking-wide flex items-center gap-2 mb-4">
                <Wrench className="w-5 h-5" /> Sound-System Engineering & Support
              </h2>
              <p className={`text-sm leading-relaxed mb-6 ${isDark ? 'text-[#9ca3af]' : 'text-[#4b5563]'}`}>
                Mix Analyst is tailored specifically for underground sound-system culture (freetekno, hardtek, jungle, acidcore). Below are operational guidelines and troubleshooting steps for continuous DJ mix analysis and hardware compliance.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className={`p-4 rounded-lg border ${isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]'}`}>
                  <h3 className="font-bold text-sm text-[#ea580c] mb-2 flex items-center gap-2">
                    <Volume2 className="w-4 h-4" /> EBU R128 Loudness Targets
                  </h3>
                  <p className={`text-xs leading-relaxed ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
                    For outdoor freetekno speaker stacks, master target is <strong>-14.0 LUFS</strong> Integrated with True Peak capped at <strong>-0.5 dBTP</strong> to avoid DAC inter-sample clipping on high-powered amplifiers.
                  </p>
                </div>

                <div className={`p-4 rounded-lg border ${isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]'}`}>
                  <h3 className="font-bold text-sm text-[#14b8a6] mb-2 flex items-center gap-2">
                    <Layers className="w-4 h-4" /> Demucs 4-Stem GPU Processing
                  </h3>
                  <p className={`text-xs leading-relaxed ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
                    Stem separation requires CUDA or Apple Silicon acceleration. On CPU workers, 30-minute sets process in ~180s using multi-threaded PyTorch chunking.
                  </p>
                </div>

                <div className={`p-4 rounded-lg border ${isDark ? 'bg-[#1a1c24] border-[#292c38]' : 'bg-[#f9fafb] border-[#e5e7eb]'}`}>
                  <h3 className="font-bold text-sm text-[#f59e0b] mb-2 flex items-center gap-2">
                    <Radio className="w-4 h-4" /> AzuraCast Sync Protocol
                  </h3>
                  <p className={`text-xs leading-relaxed ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'}`}>
                    Dynamic cue sheets sync automatically over WebSocket/REST webhooks to inject upcoming artist tags and energy transitions to 24/7 web radio streams.
                  </p>
                </div>
              </div>
            </div>

            <div className={`border rounded-lg p-6 ${isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'}`}>
              <h3 className="text-base font-bold text-white mb-3">Community & Issue Reporting</h3>
              <p className={`text-xs ${isDark ? 'text-[#9ca3af]' : 'text-[#6b7280]'} mb-4`}>
                Need assistance with custom audio processing pipelines, container deployments, or station webhooks? Open an issue on GitHub:
              </p>
              <a
                href="https://github.com/murphieslaw23/mix-analyst/issues"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold rounded"
              >
                GitHub Issue Tracker <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        )}

        {activeTab === 'imprint' && (
          <div className="space-y-6">
            <div className={`border rounded-lg p-6 space-y-6 ${isDark ? 'bg-[#15171e] border-[#232630]' : 'bg-white border-[#e5e7eb] shadow-sm'}`}>
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
            </div>
          </div>
        )}
      </main>

      <MidiControllerModal
        isOpen={isMidiModalOpen}
        onClose={() => setIsMidiModalOpen(false)}
        isSupported={isMidiSupported}
        devices={midiDevices}
        selectedDeviceId={selectedMidiDevice}
        onSelectDevice={selectMidiDevice}
        mapping={midiMapping}
        learningParam={midiLearningParam}
        onStartLearning={startMidiLearning}
        onCancelLearning={cancelMidiLearning}
        onApplyPreset={applyMidiPreset}
        lastMessage={lastMidiMessage}
      />
    </div>
  );
};

export default App;
