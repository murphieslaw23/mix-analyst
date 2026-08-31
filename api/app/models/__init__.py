from ..db.session import Base
from .media import MediaAsset, UploadSession, UploadStatus, Mix
from .job import Job, JobAttempt, StageRun, JobType, JobStatus, StageStatus
from .analysis import AnalysisResult

Mix.analysis_result = relationship("AnalysisResult", back_populates="mix", uselist=False, cascade="all, delete-orphan")

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
]
