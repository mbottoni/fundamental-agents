"""
Alembic environment configuration.
Reads DATABASE_URL from the app's settings and uses the app's Base metadata
for auto-generating migrations.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

# Add the backend directory to sys.path so we can import the app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402  (imports all models)

config = context.config

# Use the app's DATABASE_URL unless the caller supplied a real one. Overriding
# unconditionally meant migrations always ran against the environment's
# database, whatever target was requested — including in tests.
PLACEHOLDER_URL = "driver://user:pass@localhost/dbname"
# Arbitrary, fixed: the key every process agrees on for "a migration is running".
MIGRATION_LOCK_KEY = 7_203_118_045
configured_url = config.get_main_option("sqlalchemy.url", None)
if not configured_url or configured_url == PLACEHOLDER_URL:
    # ConfigParser treats % as interpolation; a password may contain one.
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

# alembic.ini sets up logging for the command line. When the app runs the
# migrations itself (app/db/migrate.py) that would replace the app's handlers
# and silence its loggers, so the app opts out.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to DB)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            # Two processes starting together must not both run the same
            # revision. The lock is released when the transaction ends.
            if connection.dialect.name == "postgresql":
                connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
