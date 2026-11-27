"""Queue bookkeeping on analysis jobs.

The job table doubles as the work queue now that analyses run in a worker
rather than as an in-process background task. A worker claims a row, holds a
lease on it by refreshing `locked_at`, and releases it when done; a lease that
stops being refreshed expires and the job is picked up again instead of being
abandoned by a deploy.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {c["name"] for c in inspector.get_columns("analysisjobs")}

    if "attempts" not in columns:
        op.add_column(
            "analysisjobs",
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        )
    if "locked_at" not in columns:
        op.add_column(
            "analysisjobs", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True)
        )
    if "locked_by" not in columns:
        op.add_column("analysisjobs", sa.Column("locked_by", sa.String(), nullable=True))

    # Claiming filters on the lease, and the queue is polled continuously.
    indexes = {i["name"] for i in inspector.get_indexes("analysisjobs")}
    if "ix_analysisjobs_locked_at" not in indexes:
        op.create_index("ix_analysisjobs_locked_at", "analysisjobs", ["locked_at"])


def downgrade() -> None:
    op.drop_index("ix_analysisjobs_locked_at", table_name="analysisjobs")
    op.drop_column("analysisjobs", "locked_by")
    op.drop_column("analysisjobs", "locked_at")
    op.drop_column("analysisjobs", "attempts")
