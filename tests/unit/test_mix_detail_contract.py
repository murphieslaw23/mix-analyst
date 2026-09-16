"""Contract tests for the PWA mix payloads (frontend/backend shape agreement)."""

from datetime import datetime, timezone

from api.app.schemas.mix import MixDetailOut


def _detail_payload(**overrides):
    base = {
        "id": "mix-1",
        "title": "Live Set",
        "artist": "SYCO23",
        "status": "ready",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "original_filename": "set.wav",
        "duration_seconds": 1800.0,
        "bpm": 152.0,
        "camelot_key": "9A",
        "audio_url": "/api/v1/mixes/mix-1/audio",
        "tracks": [
            {
                "id": "tr-1",
                "title": "Intro",
                "artist": "SYCO23",
                "start_time": 0.0,
                "end_time": 225.0,
                "bpm": 152.0,
                "camelot_key": "9A",
            }
        ],
        "transitions": [
            {
                "id": "t-1",
                "start_time": 200.0,
                "end_time": 250.0,
                "transition_type": "BASS_SWAP",
                "from_key": None,
                "to_key": None,
                "harmonic_compatibility": "PERFECT_MATCH",
            }
        ],
    }
    base.update(overrides)
    return base


def test_mix_detail_out_carries_everything_the_pwa_needs():
    """The detail payload must include audio URL, cues and transitions."""
    detail = MixDetailOut(**_detail_payload())

    assert detail.audio_url == "/api/v1/mixes/mix-1/audio"
    assert detail.original_filename == "set.wav"
    assert detail.duration_seconds == 1800.0
    assert detail.bpm == 152.0
    assert len(detail.tracks) == 1
    assert detail.tracks[0].start_time == 0.0
    assert len(detail.transitions) == 1
    assert detail.transitions[0].harmonic_compatibility == "PERFECT_MATCH"


def test_mix_detail_out_tolerates_missing_analysis():
    """Mixes without analysis results must still validate (nullable fields)."""
    detail = MixDetailOut(
        **_detail_payload(bpm=None, camelot_key=None, tracks=[], transitions=[])
    )

    assert detail.bpm is None
    assert detail.tracks == []
    assert detail.transitions == []
