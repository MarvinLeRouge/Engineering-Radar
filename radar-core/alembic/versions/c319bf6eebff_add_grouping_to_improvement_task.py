"""add grouping to improvement task

Revision ID: c319bf6eebff
Revises: 76cdb0e682e8
Create Date: 2026-10-22 12:42:42.983864

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "c319bf6eebff"
down_revision = "76cdb0e682e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("improvement_task", schema=None) as batch_op:
        batch_op.add_column(sa.Column("criterion_id", sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column("file", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(
            sa.Column("group_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False)
        )
        batch_op.create_index(
            batch_op.f("ix_improvement_task_criterion_id"), ["criterion_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_improvement_task_file"), ["file"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_improvement_task_group_key"), ["group_key"], unique=True
        )
        batch_op.create_foreign_key(
            "fk_improvement_task_criterion_id_criterion",
            "criterion",
            ["criterion_id"],
            ["id"],
        )

    with op.batch_alter_table("roadmap_item", schema=None) as batch_op:
        batch_op.alter_column(
            "priority",
            existing_type=sa.Integer(),
            type_=sa.Float(),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("roadmap_item", schema=None) as batch_op:
        batch_op.alter_column(
            "priority",
            existing_type=sa.Float(),
            type_=sa.Integer(),
            existing_nullable=False,
        )

    with op.batch_alter_table("improvement_task", schema=None) as batch_op:
        batch_op.drop_constraint("fk_improvement_task_criterion_id_criterion", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_improvement_task_group_key"))
        batch_op.drop_index(batch_op.f("ix_improvement_task_file"))
        batch_op.drop_index(batch_op.f("ix_improvement_task_criterion_id"))
        batch_op.drop_column("group_key")
        batch_op.drop_column("file")
        batch_op.drop_column("criterion_id")
