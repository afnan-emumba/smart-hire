"""Normalize candidate resume storage

Revision ID: d2e5f8a1b3c4
Revises: a6d4f2b1c8e3
Create Date: 2026-05-22 12:30:00.000000

"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d2e5f8a1b3c4"
down_revision: Union[str, Sequence[str], None] = "a6d4f2b1c8e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _parse_resume_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def upgrade() -> None:
    op.create_table(
        "candidate_resumes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(
            as_uuid=True), nullable=False),
        sa.Column("source_application_id", postgresql.UUID(
            as_uuid=True), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("storage_path", sa.String(length=1024), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parsing_status", sa.String(length=32),
                  nullable=False, server_default="pending"),
        sa.Column("parsing_error", sa.Text(), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parser_version", sa.String(length=64), nullable=True),
        sa.Column(
            "schema_version",
            sa.String(length=64),
            nullable=False,
            server_default="resume_profile.v1",
        ),
        sa.Column("raw_markdown", sa.Text(), nullable=True),
        sa.Column("structured_data", postgresql.JSONB(
            astext_type=sa.Text()), nullable=True),
        sa.Column(
            "extraction_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_application_id"], [
                                "applications.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_candidate_resumes_candidate_id"),
                    "candidate_resumes", ["candidate_id"], unique=False)
    op.create_index(
        op.f("ix_candidate_resumes_source_application_id"),
        "candidate_resumes",
        ["source_application_id"],
        unique=False,
    )

    op.add_column("applications", sa.Column(
        "resume_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index(op.f("ix_applications_resume_id"),
                    "applications", ["resume_id"], unique=False)
    op.create_foreign_key(
        "applications_resume_id_fkey",
        "applications",
        "candidate_resumes",
        ["resume_id"],
        ["id"],
        ondelete="SET NULL",
    )

    connection = op.get_bind()
    applications = sa.table(
        "applications",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("candidate_id", postgresql.UUID(as_uuid=True)),
        sa.column("metadata", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("resume_file_name", sa.String(length=255)),
        sa.column("resume_content_type", sa.String(length=255)),
        sa.column("resume_storage_path", sa.String(length=1024)),
        sa.column("resume_uploaded_at", sa.DateTime(timezone=True)),
        sa.column("resume_data", postgresql.JSONB(astext_type=sa.Text())),
    )
    candidate_resumes = sa.table(
        "candidate_resumes",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("candidate_id", postgresql.UUID(as_uuid=True)),
        sa.column("source_application_id", postgresql.UUID(as_uuid=True)),
        sa.column("file_name", sa.String(length=255)),
        sa.column("content_type", sa.String(length=255)),
        sa.column("storage_path", sa.String(length=1024)),
        sa.column("uploaded_at", sa.DateTime(timezone=True)),
        sa.column("parsing_status", sa.String(length=32)),
        sa.column("parsing_error", sa.Text()),
        sa.column("parsed_at", sa.DateTime(timezone=True)),
        sa.column("parser_version", sa.String(length=64)),
        sa.column("schema_version", sa.String(length=64)),
        sa.column("raw_markdown", sa.Text()),
        sa.column("structured_data", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("extraction_metadata",
                  postgresql.JSONB(astext_type=sa.Text())),
    )

    existing_rows = connection.execute(
        sa.select(
            applications.c.id,
            applications.c.candidate_id,
            applications.c.metadata,
            applications.c.resume_file_name,
            applications.c.resume_content_type,
            applications.c.resume_storage_path,
            applications.c.resume_uploaded_at,
            applications.c.resume_data,
        ).where(
            sa.or_(
                applications.c.resume_file_name.is_not(None),
                applications.c.resume_content_type.is_not(None),
                applications.c.resume_storage_path.is_not(None),
                applications.c.resume_uploaded_at.is_not(None),
                applications.c.resume_data.is_not(None),
            )
        )
    ).mappings().all()

    for row in existing_rows:
        resume_id = uuid.uuid4()
        metadata = row["metadata"] if isinstance(row["metadata"], dict) else {}
        resume_parsing = metadata.get(
            "resume_parsing", {}) if isinstance(metadata, dict) else {}
        structured_data = row["resume_data"] if isinstance(
            row["resume_data"], dict) else None
        parsed_at = _parse_resume_timestamp(resume_parsing.get("parsed_at"))
        parsing_status = resume_parsing.get("status") or (
            "parsed" if structured_data else "pending")
        parsing_error = resume_parsing.get("error")

        connection.execute(
            candidate_resumes.insert().values(
                id=resume_id,
                candidate_id=row["candidate_id"],
                source_application_id=row["id"],
                file_name=row["resume_file_name"],
                content_type=row["resume_content_type"],
                storage_path=row["resume_storage_path"],
                uploaded_at=row["resume_uploaded_at"],
                parsing_status=parsing_status,
                parsing_error=parsing_error,
                parsed_at=parsed_at,
                parser_version=None,
                schema_version="resume_profile.v1",
                raw_markdown=structured_data.get(
                    "markdown") if structured_data else None,
                structured_data=structured_data,
                extraction_metadata={
                    "source": "application_migration",
                    "migrated_from_application_id": str(row["id"]),
                },
            )
        )

        connection.execute(
            applications.update()
            .where(applications.c.id == row["id"])
            .values(resume_id=resume_id)
        )

    op.drop_column("applications", "resume_data")
    op.drop_column("applications", "resume_uploaded_at")
    op.drop_column("applications", "resume_storage_path")
    op.drop_column("applications", "resume_content_type")
    op.drop_column("applications", "resume_file_name")


def downgrade() -> None:
    op.add_column("applications", sa.Column(
        "resume_file_name", sa.String(length=255), nullable=True))
    op.add_column("applications", sa.Column(
        "resume_content_type", sa.String(length=255), nullable=True))
    op.add_column("applications", sa.Column(
        "resume_storage_path", sa.String(length=1024), nullable=True))
    op.add_column("applications", sa.Column("resume_uploaded_at",
                  sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "applications",
        sa.Column("resume_data", postgresql.JSONB(
            astext_type=sa.Text()), nullable=True),
    )

    connection = op.get_bind()
    applications = sa.table(
        "applications",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("resume_id", postgresql.UUID(as_uuid=True)),
        sa.column("resume_file_name", sa.String(length=255)),
        sa.column("resume_content_type", sa.String(length=255)),
        sa.column("resume_storage_path", sa.String(length=1024)),
        sa.column("resume_uploaded_at", sa.DateTime(timezone=True)),
        sa.column("resume_data", postgresql.JSONB(astext_type=sa.Text())),
    )
    candidate_resumes = sa.table(
        "candidate_resumes",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("file_name", sa.String(length=255)),
        sa.column("content_type", sa.String(length=255)),
        sa.column("storage_path", sa.String(length=1024)),
        sa.column("uploaded_at", sa.DateTime(timezone=True)),
        sa.column("raw_markdown", sa.Text()),
        sa.column("structured_data", postgresql.JSONB(astext_type=sa.Text())),
    )

    joined_rows = connection.execute(
        sa.select(
            applications.c.id,
            applications.c.resume_id,
            candidate_resumes.c.file_name,
            candidate_resumes.c.content_type,
            candidate_resumes.c.storage_path,
            candidate_resumes.c.uploaded_at,
            candidate_resumes.c.raw_markdown,
            candidate_resumes.c.structured_data,
        ).select_from(
            applications.join(
                candidate_resumes, applications.c.resume_id == candidate_resumes.c.id)
        )
    ).mappings().all()

    for row in joined_rows:
        structured_data = row["structured_data"] if isinstance(
            row["structured_data"], dict) else None
        if structured_data is None and row["raw_markdown"]:
            structured_data = {"markdown": row["raw_markdown"]}

        connection.execute(
            applications.update()
            .where(applications.c.id == row["id"])
            .values(
                resume_file_name=row["file_name"],
                resume_content_type=row["content_type"],
                resume_storage_path=row["storage_path"],
                resume_uploaded_at=row["uploaded_at"],
                resume_data=structured_data,
            )
        )

    op.drop_constraint("applications_resume_id_fkey",
                       "applications", type_="foreignkey")
    op.drop_index(op.f("ix_applications_resume_id"), table_name="applications")
    op.drop_column("applications", "resume_id")
    op.drop_index(op.f("ix_candidate_resumes_source_application_id"),
                  table_name="candidate_resumes")
    op.drop_index(op.f("ix_candidate_resumes_candidate_id"),
                  table_name="candidate_resumes")
    op.drop_table("candidate_resumes")
