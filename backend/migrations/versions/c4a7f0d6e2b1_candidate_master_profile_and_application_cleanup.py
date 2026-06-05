"""Add candidate master profile data and drop redundant application recruiter fk

Revision ID: c4a7f0d6e2b1
Revises: 9f3a6b2c1d44
Create Date: 2026-05-14 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c4a7f0d6e2b1"
down_revision: Union[str, Sequence[str], None] = "9f3a6b2c1d44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column(
            "master_profile_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )

    op.execute(
        "ALTER TABLE applications DROP CONSTRAINT IF EXISTS applications_recruiter_id_fkey")
    op.drop_index(op.f("ix_applications_recruiter_id"),
                  table_name="applications")
    op.drop_column("applications", "recruiter_id")


def downgrade() -> None:
    op.add_column("applications", sa.Column(
        "recruiter_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_applications_recruiter_id"),
                    "applications", ["recruiter_id"], unique=False)
    op.create_foreign_key(
        "applications_recruiter_id_fkey",
        "applications",
        "recruiters",
        ["recruiter_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_column("candidates", "master_profile_data")
