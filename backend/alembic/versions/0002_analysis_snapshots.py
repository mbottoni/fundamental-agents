"""Analysis snapshots.

Records the recommendation, score and price at the moment of each analysis, so
history and past-call performance can be shown. Neither is reconstructable
after the fact, which is why the table exists rather than deriving it from
stored reports.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("analysissnapshots"):
        return

    op.create_table(
        "analysissnapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("recommendation", sa.String(), nullable=True),
        sa.Column("composite_score", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("dcf_value", sa.Float(), nullable=True),
        sa.Column("risk_rating", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["analysisjobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index("ix_analysissnapshots_id", "analysissnapshots", ["id"])
    op.create_index("ix_analysissnapshots_user_id", "analysissnapshots", ["user_id"])
    op.create_index("ix_analysissnapshots_ticker", "analysissnapshots", ["ticker"])


def downgrade() -> None:
    op.drop_table("analysissnapshots")
