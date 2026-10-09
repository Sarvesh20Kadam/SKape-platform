"""set organization active server default

Revision ID: c4e8a1b92f30
Revises: 4a4fc62a3a6a
Create Date: 2026-10-09 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4e8a1b92f30"
down_revision: Union[str, Sequence[str], None] = "4a4fc62a3a6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Backfill nulls, then enforce NOT NULL and a server default."""

    op.execute(
        sa.text(
            "UPDATE organizations "
            "SET is_active = TRUE "
            "WHERE is_active IS NULL"
        )
    )

    with op.batch_alter_table("organizations") as batch_op:
        batch_op.alter_column(
            "is_active",
            existing_type=sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        )


def downgrade() -> None:
    """Remove the server default and keep the NOT NULL constraint."""

    with op.batch_alter_table("organizations") as batch_op:
        batch_op.alter_column(
            "is_active",
            existing_type=sa.Boolean(),
            nullable=False,
            existing_server_default=sa.true(),
            server_default=None,
        )
