"""Set structured default for candidate master profile data

Revision ID: f1b4d3c8a921
Revises: c4a7f0d6e2b1
Create Date: 2026-05-14 17:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f1b4d3c8a921"
down_revision: Union[str, Sequence[str], None] = "c4a7f0d6e2b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CANONICAL_MASTER_PROFILE_DATA = (
    '{"summary": null, "skills": [], "contact": {"phone": null, "location": null}, '
    '"education": [], "work_experience": [], "links": {"linkedin": null, "github": null, '
    '"portfolio": null, "website": null}}'
)


def upgrade() -> None:
    op.alter_column(
        "candidates",
        "master_profile_data",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=False,
        server_default=sa.text(f"'{CANONICAL_MASTER_PROFILE_DATA}'::jsonb"),
    )

    op.execute(
        """
        UPDATE candidates
        SET master_profile_data = jsonb_build_object(
            'summary', COALESCE(
                master_profile_data->'master_profile'->'summary',
                master_profile_data->'summary',
                'null'::jsonb
            ),
            'skills', COALESCE(
                master_profile_data->'master_profile'->'top_skills',
                master_profile_data->'skills',
                '[]'::jsonb
            ),
            'contact', CASE
                WHEN jsonb_typeof(master_profile_data->'contact') = 'object' THEN
                    jsonb_build_object(
                        'phone', COALESCE(master_profile_data->'contact'->'phone', 'null'::jsonb),
                        'location', COALESCE(master_profile_data->'contact'->'location', 'null'::jsonb)
                    )
                WHEN jsonb_typeof(master_profile_data->'personal_info') = 'object' THEN
                    jsonb_build_object(
                        'phone', COALESCE(master_profile_data->'personal_info'->'phone', 'null'::jsonb),
                        'location', COALESCE(master_profile_data->'personal_info'->'location', 'null'::jsonb)
                    )
                ELSE
                    jsonb_build_object('phone', 'null'::jsonb, 'location', 'null'::jsonb)
            END,
            'education', COALESCE(master_profile_data->'education', '[]'::jsonb),
            'work_experience', COALESCE(master_profile_data->'work_experience', '[]'::jsonb),
            'links', CASE
                WHEN jsonb_typeof(master_profile_data->'links') = 'object' THEN
                    jsonb_build_object(
                        'linkedin', COALESCE(master_profile_data->'links'->'linkedin', 'null'::jsonb),
                        'github', COALESCE(master_profile_data->'links'->'github', 'null'::jsonb),
                        'portfolio', COALESCE(master_profile_data->'links'->'portfolio', 'null'::jsonb),
                        'website', COALESCE(master_profile_data->'links'->'website', 'null'::jsonb)
                    )
                ELSE
                    jsonb_build_object(
                        'linkedin', 'null'::jsonb,
                        'github', 'null'::jsonb,
                        'portfolio', 'null'::jsonb,
                        'website', 'null'::jsonb
                    )
            END
        )
        WHERE master_profile_data = '{}'::jsonb
           OR master_profile_data ? 'personal_info'
           OR master_profile_data ? 'master_profile';
        """
    )


def downgrade() -> None:
    op.alter_column(
        "candidates",
        "master_profile_data",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )