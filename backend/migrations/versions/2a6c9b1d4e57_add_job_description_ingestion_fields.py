"""Add job description ingestion fields

Revision ID: 2a6c9b1d4e57
Revises: f1b4d3c8a921
Create Date: 2026-05-17 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2a6c9b1d4e57"
down_revision: Union[str, Sequence[str], None] = "f1b4d3c8a921"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "jobs",
        "description",
        existing_type=sa.Text(),
        nullable=True,
    )
    op.add_column("jobs", sa.Column("jd_source_type", sa.String(length=32), nullable=True))
    op.add_column(
        "jobs",
        sa.Column(
            "jd_parsing_status",
            sa.String(length=32),
            nullable=False,
            server_default="not_started",
        ),
    )
    op.add_column("jobs", sa.Column("jd_parsing_error", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("jd_file_name", sa.String(length=255), nullable=True))
    op.add_column("jobs", sa.Column("jd_content_type", sa.String(length=255), nullable=True))
    op.add_column("jobs", sa.Column("jd_storage_path", sa.String(length=1024), nullable=True))
    op.add_column("jobs", sa.Column("jd_uploaded_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        """
        UPDATE jobs
        SET jd_source_type = CASE
                WHEN description IS NOT NULL AND btrim(description) <> '' THEN 'manual_text'
                ELSE NULL
            END,
            jd_parsing_status = CASE
                WHEN description IS NOT NULL AND btrim(description) <> '' THEN 'parsed'
                ELSE 'not_started'
            END
        """
    )


def downgrade() -> None:
    op.execute("UPDATE jobs SET description = '' WHERE description IS NULL")
    op.drop_column("jobs", "jd_uploaded_at")
    op.drop_column("jobs", "jd_storage_path")
    op.drop_column("jobs", "jd_content_type")
    op.drop_column("jobs", "jd_file_name")
    op.drop_column("jobs", "jd_parsing_error")
    op.drop_column("jobs", "jd_parsing_status")
    op.drop_column("jobs", "jd_source_type")
    op.alter_column(
        "jobs",
        "description",
        existing_type=sa.Text(),
        nullable=False,
    )