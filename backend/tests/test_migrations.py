"""
The Alembic baseline must describe the same schema the models do.

`versions/` was empty and the schema was maintained by `create_all()` plus a
hand-rolled patcher in `main.py`, so a database built by migrations could
silently differ from one built by the app.
"""

import os
import pathlib

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db.base_class import Base

BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Differences Alembic reports that are not real drift: SQLite renders server
# defaults and types differently from the DDL that produced them.
IGNORED_DIFF_KINDS = {"modify_default", "modify_type", "modify_nullable"}


@pytest.fixture
def migrated_engine(tmp_path):
    """A database built by running the migrations."""
    db_path = tmp_path / "migrated.db"
    url = f"sqlite:///{db_path}"

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")

    engine = create_engine(url)
    yield engine
    engine.dispose()


def test_every_model_table_is_created(migrated_engine):
    tables = set(inspect(migrated_engine).get_table_names())
    for table in Base.metadata.tables:
        assert table in tables, f"{table} is missing from the migrations"


def test_migrations_match_the_models(migrated_engine):
    """Autogenerate should find nothing left to do."""
    import app.db.base  # noqa: F401 - registers every model on Base.metadata

    with migrated_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        diffs = compare_metadata(context, Base.metadata)

    meaningful = [d for d in diffs if not (isinstance(d, tuple) and d[0] in IGNORED_DIFF_KINDS)]
    assert not meaningful, f"schema drift between models and migrations: {meaningful}"


def test_columns_added_by_the_startup_patcher_are_present(migrated_engine):
    """
    These three were only ever created by `_run_auto_migrations()`, so a
    migration-built database used to be missing them.
    """
    inspector = inspect(migrated_engine)
    assert "chart_data" in {c["name"] for c in inspector.get_columns("reports")}
    assert "is_verified" in {c["name"] for c in inspector.get_columns("users")}
    assert "error_message" in {c["name"] for c in inspector.get_columns("analysisjobs")}


# Every table that existed when start-up still called create_all(). Tables
# added since then can only ever be created by their own revision.
PRE_ALEMBIC_TABLES = (
    "users", "analysisjobs", "reports", "watchlistitems", "analysissnapshots", "alerts",
)


def test_a_database_built_before_alembic_can_be_adopted(tmp_path):
    """
    The first databases were built by create_all() and have no version table.
    `upgrade head` must adopt one as it stands: revisions 0001 to 0004 skip
    what is already there, and later ones add what is not.
    """
    import app.db.base  # noqa: F401
    from app.db import migrate

    engine = create_engine(f"sqlite:///{tmp_path / 'existing.db'}")
    Base.metadata.create_all(
        bind=engine, tables=[Base.metadata.tables[name] for name in PRE_ALEMBIC_TABLES]
    )
    try:
        assert migrate.schema_state(engine) == "behind"
        assert migrate.upgrade_to_head(engine) == "current"  # must not raise
        assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


# ── The app runs the migrations itself (app/db/migrate.py) ────────────────


@pytest.fixture
def empty_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'app.db'}")
    yield engine
    engine.dispose()


def _set_revision(engine, revision: str) -> None:
    from sqlalchemy import text

    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = :r"), {"r": revision})


def test_an_empty_database_is_behind_and_upgrading_makes_it_current(empty_engine):
    from app.db import migrate

    assert migrate.schema_state(empty_engine) == "behind"
    assert migrate.upgrade_to_head(empty_engine) == "current"
    assert migrate.current_revision(empty_engine) == migrate.head_revision()
    # And again: a restart must be a no-op, not an error.
    assert migrate.upgrade_to_head(empty_engine) == "current"


def test_a_database_on_an_older_revision_is_behind(empty_engine):
    from app.db import migrate

    migrate.upgrade_to_head(empty_engine)
    _set_revision(empty_engine, "0003")
    assert migrate.schema_state(empty_engine) == "behind"


def test_a_database_newer_than_the_code_is_left_alone(empty_engine):
    """
    A rollback runs an older image against a schema it has never heard of.
    Alembic cannot upgrade from a revision it cannot find; refusing to start
    would turn every rollback into an outage.
    """
    from app.db import migrate

    migrate.upgrade_to_head(empty_engine)
    _set_revision(empty_engine, "9999_from_the_future")

    assert migrate.schema_state(empty_engine) == "ahead"
    assert migrate.upgrade_to_head(empty_engine) == "ahead"  # must not raise
    assert migrate.current_revision(empty_engine) == "9999_from_the_future"


def test_running_migrations_leaves_the_apps_logging_alone(empty_engine):
    """
    alembic.ini configures logging for the command line. Applied inside the
    running app it disables every logger that already exists, after which the
    app logs nothing at all.
    """
    import logging

    from app.db import migrate

    app_logger = logging.getLogger("stock_analyzer")
    handlers_before = list(logging.getLogger().handlers)
    level_before = logging.getLogger().level

    migrate.upgrade_to_head(empty_engine)

    assert app_logger.disabled is False
    assert logging.getLogger().handlers == handlers_before
    assert logging.getLogger().level == level_before


def test_a_percent_sign_in_the_database_url_survives(tmp_path):
    """ConfigParser reads % as interpolation; generated passwords contain them."""
    from app.db import migrate

    directory = tmp_path / "100%"
    directory.mkdir()
    engine = create_engine(f"sqlite:///{directory / 'app.db'}")
    try:
        assert migrate.upgrade_to_head(engine) == "current"
    finally:
        engine.dispose()


def test_startup_migrates_the_database_and_nothing_else_creates_tables(tmp_path, monkeypatch):
    """
    The API process is what migrates a deployment. If start-up ever goes back
    to `create_all()`, the tables appear but `alembic_version` does not.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    import app.core.db as core_db
    import app.main as main
    from app.core.config import settings
    from app.db import migrate

    engine = create_engine(f"sqlite:///{tmp_path / 'startup.db'}")
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(core_db, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(settings, "ANALYSIS_WORKER_INLINE", False)
    monkeypatch.setattr(settings, "ALERT_SWEEP_MINUTES", 0)

    with TestClient(main.app):
        assert migrate.schema_state(engine) == "current"
        assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())


def test_the_worker_waits_for_the_schema_and_gives_up_with_a_reason(empty_engine, monkeypatch):
    import app.core.db as core_db
    from app import worker
    from app.db import migrate

    monkeypatch.setattr(core_db, "engine", empty_engine)

    with pytest.raises(SystemExit) as stopped:
        worker.wait_for_schema(timeout_seconds=0.3, poll_seconds=0.05)
    assert "migrations" in str(stopped.value)

    migrate.upgrade_to_head(empty_engine)
    worker.wait_for_schema(timeout_seconds=0.3, poll_seconds=0.05)  # returns at once


# ── The real check: PostgreSQL, with nothing ignored ──────────────────────

POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")


@pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not set")
def test_migrations_reproduce_the_models_exactly_on_postgres():
    """
    `alembic check`, in effect. SQLite hides differences in types, defaults
    and constraints, which is why the comparison above ignores three kinds of
    diff; production runs PostgreSQL, where nothing may be ignored.
    """
    from sqlalchemy import text
    from sqlalchemy.engine import make_url

    import app.db.base  # noqa: F401
    from app.db import migrate

    scratch = "migration_check"
    admin = create_engine(POSTGRES_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {scratch}"))
        connection.execute(text(f"CREATE DATABASE {scratch}"))

    engine = create_engine(make_url(POSTGRES_URL).set(database=scratch))
    try:
        assert migrate.upgrade_to_head(engine) == "current"
        with engine.connect() as connection:
            diffs = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert not diffs, f"schema drift between models and migrations: {diffs}"
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS {scratch}"))
        admin.dispose()
