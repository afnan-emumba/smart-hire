"""Add deletion_state to jobs

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-26 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "jobs",
        sa.Column(
            "deletion_state",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
    )
    op.create_index(
        op.f("ix_jobs_deletion_state"), "jobs", ["deletion_state"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_jobs_deletion_state"), table_name="jobs")
    op.drop_column("jobs", "deletion_state")
