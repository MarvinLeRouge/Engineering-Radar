"""add fingerprint to finding

Revision ID: 76cdb0e682e8
Revises: 1a3584e18846
Create Date: 2026-10-21 09:11:19.196453

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "76cdb0e682e8"
down_revision = "1a3584e18846"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("finding", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("fingerprint", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )
        batch_op.create_index(batch_op.f("ix_finding_fingerprint"), ["fingerprint"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("finding", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_finding_fingerprint"))
        batch_op.drop_column("fingerprint")
