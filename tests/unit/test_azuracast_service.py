"""Unit tests for AzuraCast broadcast service."""

from api.app.services.azuracast_service import AzuraCastService


def test_format_azuracast_cue_points():
    """Verify cue markers transformation."""
    tracks = [
        {
            "title": "Track One",
            "artist": "Kaotek",
            "start_time": 0.0,
            "bpm": 128.0,
            "camelot_key": "8A",
        },
        {
            "title": "Track Two",
            "artist": "Suburbass",
            "start_time": 180.5,
            "bpm": 130.0,
            "camelot_key": "9A",
        },
    ]
    markers = AzuraCastService.format_azuracast_cue_points(tracks)
    assert len(markers) == 2
    assert markers[0]["title"] == "Track One"
    assert markers[1]["start_seconds"] == 180.5


def test_match_live_track():
    """Verify playhead position matches the active track."""
    tracks = [
        {"title": "Intro Track", "artist": "Artist A", "start_time": 0.0},
        {"title": "Main Track", "artist": "Artist B", "start_time": 120.0},
        {"title": "Outro Track", "artist": "Artist C", "start_time": 300.0},
    ]
    matched = AzuraCastService.match_live_track(150.0, tracks)
    assert matched["title"] == "Main Track"
    assert matched["artist"] == "Artist B"
