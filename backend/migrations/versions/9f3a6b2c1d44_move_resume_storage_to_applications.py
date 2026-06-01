"""Move resume storage from candidates to applications

Revision ID: 9f3a6b2c1d44
Revises: 8d589fc077b1
Create Date: 2026-05-14 11:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "9f3a6b2c1d44"
down_revision: Union[str, Sequence[str], None] = "8d589fc077b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("candidates", "resume_data")

    op.add_column("applications", sa.Column("resume_file_name", sa.String(length=255), nullable=True))
    op.add_column("applications", sa.Column("resume_content_type", sa.String(length=255), nullable=True))
    op.add_column("applications", sa.Column("resume_storage_path", sa.String(length=1024), nullable=True))
    op.add_column("applications", sa.Column("resume_uploaded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "applications",
        sa.Column("resume_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applications", "resume_data")
    op.drop_column("applications", "resume_uploaded_at")
    op.drop_column("applications", "resume_storage_path")
    op.drop_column("applications", "resume_content_type")
    op.drop_column("applications", "resume_file_name")

    op.add_column(
        "candidates",
        sa.Column("resume_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )