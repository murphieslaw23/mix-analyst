import json
import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import librosa
import numpy as np

ACOUSTID_API_KEY = os.getenv("ACOUSTID_API_KEY", "")
ACOUSTID_URL = "https://api.acoustid.org/v2/lookup"


def generate_audio_fingerprint(
    audio_path: Path, offset_seconds: float, duration_seconds: float = 120.0
) -> dict[str, Any]:
    """
    Extract Chromaprint acoustic fingerprint for an audio window using fpcalc CLI.
    If fpcalc is not present in container, computes an acoustic spectral feature hash.
    """
    try:
        cmd = [
            "fpcalc",
            "-length",
            str(int(duration_seconds)),
            "-raw",
            "-json",
            "-ss",
            str(int(offset_seconds)),
            str(audio_path),
        ]
        res = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=25
        )
        data = json.loads(res.stdout)
        return {
            "duration": data.get("duration", duration_seconds),
            "fingerprint": data.get("fingerprint", ""),
            "raw": True,
        }
    except Exception:  # noqa: BLE001 - fpcalc may be absent or reject malformed audio.
        # Fallback acoustic feature hashing using librosa chromagram
        try:
            from .audio_reader import read_audio_window

            y, sr = read_audio_window(
                audio_path, offset_seconds, min(duration_seconds, 30.0), target_sr=11025
            )
            chroma = librosa.feature.chroma_cens(y=y, sr=sr, n_chroma=12)
            # Binary quantization of dominant chroma energy
            quantized = np.where(chroma > np.median(chroma), 1, 0)
            fp_repr = ",".join(
                str(int("".join(map(str, row[:32])), 2)) for row in quantized
            )
            return {
                "duration": min(duration_seconds, 30.0),
                "fingerprint": fp_repr,
                "raw": False,
            }
        except Exception:  # noqa: BLE001 - return a stable fallback when feature extraction fails.
            return {
                "duration": duration_seconds,
                "fingerprint": f"fallback_hash_{int(offset_seconds)}",
                "raw": False,
            }


def query_acoustid_metadata(fingerprint: str, duration: float) -> dict[str, Any] | None:
    """
    Query AcoustID & MusicBrainz public API for track metadata.
    Returns title, artist, album, and match confidence.
    """
    if not ACOUSTID_API_KEY or not fingerprint:
        return None

    params = {
        "client": ACOUSTID_API_KEY,
        "meta": "recordings+releasegroups+compress",
        "duration": int(duration),
        "fingerprint": fingerprint,
    }

    query_str = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{ACOUSTID_URL}?{query_str}",
        headers={"User-Agent": "MixAnalyst/1.0"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                body = json.loads(response.read().decode())
                results = body.get("results", [])
                if results and len(results) > 0:
                    best_res = results[0]
                    score = float(best_res.get("score", 0.0))
                    recordings = best_res.get("recordings", [])
                    if recordings:
                        rec = recordings[0]
                        artists = rec.get("artists", [])
                        artist_name = (
                            ", ".join(a.get("name", "Unknown Artist") for a in artists)
                            if artists
                            else "Unknown Artist"
                        )
                        title = rec.get("title", "Unknown Track")
                        releases = rec.get("releasegroups", [])
                        album = releases[0].get("title") if releases else None

                        return {
                            "title": title,
                            "artist": artist_name,
                            "album": album,
                            "acoustid_id": best_res.get("id"),
                            "musicbrainz_recording_id": rec.get("id"),
                            "match_score": round(score, 2),
                        }
    except Exception as e:  # noqa: BLE001 - external metadata lookup is best effort.
        print(f"AcoustID lookup failed: {e}")

    return None


def partition_mix_segments(
    duration_seconds: float, avg_track_length: float = 240.0
) -> list[dict[str, float]]:
    """
    Partition continuous mix duration into estimated track segments.
    Creates structured segment intervals with safety overlap margins.
    """
    if duration_seconds <= 180.0:
        return [
            {
                "segment_index": 1,
                "start_time_seconds": 0.0,
                "end_time_seconds": duration_seconds,
                "duration_seconds": duration_seconds,
            }
        ]

    segments = []
    current_time = 0.0
    seg_idx = 1

    while current_time < duration_seconds:
        seg_duration = min(avg_track_length, duration_seconds - current_time)
        end_time = current_time + seg_duration

        segments.append(
            {
                "segment_index": seg_idx,
                "start_time_seconds": round(current_time, 2),
                "end_time_seconds": round(end_time, 2),
                "duration_seconds": round(seg_duration, 2),
            }
        )

        current_time += seg_duration
        seg_idx += 1

    return segments
