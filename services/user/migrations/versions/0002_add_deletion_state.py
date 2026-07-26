"""Add deletion_state to recruiters and candidates

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

_TABLES = ("recruiters", "candidates")


def upgrade() -> None:
    """Upgrade schema."""
    for table_name in _TABLES:
        op.add_column(
            table_name,
            sa.Column(
                "deletion_state",
                sa.String(length=20),
                nullable=False,
                server_default="active",
            ),
        )
        op.create_index(
            op.f(f"ix_{table_name}_deletion_state"),
            table_name,
            ["deletion_state"],
            unique=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table_name in reversed(_TABLES):
        op.drop_index(op.f(f"ix_{table_name}_deletion_state"), table_name=table_name)
        op.drop_column(table_name, "deletion_state")
