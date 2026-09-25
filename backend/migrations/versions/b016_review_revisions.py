"""Immutable definition/review revisions and compare-and-swap heads."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b016_review_revisions"
down_revision = "b005_discovery_catalogs"
branch_labels = None
depends_on = None


def upgrade():
    document = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "definition_revisions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("market_key", sa.String(), sa.ForeignKey("markets.key"), nullable=False),
        sa.Column("previous_revision_id", sa.String(32), sa.ForeignKey("definition_revisions.id")),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload", document, nullable=False),
    )
    op.create_index("ix_definition_revisions_market_key", "definition_revisions", ["market_key"])
    op.create_table(
        "definition_heads",
        sa.Column("market_key", sa.String(), sa.ForeignKey("markets.key"), primary_key=True),
        sa.Column(
            "revision_id",
            sa.String(32),
            sa.ForeignKey("definition_revisions.id"),
            nullable=False,
            unique=True,
        ),
    )
    op.create_table(
        "review_revisions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("pair_key", sa.String(64), nullable=False),
        sa.Column("previous_revision_id", sa.String(32), sa.ForeignKey("review_revisions.id")),
        sa.Column(
            "left_draft_id", sa.String(32), sa.ForeignKey("definition_revisions.id"), nullable=False
        ),
        sa.Column(
            "right_draft_id",
            sa.String(32),
            sa.ForeignKey("definition_revisions.id"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload", document, nullable=False),
    )
    op.create_index("ix_review_revisions_mode", "review_revisions", ["mode"])
    op.create_index("ix_review_revisions_pair_key", "review_revisions", ["pair_key"])
    op.create_table(
        "review_heads",
        sa.Column("pair_key", sa.String(64), primary_key=True),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column(
            "revision_id",
            sa.String(32),
            sa.ForeignKey("review_revisions.id"),
            nullable=False,
            unique=True,
        ),
    )
    op.create_index("ix_review_heads_mode", "review_heads", ["mode"])


def downgrade():
    op.drop_table("review_heads")
    op.drop_table("review_revisions")
    op.drop_table("definition_heads")
    op.drop_table("definition_revisions")
