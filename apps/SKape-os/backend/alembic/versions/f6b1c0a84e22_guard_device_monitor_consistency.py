"""guard device monitor consistency

Revision ID: f6b1c0a84e22
Revises: e3a91c7b2d44
Create Date: 2026-10-09 19:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6b1c0a84e22"
down_revision: Union[str, Sequence[str], None] = "e3a91c7b2d44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Reject conflicting rows, then enforce monitor invariants."""

    connection = op.get_bind()
    duplicates = connection.execute(
        sa.text(
            "SELECT device_id, COUNT(*) AS copies "
            "FROM alerts "
            "WHERE alert_type = 'device_offline' "
            "AND NOT is_resolved "
            "GROUP BY device_id "
            "HAVING COUNT(*) > 1"
        )
    ).fetchall()

    if duplicates:
        conflicts = ", ".join(
            f"device {row[0]} ({row[1]})"
            for row in duplicates
        )
        raise RuntimeError(
            "Duplicate unresolved device_offline alerts must be "
            "resolved before enforcing uniqueness. Alerts were "
            "not deleted or merged: "
            + conflicts
        )

    missing_seen = connection.execute(
        sa.text(
            "SELECT device_id FROM devices "
            "WHERE status = 'online' AND last_seen_at IS NULL "
            "ORDER BY device_id"
        )
    ).fetchall()

    if missing_seen:
        conflicts = ", ".join(row[0] for row in missing_seen)
        raise RuntimeError(
            "Devices marked online without last_seen_at must be "
            "corrected before enforcing the check. Rows were not "
            "changed: "
            + conflicts
        )

    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX "
            "uq_alerts_unresolved_device_offline "
            "ON alerts (device_id) "
            "WHERE alert_type = 'device_offline' "
            "AND NOT is_resolved"
        )
    )

    if connection.dialect.name == "sqlite":
        with op.batch_alter_table("devices") as batch:
            batch.create_check_constraint(
                "ck_devices_online_requires_last_seen",
                "status <> 'online' OR last_seen_at IS NOT NULL",
            )
    else:
        op.create_check_constraint(
            "ck_devices_online_requires_last_seen",
            "devices",
            "status <> 'online' OR last_seen_at IS NOT NULL",
        )


def downgrade() -> None:
    """Remove the monitor uniqueness and online-contact checks."""

    connection = op.get_bind()
    op.execute(
        sa.text(
            "DROP INDEX IF EXISTS "
            "uq_alerts_unresolved_device_offline"
        )
    )

    if connection.dialect.name == "sqlite":
        with op.batch_alter_table("devices") as batch:
            batch.drop_constraint(
                "ck_devices_online_requires_last_seen",
                type_="check",
            )
    else:
        op.drop_constraint(
            "ck_devices_online_requires_last_seen",
            "devices",
            type_="check",
        )
