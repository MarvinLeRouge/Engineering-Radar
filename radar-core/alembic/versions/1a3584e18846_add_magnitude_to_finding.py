"""add magnitude to finding

Revision ID: 1a3584e18846
Revises: 397586186d42
Create Date: 2026-10-06 10:15:52.016046

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1a3584e18846"
down_revision = "397586186d42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("finding", schema=None) as batch_op:
        batch_op.add_column(sa.Column("magnitude", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("finding", schema=None) as batch_op:
        batch_op.drop_column("magnitude")
