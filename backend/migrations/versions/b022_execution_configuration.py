"""Immutable reviewed access, applicability, and fee policy revisions."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "b022_execution_configuration"
down_revision = "b021_us_catalog_inventory"
branch_labels = None
depends_on = None


def upgrade():
    document = sa.JSON().with_variant(JSONB, "postgresql")
    op.create_table(
        "execution_configuration_revisions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("key", sa.String(), nullable=False, index=True),
        sa.Column("payload", document, nullable=False),
    )
    op.create_table(
        "execution_configuration_heads",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column(
            "revision_id",
            sa.String(32),
            sa.ForeignKey("execution_configuration_revisions.id"),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_table("execution_configuration_heads")
    op.drop_table("execution_configuration_revisions")
