// Web MIDI API Hardware Service for SYCO23 / Mix-Analyst
// Supports Pioneer DDJ, Traktor Kontrol, Akai APC, Novation, and generic MIDI controllers

export interface MidiMapping {
  masterVolumeCc?: number;
  subBassExcursionCc?: number;
  filterCutoffCc?: number;
  strobeSensitivityCc?: number;
  cameraOrbitCc?: number;
  playPauseNote?: number;
  cueJumpPrevNote?: number;
  cueJumpNextNote?: number;
  channel?: number; // 0 = all channels, 1-16
}

export interface MidiDevice {
  id: string;
  name: string;
  manufacturer: string;
  state: string;
  type: string;
}

export interface MidiLogMessage {
  id: string;
  timestamp: number;
  channel: number;
  type: 'cc' | 'note_on' | 'note_off' | 'pitch_bend' | 'other';
  number: number;
  value: number;
  normalized: number;
}

export type MidiParamKey =
  | 'masterVolume'
  | 'subBassExcursion'
  | 'filterCutoff'
  | 'strobeSensitivity'
  | 'cameraOrbit'
  | 'playPause'
  | 'cueJumpPrev'
  | 'cueJumpNext';

const STORAGE_KEY = 'syco23_midi_mapping';

export const DEFAULT_PRESETS: Record<string, MidiMapping> = {
  pioneer_ddj: {
    masterVolumeCc: 7,
    subBassExcursionCc: 19,
    filterCutoffCc: 23,
    strobeSensitivityCc: 20,
    cameraOrbitCc: 21,
    playPauseNote: 11,
    cueJumpPrevNote: 12,
    cueJumpNextNote: 13,
    channel: 0,
  },
  traktor_kontrol: {
    masterVolumeCc: 14,
    subBassExcursionCc: 16,
    filterCutoffCc: 17,
    strobeSensitivityCc: 18,
    cameraOrbitCc: 19,
    playPauseNote: 36,
    cueJumpPrevNote: 37,
    cueJumpNextNote: 38,
    channel: 0,
  },
  akai_apc: {
    masterVolumeCc: 48,
    subBassExcursionCc: 49,
    filterCutoffCc: 50,
    strobeSensitivityCc: 51,
    cameraOrbitCc: 52,
    playPauseNote: 0,
    cueJumpPrevNote: 1,
    cueJumpNextNote: 2,
    channel: 0,
  },
  generic_8knob: {
    masterVolumeCc: 1,
    subBassExcursionCc: 2,
    filterCutoffCc: 3,
    strobeSensitivityCc: 4,
    cameraOrbitCc: 5,
    playPauseNote: 60,
    cueJumpPrevNote: 62,
    cueJumpNextNote: 64,
    channel: 0,
  },
};

type MidiEventListener = (param: MidiParamKey, value: number, rawEvent: MidiLogMessage) => void;
type DeviceChangeListener = (devices: MidiDevice[]) => void;
type RawMidiListener = (msg: MidiLogMessage) => void;

export class WebMidiService {
  private midiAccess: any = null;
  private isInitialized = false;
  private mapping: MidiMapping = { ...DEFAULT_PRESETS.generic_8knob };
  private eventListeners: Set<MidiEventListener> = new Set();
  private deviceListeners: Set<DeviceChangeListener> = new Set();
  private rawListeners: Set<RawMidiListener> = new Set();
  private learningParam: MidiParamKey | null = null;
  private selectedDeviceId: string | null = null;

  constructor() {
    this.loadMapping();
  }

  public isSupported(): boolean {
    return typeof navigator !== 'undefined' && 'requestMIDIAccess' in navigator;
  }

  public async init(): Promise<boolean> {
    if (!this.isSupported()) return false;
    if (this.isInitialized && this.midiAccess) return true;

    try {
      const midi = await (navigator as any).requestMIDIAccess({ sysex: false });
      this.midiAccess = midi;
      this.isInitialized = true;

      this.midiAccess.onstatechange = () => {
        this.notifyDevices();
        this.bindInputs();
      };

      this.bindInputs();
      this.notifyDevices();
      return true;
    } catch (err) {
      console.warn('[WebMidiService] MIDI access denied or unavailable:', err);
      return false;
    }
  }

  private bindInputs(): void {
    if (!this.midiAccess) return;
    const inputs = this.midiAccess.inputs.values();
    for (const input of inputs) {
      input.onmidimessage = (event: any) => this.handleMidiMessage(event, input.id);
    }
  }

  public getDevices(): MidiDevice[] {
    if (!this.midiAccess) return [];
    const devices: MidiDevice[] = [];
    const inputs = this.midiAccess.inputs.values();
    for (const input of inputs) {
      devices.push({
        id: input.id,
        name: input.name || 'Unknown MIDI Device',
        manufacturer: input.manufacturer || 'Generic',
        state: input.state,
        type: input.type,
      });
    }
    return devices;
  }

  public selectDevice(id: string | null): void {
    this.selectedDeviceId = id;
  }

  private handleMidiMessage(event: any, sourceId: string): void {
    if (this.selectedDeviceId && sourceId !== this.selectedDeviceId) return;

    const data = event.data;
    if (!data || data.length < 2) return;

    const status = data[0];
    const channel = (status & 0x0f) + 1;
    const command = status >> 4;
    const byte1 = data[1];
    const byte2 = data.length > 2 ? data[2] : 0;

    let msgType: MidiLogMessage['type'] = 'other';
    let normalized = byte2 / 127.0;

    if (command === 0x9) {
      msgType = byte2 > 0 ? 'note_on' : 'note_off';
    } else if (command === 0x8) {
      msgType = 'note_off';
      normalized = 0;
    } else if (command === 0xb) {
      msgType = 'cc';
    } else if (command === 0xe) {
      msgType = 'pitch_bend';
      const bendValue = (byte2 << 7) | byte1;
      normalized = bendValue / 16383.0;
    }

    const logMsg: MidiLogMessage = {
      id: Math.random().toString(36).substring(2, 9),
      timestamp: Date.now(),
      channel,
      type: msgType,
      number: byte1,
      value: byte2,
      normalized: Math.min(1.0, Math.max(0.0, normalized)),
    };

    // Notify raw listeners for UI monitors
    for (const listener of this.rawListeners) {
      listener(logMsg);
    }

    // Handle MIDI Learn
    if (this.learningParam) {
      this.bindLearnedParam(this.learningParam, msgType, byte1);
      this.learningParam = null;
      return;
    }

    // Dispatch to mapped parameters
    this.dispatchMappedControl(msgType, byte1, logMsg);
  }

  private bindLearnedParam(param: MidiParamKey, type: MidiLogMessage['type'], num: number): void {
    const updated = { ...this.mapping };
    if (type === 'cc') {
      if (param === 'masterVolume') updated.masterVolumeCc = num;
      if (param === 'subBassExcursion') updated.subBassExcursionCc = num;
      if (param === 'filterCutoff') updated.filterCutoffCc = num;
      if (param === 'strobeSensitivity') updated.strobeSensitivityCc = num;
      if (param === 'cameraOrbit') updated.cameraOrbitCc = num;
    } else if (type === 'note_on') {
      if (param === 'playPause') updated.playPauseNote = num;
      if (param === 'cueJumpPrev') updated.cueJumpPrevNote = num;
      if (param === 'cueJumpNext') updated.cueJumpNextNote = num;
    }
    this.mapping = updated;
    this.saveMapping();
  }

  private dispatchMappedControl(type: MidiLogMessage['type'], num: number, logMsg: MidiLogMessage): void {
    if (type === 'cc') {
      if (num === this.mapping.masterVolumeCc) this.emitParam('masterVolume', logMsg.normalized, logMsg);
      if (num === this.mapping.subBassExcursionCc) this.emitParam('subBassExcursion', logMsg.normalized, logMsg);
      if (num === this.mapping.filterCutoffCc) this.emitParam('filterCutoff', logMsg.normalized, logMsg);
      if (num === this.mapping.strobeSensitivityCc) this.emitParam('strobeSensitivity', logMsg.normalized, logMsg);
      if (num === this.mapping.cameraOrbitCc) this.emitParam('cameraOrbit', logMsg.normalized, logMsg);
    } else if (type === 'note_on' && logMsg.value > 0) {
      if (num === this.mapping.playPauseNote) this.emitParam('playPause', 1.0, logMsg);
      if (num === this.mapping.cueJumpPrevNote) this.emitParam('cueJumpPrev', 1.0, logMsg);
      if (num === this.mapping.cueJumpNextNote) this.emitParam('cueJumpNext', 1.0, logMsg);
    }
  }

  private emitParam(param: MidiParamKey, val: number, raw: MidiLogMessage): void {
    for (const listener of this.eventListeners) {
      listener(param, val, raw);
    }
  }

  private notifyDevices(): void {
    const devs = this.getDevices();
    for (const listener of this.deviceListeners) {
      listener(devs);
    }
  }

  public startLearning(param: MidiParamKey): void {
    this.learningParam = param;
  }

  public cancelLearning(): void {
    this.learningParam = null;
  }

  public getLearningParam(): MidiParamKey | null {
    return this.learningParam;
  }

  public getMapping(): MidiMapping {
    return { ...this.mapping };
  }

  public setMapping(mapping: MidiMapping): void {
    this.mapping = { ...mapping };
    this.saveMapping();
  }

  public applyPreset(presetKey: keyof typeof DEFAULT_PRESETS): void {
    if (DEFAULT_PRESETS[presetKey]) {
      this.mapping = { ...DEFAULT_PRESETS[presetKey] };
      this.saveMapping();
    }
  }

  public subscribe(listener: MidiEventListener): () => void {
    this.eventListeners.add(listener);
    return () => this.eventListeners.delete(listener);
  }

  public onDevicesChanged(listener: DeviceChangeListener): () => void {
    this.deviceListeners.add(listener);
    return () => this.deviceListeners.delete(listener);
  }

  public onRawMessage(listener: RawMidiListener): () => void {
    this.rawListeners.add(listener);
    return () => this.rawListeners.delete(listener);
  }

  private loadMapping(): void {
    if (typeof localStorage === 'undefined') return;
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        this.mapping = { ...this.mapping, ...JSON.parse(saved) };
      }
    } catch {
      // Ignore storage read errors
    }
  }

  private saveMapping(): void {
    if (typeof localStorage === 'undefined') return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.mapping));
    } catch {
      // Ignore storage write errors
    }
  }
}

export const webMidiService = new WebMidiService();
