"""Preserve broad raw catalog observations and resumable discovery progress."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "b021_us_catalog_inventory"
down_revision = "b016_review_revisions"
branch_labels = None
depends_on = None


def upgrade():
    document = sa.JSON().with_variant(JSONB, "postgresql")
    op.create_table(
        "catalog_observations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("mode", sa.String(), nullable=False, index=True),
        sa.Column("venue", sa.String(), nullable=False, index=True),
        sa.Column("external_id", sa.String(), nullable=False, index=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", document, nullable=False),
    )
    op.create_table(
        "catalog_inventory",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("venue", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column(
            "observation_id", sa.String(), sa.ForeignKey("catalog_observations.id"), nullable=False
        ),
        sa.Column("market_id", sa.String(), nullable=True),
        sa.Column("supported", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inventory_fresh", "catalog_inventory", ["mode", "venue", "observed_at"])
    op.create_table(
        "discovery_progress",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("venue", sa.String(), nullable=False),
        sa.Column("payload", document, nullable=False),
    )


def downgrade():
    op.drop_table("discovery_progress")
    op.drop_table("catalog_inventory")
    op.drop_table("catalog_observations")
