# Phase 15 — Speaker-Stack Visualizer & Web MIDI

**Status:** Implemented and integrated in `web/src/App.tsx` (visualizer, controls,
MIDI modal, live `AnalyserNode` graph, MIDI→visual/playback mapping with
250 ms note debounce). Remaining: physical-controller verification and
mobile frame-time profiling (see checklist).

**Repository:** `murphieslaw23/mix-analyst`  
**Branch:** `main`  
**Implementation commit:** `fe026d8e7f377ddb9812b819b648b74f711cd2ea`  
**Preceding broadcast work:** Phase 14, `aa56fb9da30334625d6c90dbdce440a4e26ea6ca`

## Scope

Phase 15 provides client-side building blocks for an audio-reactive sound-system view and browser MIDI input:

- A projected 3D speaker-rig renderer using a `CanvasRenderingContext2D` canvas.
- Three rig geometries: `wall_of_sound`, `mechanical_totem`, and `underground_rig`.
- Reactive sub, mid, and high-band telemetry sourced from an optional Web Audio `AnalyserNode`.
- User-selectable SYCO23-aligned rust, crimson, amber, oxidized copper, and ochre palettes.
- Drag-to-orbit interaction, automatic orbit, cabinet-cone excursion, horn illumination, and a sub-triggered strobe effect.
- Web MIDI device discovery, hot-plug rebinding, device selection, persistent mappings, mapping presets, and MIDI Learn.
- UI components for visualizer configuration and Web MIDI mapping.

## Files

| Path | Responsibility |
| --- | --- |
| `web/src/visualizer/SpeakerStackVisualizer.tsx` | Canvas renderer, audio-band extraction, cabinet geometry, interaction, and telemetry HUD |
| `web/src/midi/WebMidiService.ts` | Web MIDI API access, CC/note dispatch, learn mode, presets, and `localStorage` persistence |
| `web/src/midi/useWebMidi.ts` | React state adapter for devices, mappings, MIDI messages, and parameter values |
| `web/src/components/VisualizerControls.tsx` | Rig/theme/excursion/orbit controls and MIDI configuration launcher |
| `web/src/components/MidiControllerModal.tsx` | Hardware picker, preset selection, MIDI Learn table, and live-message monitor |
| `web/tests/e2e/specs/speaker_stack_midi.spec.ts` | Intended Playwright coverage for visualizer controls and MIDI modal flows |

## Audio-reactive behavior

When an `AnalyserNode` and active playback state are supplied, the renderer reads frequency-domain byte data each animation frame and derives approximate bands as follows:

| Band | FFT bins | Visual target |
| --- | --- | --- |
| Sub | 1–6 | Scoop-cone excursion, stage glow, strobe threshold, `SUB` telemetry |
| Mid | 7–30 | Kick-bin movement and `MID` telemetry |
| High | 31–80 | Horn outline illumination |

The projection is a custom perspective transform painted to a 2D canvas. It does **not** instantiate a WebGL context or depend on Three.js. The Phase 15 naming is retained for continuity, but a production requirement for a hardware-accelerated WebGL renderer remains future work.

## Web MIDI contract

`WebMidiService` requests standard Web MIDI access without SysEx (`requestMIDIAccess({ sysex: false })`). It accepts MIDI CC and note-on events and emits normalized values in the range 0–1.

| MIDI target | Event type | Default generic mapping |
| --- | --- | --- |
| Master volume | CC | 1 |
| Sub-bass excursion | CC | 2 |
| Filter cutoff | CC | 3 |
| Strobe sensitivity | CC | 4 |
| Camera orbit | CC | 5 |
| Play/pause | Note-on | 60 |
| Previous cue | Note-on | 62 |
| Next cue | Note-on | 64 |

The service also defines mappings for Pioneer DDJ, Traktor Kontrol, and Akai APC families. Controller MIDI messages vary by device, mode, firmware, and user mapping; confirm actual messages with the live monitor and use MIDI Learn before relying on a preset during a broadcast.

Mappings are stored per browser origin under `syco23_midi_mapping`. No MIDI data is sent to the API or worker by the committed service.

## Integration status

The Phase 15 source modules were first added in commit `fe026d8`, and the
application wiring landed afterwards (`1472ee9` and follow-up `fix(phase15)`
commits): `App.tsx` mounts `SpeakerStackVisualizer`, `VisualizerControls`,
and `MidiControllerModal`, holds the shared `VisualizerSettings` state,
builds the playback `AudioContext`/`AnalyserNode` graph, maps CC values to
excursion/strobe/orbit/volume, and maps debounced note triggers to
play/pause and cue jumps. The HUD telemetry update is throttled to ~8 Hz.

Still open before calling Phase 15 done:

1. Test with a physical controller in a Chromium-family browser over a secure
   origin or localhost (presets are untested against real hardware).
2. Profile frame times on low-power mobile devices; if the animation loop
   causes UI churn, render telemetry directly to canvas.
3. Decide on `atmosphericHaze`: it is declared in `VisualizerSettings` but not
   consumed by the renderer — implement it or remove it from the contract.
4. Evaluate a WebGL/Three.js renderer if richer meshes, textures, or
   post-processing are required (current projection is 2D canvas).

## Operational notes

- Do not treat the HUD dB figures as calibrated measurements; they are display values derived from normalized FFT magnitudes.
- The renderer currently updates React telemetry state in its animation loop. Throttle HUD state updates or render telemetry directly to the canvas if frame-time profiling shows UI churn on mobile devices.
- The `atmosphericHaze` setting is declared but not consumed by the renderer; either implement it or remove it from the public settings contract.
- The `masterVolume`, `filterCutoff`, and note-action parameters are emitted by the MIDI hook but have no integration target in the committed application yet.
- Prefer WebGL/Three.js or a carefully profiled custom WebGL renderer if the visualizer must scale to richer meshes, textures, post-processing, or low-power mobile hardware.

## Acceptance checklist

- [x] Visualizer and controls are mounted from `App.tsx`
- [x] Playback audio provides a live `AnalyserNode`
- [x] MIDI access and permission denial states are visible and recoverable
- [ ] At least one physical controller is verified via MIDI Learn
- [ ] MIDI CC values produce the intended visual or playback changes
- [x] Note triggers are debounced and do not fire on note-off
- [x] Typecheck, production build, and Phase 15 Playwright test pass
- [ ] Chromium desktop and mobile/responsive behavior are manually checked
