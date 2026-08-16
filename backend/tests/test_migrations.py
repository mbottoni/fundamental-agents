"""
The Alembic baseline must describe the same schema the models do.

`versions/` was empty and the schema was maintained by `create_all()` plus a
hand-rolled patcher in `main.py`, so a database built by migrations could
silently differ from one built by the app.
"""

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


def test_upgrade_is_idempotent_against_an_existing_schema(tmp_path):
    """
    Deployed databases were built by create_all(); running the baseline against
    them must not fail, so the release can stamp or upgrade either way.
    """
    import app.db.base  # noqa: F401

    db_path = tmp_path / "existing.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)
    engine.dispose()

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")  # must not raise
