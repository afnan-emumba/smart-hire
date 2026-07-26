"""Create notifications table

Revision ID: 0001
Revises:
Create Date: 2026-07-26 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("recipient_user_id", sa.UUID(), nullable=False),
        sa.Column("recipient_role", sa.String(length=32), nullable=False),
        sa.Column("notification_type", sa.String(length=64), nullable=False),
        sa.Column(
            "channel",
            sa.String(length=32),
            server_default="in_app",
            nullable=False,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notifications_recipient_user_id"),
        "notifications",
        ["recipient_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_status"), "notifications", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_notifications_dedupe_key"),
        "notifications",
        ["dedupe_key"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_notifications_dedupe_key"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_status"), table_name="notifications")
    op.drop_index(
        op.f("ix_notifications_recipient_user_id"), table_name="notifications"
    )
    op.drop_table("notifications")
