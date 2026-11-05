"""add verdict note to finding

Revision ID: 7a8985b00e23
Revises: c319bf6eebff
Create Date: 2026-11-05 11:20:08.123911

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "7a8985b00e23"
down_revision = "c319bf6eebff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("finding", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("verdict_note", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("finding", schema=None) as batch_op:
        batch_op.drop_column("verdict_note")
