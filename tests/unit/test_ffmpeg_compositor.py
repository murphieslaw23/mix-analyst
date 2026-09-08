from worker.broadcast.ffmpeg_compositor import FFmpegBroadcastCompositor


def test_build_filter_complex():
    """Verify filtergraph contains audio-reactive spectrum, totem branding, and key display."""
    graph = FFmpegBroadcastCompositor.build_filter_complex(
        title="Acid Tribal Ritual",
        artist="Curley Korrupt",
        bpm=154.0,
        camelot_key="10A",
    )

    assert "showfreqs" in graph
    assert "showwaves" in graph
    assert "Curley Korrupt" in graph
    assert "10A" in graph
    assert "154.0 BPM" in graph


def test_build_ffmpeg_command():
    """Verify FFmpeg arguments for MP4 export and RTMP streaming."""
    cmd_mp4 = FFmpegBroadcastCompositor.build_ffmpeg_command(
        input_audio="/storage/audio/mix1.wav",
        output_dest="/storage/broadcast/mix1.mp4",
        is_rtmp=False,
    )
    assert "-c:v" in cmd_mp4
    assert "libx264" in cmd_mp4
    assert cmd_mp4[-1] == "/storage/broadcast/mix1.mp4"

    cmd_rtmp = FFmpegBroadcastCompositor.build_ffmpeg_command(
        input_audio="/storage/audio/mix1.wav",
        output_dest="rtmp://a.rtmp.youtube.com/live2/key123",
        is_rtmp=True,
    )
    assert "-f" in cmd_rtmp
    assert "flv" in cmd_rtmp
