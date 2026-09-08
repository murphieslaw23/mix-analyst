"""AzuraCast radio station sync & webhook service."""

from typing import Any


class AzuraCastService:
    """Handles communication with AzuraCast station API and live metadata webhooks."""

    @staticmethod
    def format_azuracast_cue_points(
        tracks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Transform tracklist entries into AzuraCast cue markers / visual chapter tags."""
        markers = []
        for idx, track in enumerate(tracks, start=1):
            start_sec = track.get("start_time", 0.0)
            markers.append(
                {
                    "index": idx,
                    "title": track.get("title", f"Track {idx}"),
                    "artist": track.get("artist", "SYCO23"),
                    "start_seconds": round(start_sec, 2),
                    "bpm": track.get("bpm"),
                    "camelot_key": track.get("camelot_key"),
                }
            )
        return markers

    @staticmethod
    def build_sync_payload(
        mix_title: str, file_path: str, markers: list[dict[str, Any]], playlist: str
    ) -> dict[str, Any]:
        """Build AzuraCast media creation and playlist assignment payload."""
        return {
            "title": mix_title,
            "artist": "SYSTEM CORRUPT",
            "album": "SYCO23 Live Sets",
            "playlist": playlist,
            "file_path": file_path,
            "custom_fields": {
                "cue_points_count": len(markers),
                "station_broadcast": "syco23_live",
            },
            "chapters": markers,
        }

    @staticmethod
    def match_live_track(
        current_position_sec: float, tracks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Match the current broadcast playback head to the active mix track."""
        if not tracks:
            return {"title": "Live Mix", "artist": "SYSTEM CORRUPT"}

        active = tracks[0]
        for tr in tracks:
            if tr.get("start_time", 0.0) <= current_position_sec:
                active = tr
            else:
                break

        return {
            "title": active.get("title", "Untitled Track"),
            "artist": active.get("artist", "SYCO23"),
            "bpm": active.get("bpm"),
            "camelot_key": active.get("camelot_key"),
            "start_time": active.get("start_time", 0.0),
        }
