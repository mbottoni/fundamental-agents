"""Worker heartbeats.

One row per analysis worker, refreshed while it runs, so /healthz can tell an
idle queue from a queue with no worker.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workerheartbeats",
        sa.Column("worker_id", sa.String(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("worker_id"),
    )


def downgrade() -> None:
    op.drop_table("workerheartbeats")
