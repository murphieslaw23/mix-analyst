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
    # Celery results are never read back (status lives in Postgres and the
    # Redis event stream); expire them so the result backend cannot fill Redis.
    result_expires=3600,
    # Named queues must match the `-Q` flags in worker/Dockerfile and
    # docker-compose.rpi.yml, otherwise dispatched tasks sit unconsumed
    # in the default `celery` queue forever.
    task_default_queue="analysis",
    task_queues=(
        Queue("analysis"),
        Queue("mastering"),
        Queue("stems"),
        Queue("exports"),
    ),
    task_routes={
        "tasks.run_analysis_pipeline": {"queue": "analysis"},
        "tasks.run_mastering_pipeline": {"queue": "mastering"},
        "tasks.run_stem_separation": {"queue": "stems"},
        "tasks.run_sidechain": {"queue": "mastering"},
        "tasks.run_broadcast_render": {"queue": "exports"},
    },
)
