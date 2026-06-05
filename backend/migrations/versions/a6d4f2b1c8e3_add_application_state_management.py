"""add application state management

Revision ID: a6d4f2b1c8e3
Revises: e8c1a4f6b2d3
Create Date: 2026-05-22 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a6d4f2b1c8e3"
down_revision: Union[str, Sequence[str], None] = "e8c1a4f6b2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_STATUS_CHECK = (
    "status IN ('pending', 'screening', 'interview', 'offer', 'rejected', 'accepted')"
)


def upgrade() -> None:
    op.execute(
        """
        UPDATE applications
        SET status = CASE
            WHEN status = 'submitted' THEN 'pending'
            WHEN status = 'reviewed' THEN 'screening'
            WHEN status IN ('pending', 'screening', 'interview', 'offer', 'rejected', 'accepted') THEN status
            ELSE 'pending'
        END
        """
    )

    op.alter_column(
        "applications",
        "status",
        existing_type=sa.String(length=32),
        existing_nullable=False,
        server_default="pending",
    )
    op.create_check_constraint(
        "ck_applications_status_valid",
        "applications",
        NEW_STATUS_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint("ck_applications_status_valid",
                       "applications", type_="check")

    op.execute(
        """
        UPDATE applications
        SET status = CASE
            WHEN status = 'pending' THEN 'submitted'
            WHEN status IN ('screening', 'interview', 'offer') THEN 'reviewed'
            WHEN status IN ('rejected', 'accepted') THEN status
            ELSE 'submitted'
        END
        """
    )

    op.alter_column(
        "applications",
        "status",
        existing_type=sa.String(length=32),
        existing_nullable=False,
        server_default="submitted",
    )
