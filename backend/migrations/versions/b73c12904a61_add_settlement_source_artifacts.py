"""Add immutable settlement source captures and retrieval failures.

Revision ID: b73c12904a61
Revises: a2a3099f82df
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b73c12904a61"
down_revision = "a2a3099f82df"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "source_artifacts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("market_key", sa.String(), sa.ForeignKey("markets.key"), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=True),
        sa.Column("content", sa.LargeBinary(), nullable=True),
        sa.Column(
            "payload", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
    )
    op.create_index("ix_source_history", "source_artifacts", ["market_key", "retrieved_at"])


def downgrade():
    op.drop_index("ix_source_history", table_name="source_artifacts")
    op.drop_table("source_artifacts")
