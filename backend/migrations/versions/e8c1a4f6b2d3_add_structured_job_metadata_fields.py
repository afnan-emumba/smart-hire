"""Add structured job metadata fields

Revision ID: e8c1a4f6b2d3
Revises: b7d6e91a4c2f
Create Date: 2026-05-21 19:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e8c1a4f6b2d3"
down_revision: Union[str, Sequence[str], None] = "b7d6e91a4c2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("employment_type",
                  sa.String(length=32), nullable=True))
    op.add_column("jobs", sa.Column("seniority_level",
                  sa.String(length=32), nullable=True))
    op.add_column("jobs", sa.Column(
        "department", sa.String(length=100), nullable=True))
    op.add_column("jobs", sa.Column("job_category",
                  sa.String(length=100), nullable=True))
    op.add_column("jobs", sa.Column("location", postgresql.JSONB(
        astext_type=sa.Text()), nullable=True))
    op.add_column("jobs", sa.Column("compensation", postgresql.JSONB(
        astext_type=sa.Text()), nullable=True))
    op.add_column("jobs", sa.Column(
        "years_of_experience_required", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("application_deadline",
                  sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "application_deadline")
    op.drop_column("jobs", "years_of_experience_required")
    op.drop_column("jobs", "compensation")
    op.drop_column("jobs", "location")
    op.drop_column("jobs", "job_category")
    op.drop_column("jobs", "department")
    op.drop_column("jobs", "seniority_level")
    op.drop_column("jobs", "employment_type")
