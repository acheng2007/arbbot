"""Exact signed evaluation metrics and durable latest-per-pair pointers."""

import sqlalchemy as sa
from alembic import op

revision = "b023_evaluation_heads"
down_revision = "b022_execution_configuration"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("opportunities") as batch:
        batch.alter_column("net_profit", existing_type=sa.Numeric(30, 12), type_=sa.Numeric())
        batch.alter_column("capital_required", existing_type=sa.Numeric(30, 12), type_=sa.Numeric())
    op.add_column("evaluations", sa.Column("status", sa.String(), nullable=True))
    op.add_column("evaluations", sa.Column("net_profit", sa.Numeric(), nullable=True))
    op.add_column("evaluations", sa.Column("capital_required", sa.Numeric(), nullable=True))
    op.create_table(
        "evaluation_heads",
        sa.Column("match_id", sa.String(), sa.ForeignKey("matches.id"), primary_key=True),
        sa.Column("mode", sa.String(), nullable=False, index=True),
        sa.Column(
            "evaluation_id",
            sa.String(),
            sa.ForeignKey("evaluations.id"),
            nullable=False,
            unique=True,
        ),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "UPDATE opportunities SET net_profit=(payload->>'net_profit')::numeric, "
            "capital_required=(payload->>'capital_required')::numeric"
        )
        op.execute(
            "UPDATE evaluations SET status=payload->>'status', "
            "net_profit=(payload->'best_calculation'->>'net_profit')::numeric, "
            "capital_required=(payload->'best_calculation'->>'capital_required')::numeric"
        )
    evaluations = sa.table(
        "evaluations",
        sa.column("id"),
        sa.column("match_id"),
        sa.column("mode"),
        sa.column("evaluated_at"),
    )
    ranked = sa.select(
        evaluations.c.id,
        evaluations.c.match_id,
        evaluations.c.mode,
        sa.func.row_number()
        .over(
            partition_by=evaluations.c.match_id,
            order_by=(evaluations.c.evaluated_at.desc(), evaluations.c.id.desc()),
        )
        .label("position"),
    ).subquery()
    heads = sa.table(
        "evaluation_heads", sa.column("match_id"), sa.column("mode"), sa.column("evaluation_id")
    )
    op.get_bind().execute(
        sa.insert(heads).from_select(
            ["match_id", "mode", "evaluation_id"],
            sa.select(ranked.c.match_id, ranked.c.mode, ranked.c.id).where(ranked.c.position == 1),
        )
    )


def downgrade():
    op.drop_table("evaluation_heads")
    op.drop_column("evaluations", "capital_required")
    op.drop_column("evaluations", "net_profit")
    op.drop_column("evaluations", "status")
    with op.batch_alter_table("opportunities") as batch:
        batch.alter_column("net_profit", existing_type=sa.Numeric(), type_=sa.Numeric(30, 12))
        batch.alter_column("capital_required", existing_type=sa.Numeric(), type_=sa.Numeric(30, 12))
