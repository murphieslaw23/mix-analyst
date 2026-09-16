"""Test mix and audio waveform fixtures generator."""

import io
import math
import struct
import wave

import numpy as np


def generate_synthetic_audio(
    duration_sec: float = 30.0,
    sample_rate: int = 22050,
    bpm: float = 120.0,
    freq_hz: float = 440.0,
) -> bytes:
    """Generate a valid in-memory WAV audio file with beats and harmonic tones."""
    num_samples = int(duration_sec * sample_rate)
    buffer = io.BytesIO()

    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        # Beat interval in samples
        beat_interval = int(sample_rate * (60.0 / bpm))

        frames = bytearray()
        for i in range(num_samples):
            # Base harmonic tone
            t = float(i) / sample_rate
            tone = 0.5 * math.sin(2.0 * math.pi * freq_hz * t)

            # Kick drum transient on each beat
            beat_pos = i % beat_interval
            if beat_pos < int(sample_rate * 0.05):
                decay = math.exp(-beat_pos / (sample_rate * 0.015))
                kick = (
                    0.8
                    * math.sin(2.0 * math.pi * 60.0 * (beat_pos / sample_rate))
                    * decay
                )
            else:
                kick = 0.0

            sample_val = int(np.clip(tone + kick, -1.0, 1.0) * 32767)
            frames.extend(struct.pack("<h", sample_val))

        wav_file.writeframes(frames)

    return buffer.getvalue()


def generate_multi_track_mix(
    duration_sec: float = 60.0, sample_rate: int = 22050
) -> bytes:
    """Generate a multi-track mix fixture with distinct transition zones."""
    # Track 1: 0-35s at 128 BPM (A minor / 8A: 440Hz)
    # Track 2: 25-60s at 130 BPM (E minor / 9A: 659.25Hz) with 10s crossfade (25s - 35s)
    num_samples = int(duration_sec * sample_rate)
    buffer = io.BytesIO()

    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        frames = bytearray()
        for i in range(num_samples):
            t = float(i) / sample_rate

            # Track 1 amplitude
            if t < 25.0:
                t1_gain = 1.0
                t2_gain = 0.0
            elif t <= 35.0:
                alpha = (t - 25.0) / 10.0
                t1_gain = math.cos(alpha * math.pi / 2.0)
                t2_gain = math.sin(alpha * math.pi / 2.0)
            else:
                t1_gain = 0.0
                t2_gain = 1.0

            # Tone 1 (440 Hz)
            t1_beat_interval = int(sample_rate * (60.0 / 128.0))
            t1_tone = 0.4 * math.sin(2.0 * math.pi * 440.0 * t)
            t1_pos = i % t1_beat_interval
            t1_kick = (
                0.7
                * math.sin(2.0 * math.pi * 65.0 * (t1_pos / sample_rate))
                * math.exp(-t1_pos / (sample_rate * 0.02))
                if t1_pos < sample_rate * 0.05
                else 0.0
            )

            # Tone 2 (659.25 Hz)
            t2_beat_interval = int(sample_rate * (60.0 / 130.0))
            t2_tone = 0.4 * math.sin(2.0 * math.pi * 659.25 * t)
            t2_pos = i % t2_beat_interval
            t2_kick = (
                0.7
                * math.sin(2.0 * math.pi * 70.0 * (t2_pos / sample_rate))
                * math.exp(-t2_pos / (sample_rate * 0.02))
                if t2_pos < sample_rate * 0.05
                else 0.0
            )

            mixed = (t1_tone + t1_kick) * t1_gain + (t2_tone + t2_kick) * t2_gain
            sample_val = int(np.clip(mixed, -1.0, 1.0) * 32767)
            frames.extend(struct.pack("<h", sample_val))

        wav_file.writeframes(frames)

    return buffer.getvalue()
