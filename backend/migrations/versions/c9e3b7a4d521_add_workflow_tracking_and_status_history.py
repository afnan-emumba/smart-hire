"""Add workflow tracking and status history

Revision ID: c9e3b7a4d521
Revises: f1b4d3c8a921
Create Date: 2026-05-22 10:00:00.000000

"""

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c9e3b7a4d521"
down_revision: Union[str, Sequence[str], None] = "d2e5f8a1b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("processing_started_at",
                  sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column(
        "ready_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column(
        "archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("publishing_workflow_id",
                  sa.String(length=255), nullable=True))
    op.add_column("jobs", sa.Column("publishing_failed_at",
                  sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column(
        "publishing_error", sa.Text(), nullable=True))
    op.create_index(
        op.f("ix_jobs_publishing_workflow_id"),
        "jobs",
        ["publishing_workflow_id"],
        unique=False,
    )

    op.add_column("applications", sa.Column(
        "workflow_id", sa.String(length=255), nullable=True))
    op.add_column("applications", sa.Column(
        "workflow_initialized_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("applications", sa.Column("workflow_failed_at",
                  sa.DateTime(timezone=True), nullable=True))
    op.add_column("applications", sa.Column(
        "workflow_error", sa.Text(), nullable=True))
    op.add_column("applications", sa.Column("eligibility_result",
                  postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("applications", sa.Column(
        "screening_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("applications", sa.Column(
        "interview_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("applications", sa.Column(
        "offered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("applications", sa.Column(
        "rejected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("applications", sa.Column(
        "accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        op.f("ix_applications_workflow_id"),
        "applications",
        ["workflow_id"],
        unique=False,
    )

    op.create_table(
        "job_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("changed_by_user_id", postgresql.UUID(
            as_uuid=True), nullable=True),
        sa.Column("changed_by_role", sa.String(length=32), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_status_history_job_id"),
                    "job_status_history", ["job_id"], unique=False)

    op.create_table(
        "application_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(
            as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("changed_by_user_id", postgresql.UUID(
            as_uuid=True), nullable=True),
        sa.Column("changed_by_role", sa.String(length=32), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], [
                                "applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_application_status_history_application_id"),
        "application_status_history",
        ["application_id"],
        unique=False,
    )

    op.create_check_constraint(
        "ck_candidate_resumes_parsing_status_valid",
        "candidate_resumes",
        "parsing_status IN ('pending', 'processing', 'parsed', 'failed', 'unsupported')",
    )
    op.create_check_constraint(
        "ck_jobs_jd_parsing_status_valid",
        "jobs",
        "jd_parsing_status IN ('pending', 'processing', 'parsed', 'failed')",
    )

    connection = op.get_bind()
    existing_jobs = connection.execute(
        sa.text(
            "SELECT id, status, COALESCE(updated_at, created_at, now()) AS changed_at FROM jobs")
    ).mappings()
    op.bulk_insert(
        sa.table(
            "job_status_history",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("job_id", postgresql.UUID(as_uuid=True)),
            sa.column("from_status", sa.String(length=32)),
            sa.column("to_status", sa.String(length=32)),
            sa.column("changed_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": uuid.uuid4(),
                "job_id": row["id"],
                "from_status": None,
                "to_status": row["status"],
                "changed_at": row["changed_at"],
            }
            for row in existing_jobs
        ],
    )

    existing_applications = connection.execute(
        sa.text(
            "SELECT id, status, COALESCE(updated_at, created_at, now()) AS changed_at FROM applications"
        )
    ).mappings()
    op.bulk_insert(
        sa.table(
            "application_status_history",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("application_id", postgresql.UUID(as_uuid=True)),
            sa.column("from_status", sa.String(length=32)),
            sa.column("to_status", sa.String(length=32)),
            sa.column("changed_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": uuid.uuid4(),
                "application_id": row["id"],
                "from_status": None,
                "to_status": row["status"],
                "changed_at": row["changed_at"],
            }
            for row in existing_applications
        ],
    )


def downgrade() -> None:
    op.drop_constraint("ck_jobs_jd_parsing_status_valid",
                       "jobs", type_="check")
    op.drop_constraint("ck_candidate_resumes_parsing_status_valid",
                       "candidate_resumes", type_="check")

    op.drop_index(op.f("ix_application_status_history_application_id"),
                  table_name="application_status_history")
    op.drop_table("application_status_history")

    op.drop_index(op.f("ix_job_status_history_job_id"),
                  table_name="job_status_history")
    op.drop_table("job_status_history")

    op.drop_index(op.f("ix_applications_workflow_id"),
                  table_name="applications")
    op.drop_column("applications", "accepted_at")
    op.drop_column("applications", "rejected_at")
    op.drop_column("applications", "offered_at")
    op.drop_column("applications", "interview_started_at")
    op.drop_column("applications", "screening_started_at")
    op.drop_column("applications", "eligibility_result")
    op.drop_column("applications", "workflow_error")
    op.drop_column("applications", "workflow_failed_at")
    op.drop_column("applications", "workflow_initialized_at")
    op.drop_column("applications", "workflow_id")

    op.drop_index(op.f("ix_jobs_publishing_workflow_id"), table_name="jobs")
    op.drop_column("jobs", "publishing_error")
    op.drop_column("jobs", "publishing_failed_at")
    op.drop_column("jobs", "publishing_workflow_id")
    op.drop_column("jobs", "archived_at")
    op.drop_column("jobs", "ready_at")
    op.drop_column("jobs", "processing_started_at")
