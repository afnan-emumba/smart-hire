# Product Requirements Document: SmartHire Part A

## Overview

SmartHire Part A defines the core recruitment platform for TalentSphere Inc. The focus is a scalable backend system for recruiter operations, candidate applications, workflow orchestration, and reliable asynchronous processing. This phase intentionally excludes GenAI features and instead establishes the operational backbone required for future intelligence capabilities.

## Problem Statement

TalentSphere's existing hiring operations are slowed by manual job publishing, inconsistent candidate processing, fragmented workflow state, and unreliable background execution during high-volume hiring periods. SmartHire Part A addresses these constraints by centralizing recruitment data, formalizing workflow boundaries, and introducing event-driven processing with observability.

## Goals

- Provide durable job, candidate, recruiter, and application management APIs.
- Automate job publishing and candidate application workflows with clear state transitions.
- Support high-volume hiring campaigns without sacrificing consistency.
- Isolate background processing from synchronous API operations.
- Establish observability and failure recovery patterns for workflows and workers.

## Key Use Cases

### Recruiter Use Cases

- Create and manage recruiter profiles.
- Create draft job postings with descriptions, skills, and hiring metadata.
- Publish or update jobs through a controlled workflow.
- Retrieve and review applications associated with jobs.

### Candidate Use Cases

- Register and maintain candidate profiles.
- Browse and retrieve ready jobs.
- Submit applications to eligible jobs.
- Upload a resume independently of any specific application; it is evaluated against future applications by reference (`resume_id`).
- Track application status through the hiring lifecycle.

### Platform Use Cases

- Trigger job publishing workflow steps after recruiter actions.
- Prevent duplicate applications for the same candidate and job.
- Emit domain events after successful persistence.
- Run background tasks for analytics, notifications, and scoring.
- Expose health and observability surfaces for operations teams.

## Functional Requirements

### Recruiter and Candidate Management

- FR-01: The system shall allow recruiter profile creation and retrieval.
- FR-02: The system shall allow candidate profile creation, retrieval, and listing.
- FR-03: The system shall validate request payloads and reject malformed data.

### Job Management

- FR-04: The system shall allow authenticated recruiters to create job postings.
- FR-05: The system shall bind job ownership to the authenticated recruiter identity.
- FR-06: The system shall store job descriptions, required skills, structured breakdown data, and normalized job metadata for filtering and matching.
- FR-07: The system shall support job listing and retrieval with filtering and pagination.
- FR-08: The system shall manage job status transitions such as `draft`, `processing`, `ready`, and `archived`.

### Application Management

- FR-09: The system shall allow authenticated candidates to submit applications to jobs.
- FR-10: The system shall bind application ownership to the authenticated candidate identity.
- FR-11: The system shall prevent duplicate applications for the same candidate and job.
- FR-12: The system shall reject applications to ineligible or unavailable jobs.
- FR-13: The system shall support application retrieval and listing with filters and pagination.
- FR-14: The system shall allow a candidate to upload a resume file independently of any application; applications reference the resume evaluated for eligibility by ID.
- FR-15: The system shall store application metadata required for downstream scoring and review.

### Workflow and Event Processing

- FR-16: The system shall trigger a job publishing workflow after `POST /jobs/{id}/publish` or relevant draft updates.
- FR-17: The system shall break down job descriptions into structured data for downstream retrieval and ranking.
- FR-18: The system shall trigger an application workflow after a candidate submits an application.
- FR-19: The system shall emit domain events after successful writes for jobs and applications.
- FR-20: The system shall support isolated background tasks for notifications, analytics updates, and candidate scoring.
- FR-21: The system shall preserve workflow state and application history through partial failures.

### Platform Operations

- FR-22: The system shall expose a health endpoint that verifies application and database readiness.
- FR-23: The system shall expose API documentation through Swagger UI and ReDoc.
- FR-24: The system shall maintain a Postman collection aligned with implemented routes.

## Non-Functional Requirements

- NFR-01: All network and database I/O shall use async execution patterns.
- NFR-02: Core domain data shall be stored durably in PostgreSQL with referential integrity.
- NFR-03: Flexible recruitment data such as parsed descriptions, resume output, and scores shall use JSONB where appropriate.
- NFR-04: Synchronous API requests shall remain decoupled from long-running or retryable background work.
- NFR-05: The platform shall tolerate high application volumes during hiring spikes without double-processing requests.
- NFR-06: The system shall enforce idempotency and duplicate protection for candidate applications.
- NFR-07: The system shall support traceability through logs, metrics, and distributed traces.
- NFR-08: Failures in background tasks or workflows shall not corrupt persisted core entities.
- NFR-09: Configuration shall be environment-driven, with no hardcoded secrets or environment-specific credentials in tracked files.
- NFR-10: The codebase shall preserve separation of concerns across routers, services, and repositories.
- NFR-11: Public APIs shall remain manually verifiable through Swagger UI, ReDoc, and Postman.
- NFR-12: Development and local deployment shall be reproducible through Docker and Docker Compose.

## Scope Boundaries

### In Scope for Part A

- Recruiter, candidate, job, and application domain models.
- CRUD-style API operations for the core recruitment flow.
- Job publishing and application workflow orchestration.
- Event-driven processing for post-persistence actions.
- Basic observability and system health coverage.

### Out of Scope for Part A

- Semantic search, embeddings, and vector retrieval.
- AI-generated recruiter or candidate assistance.
- Recommendation engines and LLM-based scoring.
- Production authentication and identity federation.

## Timeline and Milestones

### Week 1: Foundation and Core Management

- Application scaffold, settings, and database connectivity.
- Core schema, migrations, repositories, services, and routers.
- Baseline CRUD APIs for recruiters, candidates, jobs, and applications.
- Manual validation surface through Swagger and Postman.

### Week 2: Application Workflow and Publishing Pipeline

- Candidate application rules, duplicate handling, and eligibility checks.
- Job publishing workflow with controlled state transitions.
- Structured job content breakdown and readiness lifecycle.

### Week 3: Event-Driven Processing and Observability

- Kafka-based job and application event flows.
- Background workers for scoring, notifications, and analytics.
- Metrics, traces, and logs for workflow and worker visibility.

## Deliverables

- Six FastAPI services (recruiter, candidate, job, resume, application, notification) behind a single nginx gateway, each with async layered architecture.
- Per-service PostgreSQL schemas and Alembic migrations (one logical database per service).
- Recruiter, candidate, job, resume, and application APIs.
- Independent resume upload support, decoupled from any specific application.
- Workflow and event integration points for publishing and applications.
- Foundational observability and local deployment setup.
- Supporting technical documentation in `docs/` and API validation assets in `postman/`.

## Traceability Matrix

| Requirement ID                                  | Requirement Summary                                                      | Primary Deliverables                                                                                |
| ----------------------------------------------- | ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| FR-01, FR-02, FR-03                             | Recruiter and candidate profile management                               | FastAPI routers, Pydantic schemas, services, repositories, PostgreSQL tables                        |
| FR-04, FR-05, FR-06, FR-07, FR-08               | Job creation, ownership, listing, and status lifecycle                   | Job API, auth-bound service logic, job repository, jobs table, publishing workflow integration      |
| FR-09, FR-10, FR-11, FR-12, FR-13, FR-14, FR-15 | Application submission, duplicate protection, listing, and resume upload | Application API, application service, duplicate checks, application repository, resume storage flow |
| FR-16, FR-17                                    | Job publishing orchestration and structured breakdown                    | Temporal workflow integration, job status transitions, structured description fields                |
| FR-18, FR-19, FR-20, FR-21                      | Application workflow, domain events, and resilient async processing      | Application workflow hooks, Kafka events, Celery workers, retry and failure isolation patterns      |
| FR-22, FR-23, FR-24                             | Operational validation surfaces                                          | Health endpoint, Swagger UI, ReDoc, Postman collection                                              |
| NFR-01, NFR-02, NFR-03, NFR-10                  | Architectural quality and data integrity                                 | Async FastAPI and SQLAlchemy design, PostgreSQL schema, JSONB usage, layered architecture docs      |
| NFR-04, NFR-05, NFR-06, NFR-08                  | Reliability under load and failure isolation                             | Event-driven design, idempotency checks, workflow boundaries, background worker isolation           |
| NFR-07                                          | Observability                                                            | Metrics, tracing, logging, observability stack integration                                          |
| NFR-09, NFR-11, NFR-12                          | Operability and developer experience                                     | Env-based config, Swagger/ReDoc/Postman validation, Docker and Compose setup                        |

## Acceptance Orientation

This PRD is satisfied when the Part A backend exposes the required domain APIs, enforces ownership and duplicate rules, persists recruitment entities consistently, supports orchestration and event-driven extensions, and documents validation and deployment paths clearly enough for local verification.
