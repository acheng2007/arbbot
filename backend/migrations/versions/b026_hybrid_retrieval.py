"""Durable versioned embeddings and retrieval health; existing evidence is unchanged."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "b026_hybrid_retrieval"
down_revision = "b025_qualification"
branch_labels = None
depends_on = None


def upgrade():
    document = sa.JSON().with_variant(JSONB(), "postgresql")
    op.create_table(
        "market_embeddings",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("market_key", sa.String(), sa.ForeignKey("markets.key"), nullable=False),
        sa.Column("input_hash", sa.String(), nullable=False),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("vector", document, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_market_embeddings_market_key", "market_embeddings", ["market_key"])
    op.create_index("ix_market_embeddings_input_hash", "market_embeddings", ["input_hash"])
    op.create_table(
        "retrieval_state",
        sa.Column("mode", sa.String(), primary_key=True),
        sa.Column("payload", document, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("retrieval_state")
    op.drop_table("market_embeddings")
