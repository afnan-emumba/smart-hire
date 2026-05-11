# Database: Schema, Migrations, and Design

## Overview

SmartHire uses PostgreSQL with SQLAlchemy 2.0 async models and Alembic migrations. The schema is designed for strong consistency on core entities while keeping selective JSONB fields for flexible data.

## Entity Relationship Diagram

```mermaid
erDiagram
    RECRUITERS ||--o{ JOBS : posts
    RECRUITERS ||--o{ APPLICATIONS : reviews
    CANDIDATES ||--o{ APPLICATIONS : submits
    JOBS ||--o{ APPLICATIONS : receives

    RECRUITERS {
        uuid id PK
        string email UK
        string name
        timestamp created_at
        timestamp updated_at
    }

    CANDIDATES {
        uuid id PK
        string email UK
        string name
        jsonb resume_data
        timestamp created_at
        timestamp updated_at
    }

    JOBS {
        uuid id PK
        uuid recruiter_id FK
        string title
        text description
        jsonb description_breakdown
        jsonb required_skills
        string status
        timestamp created_at
        timestamp updated_at
    }

    APPLICATIONS {
        uuid id PK
        uuid job_id FK
        uuid candidate_id FK
        uuid recruiter_id FK
        string status
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }
```

## Migration Lifecycle

```mermaid
flowchart LR
    models[SQLAlchemy models.py]
    revision[alembic revision --autogenerate]
    migration[Migration file in backend/migrations/versions]
    upgrade[alembic upgrade head]
    schema[(PostgreSQL schema)]

    models --> revision --> migration --> upgrade --> schema
```

## Tables

### recruiters

- Purpose: recruiters who create jobs and review applications.
- Key constraints: unique email, UUID primary key.
- Relationships: one recruiter can own many jobs and review many applications.

### candidates

- Purpose: job seekers and their parsed profile data.
- Key constraints: unique email, UUID primary key.
- Flexible field: `resume_data` JSONB for parsed resume content.

### jobs

- Purpose: job postings and publishing state.
- Key constraints: recruiter foreign key, indexed recruiter lookup.
- Flexible fields: `description_breakdown` JSONB and `required_skills` JSONB.
- Status lifecycle: `draft`, `publishing`, `published`, `closed`.

### applications

- Purpose: a candidate’s application to a job.
- Key constraints: foreign keys to jobs, candidates, and optional reviewer recruiter.
- Duplicate protection: unique constraint on `(job_id, candidate_id)`.
- Flexible field: `metadata` JSONB for scores, notes, and workflow outputs.

## Constraint Summary

| Table        | Constraint                          | Reason                               |
| ------------ | ----------------------------------- | ------------------------------------ |
| recruiters   | unique(email)                       | Prevent duplicate recruiter accounts |
| candidates   | unique(email)                       | Prevent duplicate candidate accounts |
| jobs         | foreign key to recruiters           | Enforce job ownership                |
| applications | foreign keys to jobs and candidates | Enforce valid applications           |
| applications | unique(job_id, candidate_id)        | Prevent duplicate submissions        |

## Cascade Behavior

| Foreign Key               | Delete Rule | Why                                                 |
| ------------------------- | ----------- | --------------------------------------------------- |
| jobs.recruiter_id         | RESTRICT    | Do not delete recruiters with owned jobs            |
| applications.job_id       | CASCADE     | Remove applications when a job is removed           |
| applications.candidate_id | CASCADE     | Remove applications when a candidate is removed     |
| applications.recruiter_id | SET NULL    | Preserve application history if reviewer is removed |

## JSONB Usage

Use JSONB for:

- parsed resume content
- structured job description breakdowns
- application scoring metadata and notes

Do not use JSONB for:

- primary identifiers
- core relations
- frequently filtered scalar fields that need dedicated indexes

## Migration Commands

```bash
cd backend
alembic upgrade head
alembic current
alembic history --verbose
alembic revision --autogenerate -m "describe schema change"
```

## Related Documentation

- [Architecture](ARCHITECTURE.md)
- [Setup Guide](SETUP.md)
