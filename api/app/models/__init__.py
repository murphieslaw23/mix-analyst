from ..db.session import Base
from .media import MediaAsset, UploadSession, UploadStatus, Mix
from .job import Job, JobAttempt, StageRun, JobType, JobStatus, StageStatus
from .analysis import AnalysisResult
from .tracklist import TrackSegment, TrackMatch
from .transition import TransitionEvent
from sqlalchemy.orm import relationship

Mix.analysis_result = relationship("AnalysisResult", back_populates="mix", uselist=False, cascade="all, delete-orphan")
Mix.track_segments = relationship("TrackSegment", back_populates="mix", order_by="TrackSegment.segment_index", cascade="all, delete-orphan")
Mix.transitions = relationship("TransitionEvent", back_populates="mix", order_by="TransitionEvent.transition_index", cascade="all, delete-orphan")

__all__ = [
    "Base",
    "MediaAsset",
    "UploadSession",
    "UploadStatus",
    "Mix",
    "Job",
    "JobAttempt",
    "StageRun",
    "JobType",
    "JobStatus",
    "StageStatus",
    "AnalysisResult",
    "TrackSegment",
    "TrackMatch",
    "TransitionEvent",
]
