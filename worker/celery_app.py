import os

from celery import Celery
from kombu import Queue

celery_app = Celery(
    "mix_analyst_worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
    include=["worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_queues=(
        Queue("analysis-cpu"),
        Queue("dsp-heavy"),
        Queue("metadata-network"),
        Queue("exports"),
    ),
    task_default_queue="analysis-cpu",
    task_routes={
        "tasks.run_analysis_pipeline": {"queue": "analysis-cpu"},
        "tasks.run_master_mix": {"queue": "dsp-heavy"},
        "tasks.cleanup_expired_uploads": {"queue": "metadata-network"},
    },
    task_publish_retry=True,
    task_publish_retry_policy={
        "max_retries": 3,
        "interval_start": 0,
        "interval_step": 0.2,
        "interval_max": 1,
    },
    beat_schedule={
        "cleanup-expired-uploads": {
            "task": "tasks.cleanup_expired_uploads",
            "schedule": 15 * 60,
        }
    },
)
