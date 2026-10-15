"""Automatic qualification audit/jobs and separate conditional price gaps."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "b025_qualification"
down_revision = "b024_classification"
branch_labels = None
depends_on = None


def upgrade():
    document = sa.JSON().with_variant(JSONB(), "postgresql")
    op.create_table(
        "qualification_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("match_id", sa.String(), nullable=False, index=True),
        sa.Column("mode", sa.String(), nullable=False, index=True),
        sa.Column("input_hash", sa.String(), nullable=False, index=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", document, nullable=False),
    )
    op.create_table(
        "qualification_jobs",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("mode", sa.String(), nullable=False, index=True),
        sa.Column("match_id", sa.String(), nullable=False, index=True),
        sa.Column("input_hash", sa.String(), nullable=False),
        sa.Column("pair", document, nullable=False),
        sa.Column("state", sa.String(), nullable=False, index=True),
        sa.Column("run_id", sa.String(), sa.ForeignKey("qualification_runs.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "potential_opportunities",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("match_id", sa.String(), nullable=False, index=True),
        sa.Column("mode", sa.String(), nullable=False, index=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("gross_spread", sa.Numeric(), nullable=False),
        sa.Column("capital_required", sa.Numeric()),
        sa.Column("active", sa.Boolean(), nullable=False, index=True),
        sa.Column("payload", document, nullable=False),
    )


def downgrade():
    op.drop_table("potential_opportunities")
    op.drop_table("qualification_jobs")
    op.drop_table("qualification_runs")
