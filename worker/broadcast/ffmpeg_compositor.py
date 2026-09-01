import subprocess
from typing import Dict, Any, List, Optional

class FFmpegBroadcastCompositor:
    """Renders 16:9 1080p live streams with audio-reactive spectrums and totem branding."""

    @staticmethod
    def build_filter_complex(
        title: str = "SYSTEM CORRUPT LIVE",
        artist: str = "Underground Tekno",
        bpm: float = 150.0,
        camelot_key: str = "8A",
        width: int = 1920,
        height: int = 1080,
        fps: int = 30
    ) -> str:
        """Construct multi-layer FFmpeg filter graph for live video rendering."""
        filters = [
            f"color=c=#0d0e12:s={width}x{height}:r={fps}[bg]",
            "[0:a]showfreqs=s=1280x280:mode=bar:ascale=log:fscale=log:colors=#ea580c|#f59e0b|#0f766e[spectrum]",
            "[0:a]showwaves=s=480x140:mode=cline:colors=#ea580c[waves]",
            "[bg][spectrum]overlay=(W-w)/2:H-360[v1]",
            "[v1][waves]overlay=(W-w)/2:140[v2]",
            f"[v2]drawtext=text='SYSTEM CORRUPT | 24/7 SOUND-SYSTEM LIVE':fontcolor=#ea580c:fontsize=32:x=(w-text_w)/2:y=60,"
            f"drawtext=text='{artist} - {title}':fontcolor=#ffffff:fontsize=26:x=(w-text_w)/2:y=H-90,"
            f"drawtext=text='KEY\\: {camelot_key} | {bpm:.1f} BPM':fontcolor=#5eead4:fontsize=20:x=(w-text_w)/2:y=H-50[vout]"
        ]
        return ";".join(filters)

    @staticmethod
    def build_ffmpeg_command(
        input_audio: str,
        output_dest: str,
        title: str = "Live Set",
        artist: str = "SYCO23",
        bpm: float = 150.0,
        camelot_key: str = "8A",
        is_rtmp: bool = False
    ) -> List[str]:
        """Generate CLI arguments for standalone execution or live RTMP piping."""
        filter_str = FFmpegBroadcastCompositor.build_filter_complex(
            title=title,
            artist=artist,
            bpm=bpm,
            camelot_key=camelot_key
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_audio,
            "-filter_complex", filter_str,
            "-map", "[vout]",
            "-map", "0:a",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-b:v", "4500k",
            "-maxrate", "5000k",
            "-bufsize", "10000k",
            "-pix_fmt", "yuv420p",
            "-g", "60",
            "-c:a", "aac",
            "-b:a", "320k",
            "-ar", "48000"
        ]

        if is_rtmp:
            cmd.extend(["-f", "flv", output_dest])
        else:
            cmd.extend(["-f", "mp4", output_dest])

        return cmd
