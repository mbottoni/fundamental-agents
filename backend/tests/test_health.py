"""
/healthz is read by the deploy gate, the container health check and the uptime
check. "ok" has to mean the site can do its job, and anything less has to say
what is wrong.
"""

import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.db import get_db
from app.db import migrate
from app.main import app
from app.models.worker_heartbeat import WorkerHeartbeat
from app.services import health


def test_root(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Stock Analyzer AI"


@pytest.fixture
def migrated(tmp_path):
    """
    A client whose database was built by the migrations, as a deployed one is.
    (The shared fixtures use create_all(), which leaves no alembic_version.)
    """
    engine = create_engine(
        f"sqlite:///{tmp_path / 'health.db'}", connect_args={"check_same_thread": False}
    )
    migrate.upgrade_to_head(engine)
    Session = sessionmaker(bind=engine)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    previous = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = override
    app.state.inline_worker_thread = None
    try:
        yield TestClient(app), Session
    finally:
        app.dependency_overrides[get_db] = previous
        engine.dispose()


@pytest.fixture
def standalone_worker(monkeypatch):
    """Production's arrangement: the worker is a separate process."""
    monkeypatch.setattr(settings, "ANALYSIS_WORKER_INLINE", False)


def test_a_migrated_database_with_an_inline_worker_is_ok(migrated):
    client, _ = migrated
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "database": True,
        "migrations": "current",
        "worker": "inline",
        "version": settings.APP_VERSION,
    }


def test_the_version_is_the_one_the_image_was_built_with(migrated, monkeypatch):
    client, _ = migrated
    monkeypatch.setattr(settings, "APP_VERSION", "0bf3680")
    assert client.get("/healthz").json()["version"] == "0bf3680"


def test_an_unmigrated_database_is_degraded(client: TestClient):
    """The shared fixture's database has tables but was never migrated."""
    resp = client.get("/healthz")
    body = resp.json()
    # 200 either way, so the body can say what is wrong.
    assert resp.status_code == 200
    assert body["status"] == "degraded"
    assert body["database"] is True
    assert body["migrations"] == "behind"


def test_a_database_newer_than_the_code_is_ok(migrated):
    """A rollback: the health gate must pass, or nothing can be rolled back."""
    from sqlalchemy import text

    client, Session = migrated
    with Session() as db:
        db.execute(text("UPDATE alembic_version SET version_num = '9999'"))
        db.commit()
    body = client.get("/healthz").json()
    assert body["migrations"] == "ahead"
    assert body["status"] == "ok"


def test_an_unreachable_database_is_degraded_not_an_error(migrated):
    client, _ = migrated

    class DeadSession:
        def execute(self, *args, **kwargs):
            raise ConnectionError("could not connect to server")

        def rollback(self):
            pass

    app.dependency_overrides[get_db] = lambda: DeadSession()
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["database"] is False


class TestStandaloneWorker:
    def test_no_worker_has_ever_reported(self, migrated, standalone_worker):
        """Nothing would run a queued analysis: that is not healthy."""
        client, _ = migrated
        body = client.get("/healthz").json()
        assert body["worker"] == "missing"
        assert body["status"] == "degraded"

    def test_a_worker_seen_recently_is_ok(self, migrated, standalone_worker):
        client, Session = migrated
        with Session() as db:
            health.record_heartbeat(db, "worker-a")
        body = client.get("/healthz").json()
        assert body["worker"] == "ok"
        assert body["status"] == "ok"

    def test_a_worker_that_stopped_reporting_is_stale(self, migrated, standalone_worker):
        client, Session = migrated
        long_ago = datetime.now(timezone.utc) - timedelta(
            seconds=settings.WORKER_HEARTBEAT_STALE_SECONDS + 5
        )
        with Session() as db:
            db.add(WorkerHeartbeat(worker_id="worker-a", last_seen_at=long_ago))
            db.commit()
        body = client.get("/healthz").json()
        assert body["worker"] == "stale"
        assert body["status"] == "degraded"

    def test_one_live_worker_is_enough(self, migrated, standalone_worker):
        """A dead worker's old row must not mask a live one, or the reverse."""
        client, Session = migrated
        long_ago = datetime.now(timezone.utc) - timedelta(hours=2)
        with Session() as db:
            db.add(WorkerHeartbeat(worker_id="replaced", last_seen_at=long_ago))
            db.commit()
            health.record_heartbeat(db, "current")
        assert client.get("/healthz").json()["worker"] == "ok"


def test_a_dead_inline_worker_thread_is_reported(migrated):
    client, _ = migrated
    finished = threading.Thread(target=lambda: None)
    finished.start()
    finished.join()
    app.state.inline_worker_thread = finished
    try:
        body = client.get("/healthz").json()
    finally:
        app.state.inline_worker_thread = None
    assert body["worker"] == "stopped"
    assert body["status"] == "degraded"


def test_heartbeats_are_refreshed_in_place_and_old_workers_forgotten(migrated):
    _, Session = migrated
    with Session() as db:
        db.add(
            WorkerHeartbeat(
                worker_id="gone",
                last_seen_at=datetime.now(timezone.utc) - timedelta(days=2),
            )
        )
        db.commit()
        health.record_heartbeat(db, "worker-a")
        health.record_heartbeat(db, "worker-a")
        assert [row.worker_id for row in db.query(WorkerHeartbeat).all()] == ["worker-a"]
        assert health.newest_heartbeat_age(db) < 5


def test_the_worker_beats_and_survives_a_failed_beat(migrated, monkeypatch):
    from app import worker as worker_module

    _, Session = migrated
    monkeypatch.setattr(worker_module, "SessionLocal", Session)
    worker = worker_module.Worker()

    worker.beat()
    with Session() as db:
        assert db.get(WorkerHeartbeat, worker.worker_id) is not None

    def broken(*args, **kwargs):
        raise RuntimeError("database went away")

    monkeypatch.setattr(health, "record_heartbeat", broken)
    worker.beat()  # must not raise: a missed beat cannot be allowed to stop work
