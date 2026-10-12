"""enforce case-insensitive email uniqueness

Revision ID: e3a91c7b2d44
Revises: c4e8a1b92f30
Create Date: 2026-10-09 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e3a91c7b2d44"
down_revision: Union[str, Sequence[str], None] = "c4e8a1b92f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Reject case-variant duplicates, then enforce one email per case."""

    connection = op.get_bind()
    duplicates = connection.execute(
        sa.text(
            "SELECT lower(email) AS normalized_email, "
            "COUNT(*) AS copies "
            "FROM users "
            "GROUP BY lower(email) "
            "HAVING COUNT(*) > 1"
        )
    ).fetchall()

    if duplicates:
        conflicts = ", ".join(
            f"{row[0]} ({row[1]})"
            for row in duplicates
        )
        raise RuntimeError(
            "Case-variant duplicate emails must be resolved "
            "before enforcing case-insensitive uniqueness. "
            "Accounts were not merged: "
            + conflicts
        )

    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX ix_users_email_lower "
            "ON users (lower(email))"
        )
    )


def downgrade() -> None:
    """Remove the case-insensitive unique index."""

    op.execute(
        sa.text("DROP INDEX ix_users_email_lower")
    )
