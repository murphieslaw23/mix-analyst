import subprocess
import numpy as np
import io
import soundfile as sf
from pathlib import Path
from typing import Tuple


def read_audio_window(
    audio_path: Path,
    offset_seconds: float,
    duration_seconds: float,
    target_sr: int = 22050,
) -> Tuple[np.ndarray, int]:
    """
    Safely decode a bounded slice of audio directly from disk using FFmpeg stream piping.
    Consumes memory proportional ONLY to the window slice (e.g. 30 seconds), never the full mix.
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file {audio_path} not found")

    cmd = [
        "ffmpeg",
        "-nostats",
        "-ss", str(offset_seconds),
        "-t", str(duration_seconds),
        "-i", str(audio_path),
        "-f", "wav",
        "-ac", "1",               # Downmix to mono for analysis
        "-ar", str(target_sr),    # Standard analysis sample rate
        "-vn",
        "pipe:1",
    ]

    process = subprocess.run(
        cmd,
        capture_output=True,
        check=True,
        timeout=30,
    )

    data, sr = sf.read(io.BytesIO(process.stdout), dtype="float32")
    return data, sr
