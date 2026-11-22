"""Widen published_report.methodology_version to the payload's 50 characters (FEAT-042).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-22 10:00:00
"""

import sqlmodel
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("published_report") as batch_op:
        batch_op.alter_column(
            "methodology_version",
            existing_type=sqlmodel.sql.sqltypes.AutoString(length=20),
            type_=sqlmodel.sql.sqltypes.AutoString(length=50),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("published_report") as batch_op:
        batch_op.alter_column(
            "methodology_version",
            existing_type=sqlmodel.sql.sqltypes.AutoString(length=50),
            type_=sqlmodel.sql.sqltypes.AutoString(length=20),
            existing_nullable=False,
        )
