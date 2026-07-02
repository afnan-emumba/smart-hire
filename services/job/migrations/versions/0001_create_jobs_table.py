"""Create jobs table

Revision ID: 0001
Revises:
Create Date: 2026-07-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('jobs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('recruiter_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('employment_type', sa.String(length=32), nullable=True),
    sa.Column('seniority_level', sa.String(length=32), nullable=True),
    sa.Column('department', sa.String(length=100), nullable=True),
    sa.Column('job_category', sa.String(length=100), nullable=True),
    sa.Column('location', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('compensation', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('years_of_experience_required', sa.Integer(), nullable=True),
    sa.Column('application_deadline', sa.DateTime(timezone=True), nullable=True),
    sa.Column('description_breakdown', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('required_skills', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('jd_source_type', sa.String(length=32), nullable=True),
    sa.Column('jd_parsing_status', sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('jd_parsing_error', sa.Text(), nullable=True),
    sa.Column('jd_file_name', sa.String(length=255), nullable=True),
    sa.Column('jd_content_type', sa.String(length=255), nullable=True),
    sa.Column('jd_storage_path', sa.String(length=1024), nullable=True),
    sa.Column('jd_uploaded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ready_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('publishing_workflow_id', sa.String(length=255), nullable=True),
    sa.Column('publishing_failed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('publishing_error', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=32), server_default=sa.text("'draft'"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("jd_parsing_status IN ('pending', 'processing', 'parsed', 'failed')", name='ck_jobs_jd_parsing_status_valid'),
    sa.CheckConstraint("status IN ('draft', 'processing', 'ready', 'archived')", name='ck_jobs_status_valid'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_jobs_recruiter_id'), 'jobs', ['recruiter_id'], unique=False)
    op.create_index(op.f('ix_jobs_publishing_workflow_id'), 'jobs', ['publishing_workflow_id'], unique=False)

    op.create_table('job_status_history',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('job_id', sa.UUID(), nullable=False),
    sa.Column('from_status', sa.String(length=32), nullable=True),
    sa.Column('to_status', sa.String(length=32), nullable=False),
    sa.Column('changed_by_user_id', sa.UUID(), nullable=True),
    sa.Column('changed_by_role', sa.String(length=32), nullable=True),
    sa.Column('reason', sa.String(length=255), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_job_status_history_job_id'), 'job_status_history', ['job_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_job_status_history_job_id'), table_name='job_status_history')
    op.drop_table('job_status_history')
    op.drop_index(op.f('ix_jobs_publishing_workflow_id'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_recruiter_id'), table_name='jobs')
    op.drop_table('jobs')
