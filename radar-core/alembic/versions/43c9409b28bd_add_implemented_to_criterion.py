"""add implemented to criterion

Revision ID: 43c9409b28bd
Revises: 7a8985b00e23
Create Date: 2026-11-05 15:10:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "43c9409b28bd"
down_revision = "7a8985b00e23"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("criterion", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("implemented", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    # Until the next `radar-audit score` syncs it from the normalizer registry, a criterion
    # that has ever been scored is the best available sign that it is implemented.
    op.execute(
        "UPDATE criterion SET implemented = 1 "
        "WHERE id IN (SELECT DISTINCT criterion_id FROM score WHERE criterion_id IS NOT NULL)"
    )


def downgrade() -> None:
    with op.batch_alter_table("criterion", schema=None) as batch_op:
        batch_op.drop_column("implemented")
