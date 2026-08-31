import subprocess
import json
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, Dict, Any


class AudioProbeResult(BaseModel):
    duration_seconds: float
    sample_rate: int
    channels: int
    codec: str
    bit_rate: Optional[int] = None
    format_name: Optional[str] = None
    bits_per_sample: Optional[int] = None
    raw_metadata: Dict[str, Any] = {}


class AudioProbeError(Exception):
    pass


def probe_audio(file_path: Path, timeout_seconds: int = 30) -> AudioProbeResult:
    """Execute ffprobe safely to validate and inspect an audio file."""
    if not file_path.exists():
        raise AudioProbeError(f"Audio file does not exist: {file_path}")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration,size,bit_rate,format_name,tags:stream=codec_name,sample_rate,channels,bits_per_sample",
        "-of", "json",
        str(file_path),
    ]

    try:
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        raise AudioProbeError(f"ffprobe timed out after {timeout_seconds} seconds")
    except subprocess.CalledProcessError as e:
        raise AudioProbeError(f"ffprobe failed: {e.stderr.strip() or 'Invalid or corrupted audio file'}")
    except FileNotFoundError:
        raise AudioProbeError("ffprobe binary is not installed in the system environment")

    try:
        data = json.loads(process.stdout)
    except json.JSONDecodeError as e:
        raise AudioProbeError(f"Failed to parse ffprobe JSON output: {e}")

    streams = data.get("streams", [])
    audio_streams = [s for s in streams if s.get("sample_rate") or s.get("channels")]

    if not audio_streams:
        raise AudioProbeError("No valid audio stream found in media file")

    stream = audio_streams[0]
    fmt = data.get("format", {})

    duration = float(fmt.get("duration", 0.0))
    if duration <= 0:
        raise AudioProbeError("Audio duration is zero or invalid")

    sample_rate = int(stream.get("sample_rate", 44100))
    channels = int(stream.get("channels", 2))
    codec = stream.get("codec_name", "unknown")
    bit_rate = int(fmt.get("bit_rate")) if fmt.get("bit_rate") else None
    format_name = fmt.get("format_name")
    bits_per_sample = int(stream.get("bits_per_sample")) if stream.get("bits_per_sample") else None

    return AudioProbeResult(
        duration_seconds=duration,
        sample_rate=sample_rate,
        channels=channels,
        codec=codec,
        bit_rate=bit_rate,
        format_name=format_name,
        bits_per_sample=bits_per_sample,
        raw_metadata=fmt.get("tags", {}),
    )
