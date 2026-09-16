"""DJ Export & CUE Sheet generation service."""

import xml.etree.ElementTree as ET
from typing import Any
from xml.dom import minidom


def format_cue_time(seconds: float) -> str:
    """Format seconds into MM:SS:FF (75 frames/sec standard CUE format)."""
    total_frames = round(seconds * 75)
    total_seconds = total_frames // 75
    frames = total_frames % 75
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes:02d}:{secs:02d}:{frames:02d}"


def format_timestamp_mmss(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS for YouTube / human-readable text."""
    total_sec = int(seconds)
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class ExportService:
    @staticmethod
    def generate_cue_sheet(
        filename: str, title: str, performer: str, tracks: list[dict[str, Any]]
    ) -> str:
        """Generate standard CDRWIN / CUE sheet."""
        lines = [
            f'TITLE "{title}"',
            f'PERFORMER "{performer}"',
            f'FILE "{filename}" WAVE',
        ]

        for idx, track in enumerate(tracks, start=1):
            t_title = track.get("title") or f"Track {idx}"
            t_artist = track.get("artist") or performer
            start_sec = track.get("start_time", 0.0)
            bpm = track.get("bpm")
            key = track.get("camelot_key") or track.get("musical_key")

            lines.append(f"  TRACK {idx:02d} AUDIO")
            lines.append(f'    TITLE "{t_title}"')
            lines.append(f'    PERFORMER "{t_artist}"')
            if bpm:
                lines.append(f"    REM BPM {bpm:.1f}")
            if key:
                lines.append(f"    REM KEY {key}")
            lines.append(f"    INDEX 01 {format_cue_time(start_sec)}")

        return "\n".join(lines) + "\n"

    @staticmethod
    def generate_youtube_timestamps(tracks: list[dict[str, Any]]) -> str:
        """Generate YouTube video description timestamps."""
        lines = []
        for track in tracks:
            start_sec = track.get("start_time", 0.0)
            t_artist = track.get("artist", "Unknown Artist")
            t_title = track.get("title", "Untitled Track")
            bpm_str = f" [{track.get('bpm'):.0f} BPM]" if track.get("bpm") else ""
            key_str = (
                f" [{track.get('camelot_key')}]" if track.get("camelot_key") else ""
            )
            lines.append(
                f"{format_timestamp_mmss(start_sec)} {t_artist} - {t_title}{bpm_str}{key_str}"
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def generate_rekordbox_xml(
        mix_id: str,
        title: str,
        file_path: str,
        duration: float,
        bpm: float,
        tracks: list[dict[str, Any]],
        transitions: list[dict[str, Any]],
    ) -> str:
        """Generate Pioneer Rekordbox XML playlist format with cue markers."""
        root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")
        ET.SubElement(
            root,
            "PRODUCT",
            Name="SYCO23 Mix Analyst",
            Version="1.0.0",
            Company="SYSTEM CORRUPT",
        )

        collection = ET.SubElement(root, "COLLECTION", Entries="1")
        track_elem = ET.SubElement(
            collection,
            "TRACK",
            TrackID="1",
            Name=title,
            Artist="SYCO23",
            TotalTime=str(int(duration)),
            AverageBpm=f"{bpm:.2f}" if bpm else "128.00",
            Location=f"file://localhost{file_path}",
        )

        # Add cue markers for each detected track and transition point
        for idx, tr in enumerate(tracks, start=1):
            start_sec = tr.get("start_time", 0.0)
            ET.SubElement(
                track_elem,
                "POSITION_MARK",
                Name=f"Track {idx}: {tr.get('title', 'Track')}",
                Type="0",
                Start=f"{start_sec:.3f}",
                Num=str(idx),
            )

        for idx, trans in enumerate(transitions, start=len(tracks) + 1):
            t_start = trans.get("start_time", 0.0)
            ET.SubElement(
                track_elem,
                "POSITION_MARK",
                Name=f"Transition: {trans.get('transition_type', 'mix')} ({trans.get('from_key', '')}->{trans.get('to_key', '')})",
                Type="0",
                Start=f"{t_start:.3f}",
                Num=str(idx),
            )

        xml_str = ET.tostring(root, encoding="utf-8")
        parsed = minidom.parseString(xml_str)
        return parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")

    @staticmethod
    def generate_traktor_nml(
        title: str,
        file_path: str,
        duration: float,
        bpm: float,
        tracks: list[dict[str, Any]],
    ) -> str:
        """Generate Native Instruments Traktor NML collection file."""
        root = ET.Element("NML", VERSION="19")
        collection = ET.SubElement(root, "COLLECTION", ENTRIES="1")
        entry = ET.SubElement(
            collection, "ENTRY", TITLE=title, ARTIST="SYCO23", AUDIO_ID=title
        )
        ET.SubElement(entry, "INFO", PLAYTIME=str(int(duration)))
        ET.SubElement(entry, "TEMPO", BPM=f"{bpm:.2f}" if bpm else "128.00")

        for idx, tr in enumerate(tracks, start=1):
            start_ms = tr.get("start_time", 0.0) * 1000.0
            ET.SubElement(
                entry,
                "CUE_V2",
                NAME=f"{tr.get('artist', 'Artist')} - {tr.get('title', 'Track')}",
                DISPL_ORDER=str(idx),
                TYPE="0",
                START=f"{start_ms:.3f}",
                LEN="0.000",
                REPEATS="-1",
                HOTCUE=str(idx if idx <= 8 else -1),
            )

        xml_str = ET.tostring(root, encoding="utf-8")
        parsed = minidom.parseString(xml_str)
        return parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")
