"""Benchmark suite for analysis pipeline throughput and latency."""
import time
import os
import io
import tempfile
from pathlib import Path

import psutil
from tests.fixtures.synthetic_audio import generate_synthetic_audio
from worker.analysis.bpm_detector import detect_bpm
from worker.analysis.key_detector import detect_window_key
from worker.analysis.loudness_analyzer import measure_program_loudness
import soundfile as sf


def benchmark_analysis_stages():
    """Run benchmark against synthetic 60s stream and output performance metrics."""
    print("Generating 60s synthetic mix fixture...")
    wav_bytes = generate_synthetic_audio(duration_sec=60.0, bpm=130.0, freq_hz=440.0)
    data, sr = sf.read(io.BytesIO(wav_bytes))

    with tempfile.TemporaryDirectory(prefix="mixanalyst-bench-") as tmpdir:
        bench_file = Path(tmpdir) / "bench_mix.wav"
        bench_file.write_bytes(wav_bytes)

        process = psutil.Process(os.getpid())
        mem_start = process.memory_info().rss / (1024 * 1024)

        # 1. BPM Detection Benchmark
        t0 = time.perf_counter()
        bpm_res = detect_bpm(data, sr)
        t_bpm = time.perf_counter() - t0

        # 2. Key Detection Benchmark
        t0 = time.perf_counter()
        key_name, camelot_code, key_conf = detect_window_key(data, sr)
        t_key = time.perf_counter() - t0

        # 3. Loudness Benchmark (EBU R128 pass over the real file)
        t0 = time.perf_counter()
        loudness_res = measure_program_loudness(bench_file)
        t_loudness = time.perf_counter() - t0

        mem_end = process.memory_info().rss / (1024 * 1024)

        print("\n--- Pipeline Benchmark Results (60s audio) ---")
        print(f"BPM Estimate:            {bpm_res['bpm']} (conf {bpm_res['confidence']})")
        print(f"Key Estimate:            {key_name} [{camelot_code}] (conf {key_conf})")
        print(f"Integrated Loudness:     {loudness_res['integrated_lufs']} LUFS")
        print(f"BPM Analysis Time:       {t_bpm * 1000:.2f} ms")
        print(f"Key/Camelot Time:        {t_key * 1000:.2f} ms")
        print(f"Loudness Analysis Time:  {t_loudness * 1000:.2f} ms")
        print(f"Total Stage Latency:     {(t_bpm + t_key + t_loudness) * 1000:.2f} ms")
        print(f"Real-Time Factor (RTF):  {(t_bpm + t_key + t_loudness) / 60.0:.4f}x")
        print(f"Memory Delta:            {mem_end - mem_start:.2f} MB")
        print("----------------------------------------------\n")


if __name__ == "__main__":
    benchmark_analysis_stages()
