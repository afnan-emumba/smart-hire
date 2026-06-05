"""Add job state management fields

Revision ID: b7d6e91a4c2f
Revises: 2a6c9b1d4e57
Create Date: 2026-05-19 10:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7d6e91a4c2f"
down_revision: Union[str, Sequence[str], None] = "2a6c9b1d4e57"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE jobs
        SET status = CASE status
                WHEN 'publishing' THEN 'processing'
                WHEN 'published' THEN 'ready'
                WHEN 'closed' THEN 'archived'
                ELSE 'draft'
            END,
            jd_parsing_status = CASE jd_parsing_status
                WHEN 'not_started' THEN 'pending'
                WHEN 'uploaded' THEN 'pending'
                WHEN 'queued' THEN 'pending'
                WHEN 'processing' THEN 'processing'
                WHEN 'parsed' THEN 'parsed'
                WHEN 'failed' THEN 'failed'
                ELSE 'pending'
            END
        """
    )

    op.alter_column(
        "jobs",
        "status",
        existing_type=sa.String(length=32),
        existing_nullable=False,
        server_default="draft",
    )
    op.alter_column(
        "jobs",
        "jd_parsing_status",
        existing_type=sa.String(length=32),
        existing_nullable=False,
        server_default="pending",
    )
    op.create_check_constraint(
        "ck_jobs_status_valid",
        "jobs",
        "status IN ('draft', 'processing', 'ready', 'archived')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_jobs_status_valid", "jobs", type_="check")

    op.execute(
        """
        UPDATE jobs
        SET status = CASE status
                WHEN 'processing' THEN 'publishing'
                WHEN 'ready' THEN 'published'
                WHEN 'archived' THEN 'closed'
                ELSE 'draft'
            END,
            jd_parsing_status = CASE jd_parsing_status
                WHEN 'pending' THEN 'not_started'
                WHEN 'processing' THEN 'processing'
                WHEN 'parsed' THEN 'parsed'
                WHEN 'failed' THEN 'failed'
                ELSE 'not_started'
            END
        """
    )

    op.alter_column(
        "jobs",
        "jd_parsing_status",
        existing_type=sa.String(length=32),
        existing_nullable=False,
        server_default="not_started",
    )
    op.alter_column(
        "jobs",
        "status",
        existing_type=sa.String(length=32),
        existing_nullable=False,
        server_default="draft",
    )
