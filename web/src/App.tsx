import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

interface TrackEntry {
  id: string;
  artist: string;
  title: string;
  start_time: number;
  end_time?: number;
  bpm?: number;
  camelot_key?: string;
  confidence?: number;
}

interface Transition {
  id: string;
  start_time: number;
  end_time?: number;
  transition_type: string;
  from_key?: string;
  to_key?: string;
  harmonic_compatibility?: string;
  energy_delta?: number;
}

interface MixData {
  id: string;
  title: string;
  original_filename: string;
  duration_seconds: number;
  bpm?: number;
  status: string;
  tracks?: TrackEntry[];
  transitions?: Transition[];
}

export const App: React.FC = () => {
  const [mixes, setMixes] = useState<MixData[]>([]);
  const [selectedMix, setSelectedMix] = useState<MixData | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [zoomLevel] = useState<number>(1);
  const [notification, setNotification] = useState<string | null>(null);
  
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const fetchMixes = async () => {
    try {
      const res = await axios.get(`${API_BASE}/mixes`);
      const data = Array.isArray(res.data) ? res.data : (res.data.items || []);
      setMixes(data);
      if (data.length > 0 && !selectedMix) {
        setSelectedMix(data[0]);
      }
    } catch (err) {
      console.error('Failed to load mixes', err);
    }
  };

  useEffect(() => {
    fetchMixes();
  }, []);

  const handleMixSelect = async (id: string) => {
    try {
      const res = await axios.get(`${API_BASE}/mixes/${id}`);
      setSelectedMix(res.data);
      setCurrentTime(0);
      setIsPlaying(false);
    } catch (err) {
      console.error('Failed to fetch mix details', err);
    }
  };

  // Waveform canvas rendering with cues & transition zones for long sets
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !selectedMix) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    const duration = selectedMix.duration_seconds || 1800;

    ctx.clearRect(0, 0, width, height);

    // Background gradient
    const bgGrad = ctx.createLinearGradient(0, 0, 0, height);
    bgGrad.addColorStop(0, '#121316');
    bgGrad.addColorStop(1, '#0a0a0c');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, width, height);

    // Draw base audio waveform mockup / bars
    const numBars = 180;
    const barWidth = width / numBars;
    for (let i = 0; i < numBars; i++) {
      const x = i * barWidth;
      
      // Calculate amplitude visualization
      const waveHeight = Math.sin(i * 0.15) * 0.3 + Math.cos(i * 0.08) * 0.4 + 0.3;
      const h = Math.max(8, waveHeight * (height * 0.7));
      const y = (height - h) / 2;

      // Color based on spectral presence (underground freetekno / sound system theme)
      ctx.fillStyle = '#b84224'; // Crimson / Rust orange
      ctx.fillRect(x, y, barWidth - 1, h);
    }

    // Draw Transition zones
    if (selectedMix.transitions) {
      selectedMix.transitions.forEach((trans) => {
        const startX = (trans.start_time / duration) * width;
        const endX = ((trans.end_time || trans.start_time + 30) / duration) * width;
        const zoneWidth = Math.max(6, endX - startX);

        ctx.fillStyle = 'rgba(217, 119, 6, 0.35)'; // Amber transition band
        ctx.fillRect(startX, 0, zoneWidth, height);

        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(startX, 0, zoneWidth, height);
      });
    }

    // Draw Track boundary markers
    if (selectedMix.tracks) {
      selectedMix.tracks.forEach((tr, idx) => {
        const trX = (tr.start_time / duration) * width;
        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(trX, 0);
        ctx.lineTo(trX, height);
        ctx.stroke();

        ctx.fillStyle = '#fca5a5';
        ctx.font = '10px monospace';
        ctx.fillText(`T${idx + 1}: ${tr.camelot_key || ''}`, trX + 4, 14);
      });
    }

    // Draw Playhead
    const playheadX = (currentTime / duration) * width;
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(playheadX, 0);
    ctx.lineTo(playheadX, height);
    ctx.stroke();

  }, [selectedMix, currentTime, zoomLevel]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current || !selectedMix) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const ratio = Math.max(0, Math.min(1, x / rect.width));
    const newTime = ratio * (selectedMix.duration_seconds || 1800);
    setCurrentTime(newTime);
    if (audioRef.current) {
      audioRef.current.currentTime = newTime;
    }
  };

  const copyYouTubeTimestamps = async () => {
    if (!selectedMix) return;
    try {
      const res = await axios.get(`${API_BASE}/mixes/${selectedMix.id}/export/youtube`);
      await navigator.clipboard.writeText(res.data);
      setNotification('YouTube timestamps copied to clipboard!');
      setTimeout(() => setNotification(null), 3000);
    } catch (err) {
      console.error('Failed to copy timestamps', err);
    }
  };

  const formatTime = (secs: number) => {
    const hours = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = Math.floor(secs % 60);
    if (hours > 0) {
      return `${hours}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="min-h-screen bg-[#0d0e12] text-[#e0e2ec] font-sans antialiased p-6">
      <header className="flex justify-between items-center mb-8 border-b border-[#232630] pb-4">
        <div>
          <h1 className="text-2xl font-black uppercase tracking-wider text-[#ea580c] flex items-center gap-2">
            SYSTEM CORRUPT <span className="text-[#888] font-light">| MIX ANALYST</span>
          </h1>
          <p className="text-xs text-[#8c909e] uppercase tracking-widest mt-1">Sound-System Transition & Cue Engine</p>
        </div>
        {notification && (
          <div className="bg-[#ea580c]/20 border border-[#ea580c] px-4 py-1.5 rounded text-xs text-[#ff8c42]">
            {notification}
          </div>
        )}
      </header>

      {/* Main Grid */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left Sidebar: Mixes */}
        <div className="col-span-12 md:col-span-3 bg-[#15171e] border border-[#232630] rounded-lg p-4">
          <h2 className="text-xs font-bold text-[#8c909e] uppercase tracking-widest mb-3">Mix Archive</h2>
          <div className="space-y-2">
            {mixes.map((m) => (
              <button
                key={m.id}
                onClick={() => handleMixSelect(m.id)}
                className={`w-full text-left p-3 rounded text-sm transition-all border ${
                  selectedMix?.id === m.id
                    ? 'bg-[#241a18] border-[#ea580c] text-white'
                    : 'bg-[#1a1c24] border-[#292c38] text-[#9ca3af] hover:border-[#4b5563]'
                }`}
              >
                <div className="font-semibold truncate">{m.title || m.original_filename}</div>
                <div className="text-xs text-[#71717a] mt-1 flex justify-between">
                  <span>{formatTime(m.duration_seconds || 0)}</span>
                  <span>{m.bpm ? `${m.bpm.toFixed(1)} BPM` : 'Analyzed'}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Center/Right Content Area */}
        <div className="col-span-12 md:col-span-9 space-y-6">
          {selectedMix ? (
            <>
              {/* Interactive Waveform Display */}
              <div className="bg-[#15171e] border border-[#232630] rounded-lg p-5">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-3">
                  <div>
                    <h3 className="text-lg font-bold text-white">{selectedMix.title || selectedMix.original_filename}</h3>
                    <p className="text-xs text-[#9ca3af]">
                      Position: {formatTime(currentTime)} / {formatTime(selectedMix.duration_seconds || 0)}
                    </p>
                  </div>
                  {/* Export Actions */}
                  <div className="flex flex-wrap gap-2">
                    <a
                      href={`${API_BASE}/mixes/${selectedMix.id}/export/cue`}
                      download
                      className="px-3 py-1.5 bg-[#1f222c] hover:bg-[#282c38] text-xs font-semibold rounded border border-[#374151] text-[#d1d5db]"
                    >
                      Export .CUE
                    </a>
                    <a
                      href={`${API_BASE}/mixes/${selectedMix.id}/export/rekordbox`}
                      download
                      className="px-3 py-1.5 bg-[#1f222c] hover:bg-[#282c38] text-xs font-semibold rounded border border-[#374151] text-[#d1d5db]"
                    >
                      Rekordbox XML
                    </a>
                    <a
                      href={`${API_BASE}/mixes/${selectedMix.id}/export/traktor`}
                      download
                      className="px-3 py-1.5 bg-[#1f222c] hover:bg-[#282c38] text-xs font-semibold rounded border border-[#374151] text-[#d1d5db]"
                    >
                      Traktor NML
                    </a>
                    <button
                      onClick={copyYouTubeTimestamps}
                      className="px-3 py-1.5 bg-[#ea580c] hover:bg-[#f97316] text-white text-xs font-semibold rounded"
                    >
                      Copy YouTube Timestamps
                    </button>
                  </div>
                </div>

                {/* Waveform Canvas */}
                <div className="relative border border-[#2d313d] rounded overflow-hidden cursor-crosshair">
                  <canvas
                    ref={canvasRef}
                    width={900}
                    height={160}
                    onClick={handleCanvasClick}
                    className="w-full h-[160px] block"
                  />
                </div>

                {/* Playback Controls */}
                <div className="mt-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs text-[#9ca3af]">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => setIsPlaying(!isPlaying)}
                      className="px-4 py-1.5 bg-[#252834] hover:bg-[#323646] text-white rounded font-bold"
                    >
                      {isPlaying ? 'PAUSE' : 'PLAY'}
                    </button>
                    <button
                      onClick={() => setCurrentTime(0)}
                      className="px-3 py-1.5 bg-[#1f222c] hover:bg-[#2a2e3c] rounded"
                    >
                      RESTART
                    </button>
                  </div>
                  <div className="flex gap-4">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 bg-[#ef4444] rounded-sm inline-block"></span> Track Cues
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 bg-[#f59e0b] rounded-sm inline-block"></span> Transition Zones
                    </span>
                  </div>
                </div>
              </div>

              {/* Detected Tracks & Transitions Breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Tracklist Table */}
                <div className="bg-[#15171e] border border-[#232630] rounded-lg p-4">
                  <h4 className="text-xs font-bold text-[#8c909e] uppercase tracking-widest mb-3">
                    Detected Tracks ({selectedMix.tracks?.length || 0})
                  </h4>
                  <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                    {selectedMix.tracks?.map((t, idx) => (
                      <div
                        key={t.id || idx}
                        onClick={() => setCurrentTime(t.start_time)}
                        className="p-2.5 bg-[#1a1c24] hover:bg-[#20232e] border border-[#292c38] rounded flex items-center justify-between text-xs cursor-pointer"
                      >
                        <div>
                          <div className="font-semibold text-white">
                            {idx + 1}. {t.title || 'Unknown Track'}
                          </div>
                          <div className="text-[#8c909e]">{t.artist || 'Unknown Artist'}</div>
                        </div>
                        <div className="text-right">
                          <span className="px-1.5 py-0.5 bg-[#29231f] text-[#f97316] rounded border border-[#7c2d12] text-[10px] font-mono">
                            {t.camelot_key || 'KEY'}
                          </span>
                          <div className="text-[#71717a] mt-1 font-mono">{formatTime(t.start_time)}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Transitions Table */}
                <div className="bg-[#15171e] border border-[#232630] rounded-lg p-4">
                  <h4 className="text-xs font-bold text-[#8c909e] uppercase tracking-widest mb-3">
                    Harmonic Transitions ({selectedMix.transitions?.length || 0})
                  </h4>
                  <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                    {selectedMix.transitions?.map((tr, idx) => (
                      <div
                        key={tr.id || idx}
                        onClick={() => setCurrentTime(tr.start_time)}
                        className="p-2.5 bg-[#1a1c24] hover:bg-[#20232e] border border-[#292c38] rounded text-xs cursor-pointer"
                      >
                        <div className="flex justify-between items-center">
                          <span className="font-bold text-[#fb923c] uppercase">{tr.transition_type || 'MIX'}</span>
                          <span className="font-mono text-[#71717a]">{formatTime(tr.start_time)}</span>
                        </div>
                        <div className="flex justify-between items-center mt-2 text-[#9ca3af]">
                          <span>
                            Key Shift: <span className="text-white font-mono">{tr.from_key || '?'} → {tr.to_key || '?'}</span>
                          </span>
                          <span className="text-[10px] px-1.5 py-0.5 bg-[#1e293b] text-[#38bdf8] rounded">
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
            <div className="p-12 text-center text-[#71717a] bg-[#15171e] rounded-lg border border-[#232630]">
              Select a mix from the archive to view waveform and transition analytics.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default App;
