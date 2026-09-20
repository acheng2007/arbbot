"""Add conservative catalog projections and family pagination index."""

import sqlalchemy as sa
from alembic import op

revision = "b020_catalog_projection"
down_revision = "a2a3099f82df"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("markets", sa.Column("family", sa.String(100), nullable=True))
    op.add_column(
        "matches",
        sa.Column("evidence_complete", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_market_family_page", "markets", ["mode", "family", "id"])


def downgrade():
    op.drop_index("ix_market_family_page", table_name="markets")
    op.drop_column("matches", "evidence_complete")
    op.drop_column("markets", "family")
