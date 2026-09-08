from datetime import datetime

from pydantic import BaseModel


class TransitionEventOut(BaseModel):
    id: str
    mix_id: str
    transition_index: int
    start_time_seconds: float
    end_time_seconds: float
    cue_in_time: float
    cue_out_time: float
    transition_type: str
    energy_delta: float
    tempo_shift_bpm: float
    camelot_compatibility: str
    confidence: float
    created_at: datetime

    class Config:
        from_attributes = True


class TransitionListResponse(BaseModel):
    mix_id: str
    total_transitions: int
    transitions: list[TransitionEventOut]
