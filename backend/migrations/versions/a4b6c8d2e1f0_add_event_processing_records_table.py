"""Add event processing records table

Revision ID: a4b6c8d2e1f0
Revises: f3e8c2d1a9b0
Create Date: 2026-06-01 10:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a4b6c8d2e1f0"
down_revision: Union[str, Sequence[str], None] = "f3e8c2d1a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_processing_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("handler_name", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("topic_name", sa.String(length=255), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(length=64), server_default=sa.text("'v1'"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'queued', 'processing', 'completed', 'failed')",
            name="ck_event_processing_records_status_valid",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id",
            "handler_name",
            name="uq_event_processing_records_event_handler",
        ),
    )
    op.create_index(
        op.f("ix_event_processing_records_aggregate_id"),
        "event_processing_records",
        ["aggregate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_event_processing_records_event_id"),
        "event_processing_records",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_event_processing_records_event_type"),
        "event_processing_records",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_event_processing_records_handler_name"),
        "event_processing_records",
        ["handler_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_event_processing_records_topic_name"),
        "event_processing_records",
        ["topic_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_event_processing_records_topic_name"), table_name="event_processing_records")
    op.drop_index(op.f("ix_event_processing_records_handler_name"), table_name="event_processing_records")
    op.drop_index(op.f("ix_event_processing_records_event_type"), table_name="event_processing_records")
    op.drop_index(op.f("ix_event_processing_records_event_id"), table_name="event_processing_records")
    op.drop_index(op.f("ix_event_processing_records_aggregate_id"), table_name="event_processing_records")
    op.drop_table("event_processing_records")