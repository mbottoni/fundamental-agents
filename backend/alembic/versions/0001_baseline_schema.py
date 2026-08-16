"""Baseline schema.

Captures the schema as it stands: users, analysis jobs, reports and watchlist
items, including the columns previously added by the hand-rolled
`_run_auto_migrations()` in `app/main.py` (`reports.chart_data`,
`users.is_verified`, `analysisjobs.error_message`).

Existing deployments were built by `Base.metadata.create_all()` and that
startup patcher, so this revision creates each table only if it is absent and
can be stamped instead of run:

    alembic stamp 0001    # database already has these tables
    alembic upgrade head  # fresh database

Revision ID: 0001
Revises:
Create Date: 2026-08-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(name)


def upgrade() -> None:
    if not _has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("hashed_password", sa.String(), nullable=False),
            sa.Column("stripe_customer_id", sa.String(), nullable=True),
            sa.Column("subscription_status", sa.String(), nullable=False, server_default="free"),
            sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email"),
            sa.UniqueConstraint("stripe_customer_id"),
        )
        op.create_index("ix_users_id", "users", ["id"])
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    if not _has_table("analysisjobs"):
        op.create_table(
            "analysisjobs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("ticker", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_analysisjobs_id", "analysisjobs", ["id"])
        op.create_index("ix_analysisjobs_user_id", "analysisjobs", ["user_id"])
        op.create_index("ix_analysisjobs_ticker", "analysisjobs", ["ticker"])

    if not _has_table("reports"):
        op.create_table(
            "reports",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("chart_data", sa.Text(), nullable=True),
            sa.Column("job_id", sa.Integer(), nullable=False),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.ForeignKeyConstraint(["job_id"], ["analysisjobs.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("job_id"),
        )
        op.create_index("ix_reports_id", "reports", ["id"])

    if not _has_table("watchlistitems"):
        op.create_table(
            "watchlistitems",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("ticker", sa.String(length=10), nullable=False),
            sa.Column("notes", sa.String(length=500), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "ticker", name="uq_user_ticker"),
        )
        op.create_index("ix_watchlistitems_id", "watchlistitems", ["id"])
        op.create_index("ix_watchlistitems_user_id", "watchlistitems", ["user_id"])


def downgrade() -> None:
    op.drop_table("watchlistitems")
    op.drop_table("reports")
    op.drop_table("analysisjobs")
    op.drop_table("users")
