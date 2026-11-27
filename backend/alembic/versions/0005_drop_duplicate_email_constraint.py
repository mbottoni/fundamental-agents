"""Drop the duplicate unique constraint on users.email.

The baseline declared both `UniqueConstraint("email")` and the unique index
`ix_users_email`. The model declares only the index, so a database built by the
migrations carried one more constraint than a database built from the models,
and `alembic check` reported drift. Uniqueness is unaffected: the index stays.

Databases created by `create_all()` never had the constraint, hence IF EXISTS.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-27
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite cannot drop a constraint without rebuilding the table, and only
    # the test suite uses it; the redundant constraint is harmless there.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key")


def downgrade() -> None:
    # Nothing to restore: the unique index enforces the same rule.
    pass
