import { useState, useEffect, useCallback } from 'react';
import {
  webMidiService,
  MidiDevice,
  MidiMapping,
  MidiLogMessage,
  MidiParamKey,
  DEFAULT_PRESETS,
} from './WebMidiService';

export function useWebMidi() {
  const [isSupported, setIsSupported] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [devices, setDevices] = useState<MidiDevice[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [mapping, setMapping] = useState<MidiMapping>(webMidiService.getMapping());
  const [learningParam, setLearningParam] = useState<MidiParamKey | null>(null);
  const [lastMessage, setLastMessage] = useState<MidiLogMessage | null>(null);
  const [paramValues, setParamValues] = useState<Record<MidiParamKey, number>>({
    masterVolume: 0.8,
    subBassExcursion: 1.0,
    filterCutoff: 1.0,
    strobeSensitivity: 0.5,
    cameraOrbit: 0.2,
    playPause: 0,
    cueJumpPrev: 0,
    cueJumpNext: 0,
  });

  useEffect(() => {
    const supported = webMidiService.isSupported();
    setIsSupported(supported);
    if (!supported) return;

    webMidiService.init().then((connected) => {
      setIsConnected(connected);
      setDevices(webMidiService.getDevices());
    });

    const unsubDevices = webMidiService.onDevicesChanged((devs) => {
      setDevices(devs);
      setIsConnected(devs.length > 0);
    });

    const unsubParams = webMidiService.subscribe((param, val, raw) => {
      setParamValues((prev) => ({ ...prev, [param]: val }));
      setLastMessage(raw);
    });

    const unsubRaw = webMidiService.onRawMessage((msg) => {
      setLastMessage(msg);
      setLearningParam(webMidiService.getLearningParam());
      setMapping(webMidiService.getMapping());
    });

    return () => {
      unsubDevices();
      unsubParams();
      unsubRaw();
    };
  }, []);

  const selectDevice = useCallback((id: string | null) => {
    setSelectedDeviceId(id);
    webMidiService.selectDevice(id);
  }, []);

  const startLearning = useCallback((param: MidiParamKey) => {
    setLearningParam(param);
    webMidiService.startLearning(param);
  }, []);

  const cancelLearning = useCallback(() => {
    setLearningParam(null);
    webMidiService.cancelLearning();
  }, []);

  const applyPreset = useCallback((presetKey: keyof typeof DEFAULT_PRESETS) => {
    webMidiService.applyPreset(presetKey);
    setMapping(webMidiService.getMapping());
  }, []);

  const updateMapping = useCallback((newMapping: MidiMapping) => {
    webMidiService.setMapping(newMapping);
    setMapping(newMapping);
  }, []);

  return {
    isSupported,
    isConnected,
    devices,
    selectedDeviceId,
    mapping,
    learningParam,
    lastMessage,
    paramValues,
    selectDevice,
    startLearning,
    cancelLearning,
    applyPreset,
    updateMapping,
  };
}
