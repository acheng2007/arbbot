"""Persist bounded discovery reports independently of quote ingestion."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b005_discovery_catalogs"
down_revision = "b020_catalog_projection"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "discovery_catalogs",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("venue", sa.String(), nullable=False),
        sa.Column(
            "payload", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
    )
    op.create_index("ix_discovery_catalogs_mode", "discovery_catalogs", ["mode"])


def downgrade():
    op.drop_index("ix_discovery_catalogs_mode", table_name="discovery_catalogs")
    op.drop_table("discovery_catalogs")
