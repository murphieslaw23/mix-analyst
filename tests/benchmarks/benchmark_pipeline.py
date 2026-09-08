"""Benchmark suite for analysis pipeline throughput and latency."""

import io
import os
import time

import psutil
import soundfile as sf

from tests.fixtures.synthetic_audio import generate_synthetic_audio
from worker.analysis.bpm_detector import detect_window_tempo
from worker.analysis.key_detector import detect_key_and_camelot
from worker.analysis.loudness_analyzer import analyze_loudness


def benchmark_analysis_stages():
    """Run benchmark against synthetic 60s stream and output performance metrics."""
    print("Generating 60s synthetic mix fixture...")
    wav_bytes = generate_synthetic_audio(duration_sec=60.0, bpm=130.0, freq_hz=440.0)
    data, sr = sf.read(io.BytesIO(wav_bytes))

    process = psutil.Process(os.getpid())
    mem_start = process.memory_info().rss / (1024 * 1024)

    # 1. BPM Detection Benchmark
    t0 = time.perf_counter()
    detect_window_tempo(data, sr)
    t_bpm = time.perf_counter() - t0

    # 2. Key Detection Benchmark
    t0 = time.perf_counter()
    detect_key_and_camelot(data, sr)
    t_key = time.perf_counter() - t0

    # 3. Loudness Benchmark
    t0 = time.perf_counter()
    analyze_loudness(data, sr)
    t_loudness = time.perf_counter() - t0

    mem_end = process.memory_info().rss / (1024 * 1024)

    print("\n--- Pipeline Benchmark Results (60s audio) ---")
    print(f"BPM Analysis Time:       {t_bpm * 1000:.2f} ms")
    print(f"Key/Camelot Time:        {t_key * 1000:.2f} ms")
    print(f"Loudness Analysis Time:  {t_loudness * 1000:.2f} ms")
    print(f"Total Stage Latency:     {(t_bpm + t_key + t_loudness) * 1000:.2f} ms")
    print(f"Real-Time Factor (RTF):  {(t_bpm + t_key + t_loudness) / 60.0:.4f}x")
    print(f"Memory Delta:            {mem_end - mem_start:.2f} MB")
    print("----------------------------------------------\n")


if __name__ == "__main__":
    benchmark_analysis_stages()
