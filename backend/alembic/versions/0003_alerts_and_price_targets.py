"""Alerts and watchlist price targets.

Gives the watchlist something to do between visits: a price target per item,
and a table of alerts raised when a target is met or the model changes its
mind about a holding.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    watchlist_columns = {c["name"] for c in inspector.get_columns("watchlistitems")}
    if "target_price" not in watchlist_columns:
        op.add_column("watchlistitems", sa.Column("target_price", sa.Float(), nullable=True))
    if "target_direction" not in watchlist_columns:
        op.add_column(
            "watchlistitems", sa.Column("target_direction", sa.String(length=5), nullable=True)
        )

    if not inspector.has_table("alerts"):
        op.create_table(
            "alerts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("ticker", sa.String(), nullable=False),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("triggered_value", sa.Float(), nullable=True),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_alerts_id", "alerts", ["id"])
        op.create_index("ix_alerts_user_id", "alerts", ["user_id"])
        op.create_index("ix_alerts_ticker", "alerts", ["ticker"])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_column("watchlistitems", "target_direction")
    op.drop_column("watchlistitems", "target_price")
