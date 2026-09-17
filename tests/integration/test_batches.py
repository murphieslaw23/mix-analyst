"""Persistent batch slice: aggregate status, isolation, retry, unknown mix."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import api.app.api.v1.batches as batches_mod
from api.app import models as models  # noqa: PLC0414  (registers metadata)
from api.app.db.session import Base, get_db
from api.app.models.batch import Batch
from api.app.models.job import Job, JobStatus
from api.app.models.media import MediaAsset, Mix
from api.app.models.outbox import OutboxMessage
from api.app.services.batches import (
    create_batch,
    recompute_batch_status,
    retry_failed_items,
)
from tests.helpers.pipeline_seed import make_session


def _boom(*args: object, **kwargs: object) -> object:
    raise OSError("broker unreachable")


def _seed_asset_mix(
    db: Session, *, asset_id: str, mix_id: str, project_id: str = "default-project"
) -> None:
    db.add(
        MediaAsset(
            id=asset_id,
            project_id=project_id,
            original_filename="set.wav",
            storage_path=f"assets/audio/{asset_id}.wav",
            file_size_bytes=8,
            sha256_hash="0" * 64,
            duration_seconds=10.0,
            sample_rate=44100,
            channels=2,
            codec="pcm",
        )
    )
    db.add(
        Mix(
            id=mix_id,
            project_id=project_id,
            title="T",
            media_asset_id=asset_id,
            status="ready",
        )
    )


@pytest.fixture
def batch_env(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    factory = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = factory()
    _seed_asset_mix(db, asset_id="a1", mix_id="m1")
    _seed_asset_mix(db, asset_id="a2", mix_id="m2")
    db.commit()
    db.close()

    monkeypatch.setattr(batches_mod, "celery_client", SimpleNamespace(send_task=_boom))
    test_app = FastAPI()
    test_app.include_router(batches_mod.router, prefix="/api/v1")
    test_app.dependency_overrides[get_db] = lambda: factory()
    client = TestClient(test_app, raise_server_exceptions=False)
    yield SimpleNamespace(client=client, factory=factory)
    test_app.dependency_overrides.clear()


def test_batch_reports_partial_failure(batch_env: SimpleNamespace) -> None:
    res = batch_env.client.post("/api/v1/batches", json={"mix_ids": ["m1", "m2"]})
    assert res.status_code == 201, res.text
    batch_id: str = res.json()["id"]

    db = batch_env.factory()
    jobs: list[Job] = (
        db.query(Job).filter(Job.batch_id == batch_id).order_by(Job.mix_id).all()
    )
    assert len(jobs) == 2
    jobs[0].status = JobStatus.SUCCEEDED
    jobs[1].status = JobStatus.FAILED
    db.commit()
    db.close()

    got = batch_env.client.get(f"/api/v1/batches/{batch_id}")
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["status"] == "PARTIAL_FAILED"
    assert body["total_count"] == 2
    assert body["completed_count"] == 1
    assert body["failed_count"] == 1
    assert body["queued_count"] == 0
    assert len(body["items"]) == 2


def test_cross_project_batch_is_not_visible(batch_env: SimpleNamespace) -> None:
    db = batch_env.factory()
    _seed_asset_mix(db, asset_id="ab", mix_id="mb", project_id="project-b")
    db.commit()
    other = create_batch(db, project_id="project-b", mix_ids=["mb"], sender=None)
    other_id: str = other.id
    db.close()

    res = batch_env.client.get(f"/api/v1/batches/{other_id}")
    assert res.status_code == 404


def test_retry_failed_items_preserves_successes(tmp_path) -> None:
    db = make_session(tmp_path)
    _seed_asset_mix(db, asset_id="a1", mix_id="m1")
    _seed_asset_mix(db, asset_id="a2", mix_id="m2")
    db.commit()

    batch: Batch = create_batch(
        db, project_id="default-project", mix_ids=["m1", "m2"], sender=None
    )
    jobs: list[Job] = (
        db.query(Job).filter(Job.batch_id == batch.id).order_by(Job.mix_id).all()
    )
    ok_job, bad_job = jobs[0], jobs[1]
    ok_job.status = JobStatus.SUCCEEDED
    bad_job.status = JobStatus.FAILED
    db.commit()
    recompute_batch_status(db, batch)
    assert db.get(Batch, batch.id) is not None

    before_bad = (
        db.query(OutboxMessage).filter(OutboxMessage.aggregate_id == bad_job.id).count()
    )
    before_ok = (
        db.query(OutboxMessage).filter(OutboxMessage.aggregate_id == ok_job.id).count()
    )

    retried = retry_failed_items(db, batch, sender=None)

    assert retried == 1
    db.refresh(ok_job)
    db.refresh(bad_job)
    assert ok_job.status == JobStatus.SUCCEEDED
    assert bad_job.status == JobStatus.QUEUED
    after_bad = (
        db.query(OutboxMessage).filter(OutboxMessage.aggregate_id == bad_job.id).count()
    )
    after_ok = (
        db.query(OutboxMessage).filter(OutboxMessage.aggregate_id == ok_job.id).count()
    )
    assert after_bad == before_bad + 1
    assert after_ok == before_ok
    db.refresh(batch)
    assert batch.total_count == 2
    db.close()


def test_post_batch_unknown_mix_is_404(batch_env: SimpleNamespace) -> None:
    res = batch_env.client.post("/api/v1/batches", json={"mix_ids": ["does-not-exist"]})
    assert res.status_code == 404, res.text
