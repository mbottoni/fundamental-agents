"""
Schema migrations, run from code.

Alembic is the only thing that changes the schema. The API process upgrades
the database to the newest revision when it starts, so a deploy migrates
itself; everything else (the worker, the health check) only asks whether the
database is current.

`Base.metadata.create_all()` is deliberately not used outside the test suite:
it never alters an existing table, so it hid broken migrations instead of
failing on them.
"""

import pathlib
from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Engine

BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[2]


def alembic_config(url: Optional[str] = None) -> Config:
    """
    The project's Alembic configuration, located by path rather than by the
    working directory, so it works from wherever the process was started.
    """
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    if url is not None:
        # ConfigParser treats % as interpolation; a password may contain one.
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    # alembic.ini configures logging for the command line. Applied inside a
    # running app it would replace the app's own handlers and levels.
    config.attributes["configure_logger"] = False
    return config


def _known_revisions() -> set[str]:
    return {script.revision for script in ScriptDirectory.from_config(alembic_config()).walk_revisions()}


def head_revision() -> Optional[str]:
    """The newest revision the code knows about."""
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def current_revision(engine: Engine) -> Optional[str]:
    """The revision the database is at, or None if it has never been migrated."""
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def schema_state(engine: Engine) -> str:
    """
    Where the database stands relative to this code:

    - ``current``: at the revision the code was written for.
    - ``behind``: older, or never migrated. The code must not run against it.
    - ``ahead``: at a revision this code has never heard of, which is what a
      rollback looks like (an older image on a newer schema). Migrations only
      run forward, so the code carries on; whether that is safe depends on what
      the newer revisions changed.
    """
    current = current_revision(engine)
    if current == head_revision():
        return "current"
    if current is not None and current not in _known_revisions():
        return "ahead"
    return "behind"


def upgrade_to_head(engine: Engine) -> str:
    """
    Apply every outstanding revision and return the resulting schema state.

    Safe to call on an up-to-date database. A database that is *ahead* of the
    code is left alone: Alembic cannot upgrade from a revision it cannot find,
    and refusing to start would make every rollback an outage.
    """
    if schema_state(engine) == "ahead":
        return "ahead"
    command.upgrade(alembic_config(engine.url.render_as_string(hide_password=False)), "head")
    return schema_state(engine)
