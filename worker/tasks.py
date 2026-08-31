from .celery_app import celery_app


@celery_app.task(bind=True, name="tasks.placeholder")
def placeholder_task(self):
    """Placeholder task for Phase 0."""
    return {"status": "ok", "message": "Worker is running"}
