"""Immutable advisory classifications and durable current jobs/cursor."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "b024_classification"
down_revision = "b023_evaluation_heads"
branch_labels = None
depends_on = None


def upgrade():
    document = sa.JSON().with_variant(JSONB(), "postgresql")
    op.create_table(
        "classification_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("match_id", sa.String(), nullable=False, index=True),
        sa.Column("mode", sa.String(), nullable=False, index=True),
        sa.Column("input_hash", sa.String(), nullable=False, index=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", document, nullable=False),
    )
    op.create_table(
        "classification_jobs",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("mode", sa.String(), nullable=False, index=True),
        sa.Column("match_id", sa.String(), nullable=False, index=True),
        sa.Column("input_hash", sa.String(), nullable=False),
        sa.Column("request", document, nullable=False),
        sa.Column("semantic_inputs", document, nullable=False, server_default="{}"),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), sa.ForeignKey("classification_runs.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "classification_scheduler",
        sa.Column("mode", sa.String(), primary_key=True),
        sa.Column("payload", document, nullable=False),
    )


def downgrade():
    op.drop_table("classification_scheduler")
    op.drop_table("classification_jobs")
    op.drop_table("classification_runs")
