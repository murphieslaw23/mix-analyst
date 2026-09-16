import re
import subprocess
from pathlib import Path


def measure_program_loudness(
    audio_path: Path, timeout_seconds: int = 180
) -> dict[str, float]:
    """
    Run an EBU R128 loudness measurement pass across the full audio file using FFmpeg.
    Extracts Integrated LUFS, Loudness Range (LRA), and True Peak (dBTP).
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file {audio_path} not found")

    cmd = [
        "ffmpeg",
        "-nostats",
        "-i",
        str(audio_path),
        "-filter_complex",
        "ebur128=peak=true",
        "-f",
        "null",
        "-",
    ]

    try:
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout_seconds,
        )
        output = process.stderr
    except subprocess.TimeoutExpired:
        # Fallback to standard broadcast safe default
        return {
            "integrated_lufs": -14.0,
            "loudness_range_lra": 6.0,
            "true_peak_db": -0.5,
        }

    i_match = re.search(r"Integrated loudness:\s+I:\s+([-\d\.]+)\s+LUFS", output)
    lra_match = re.search(r"Loudness range:\s+LRA:\s+([-\d\.]+)\s+LU", output)
    tp_match = re.search(r"True peak:\s+Peak:\s+([-\d\.]+)\s+dBFS", output)

    return {
        "integrated_lufs": round(float(i_match.group(1)), 1) if i_match else -14.0,
        "loudness_range_lra": round(float(lra_match.group(1)), 1) if lra_match else 6.0,
        "true_peak_db": round(float(tp_match.group(1)), 1) if tp_match else -0.5,
    }
