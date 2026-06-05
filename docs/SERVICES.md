# Services: Business Logic Layer

## Overview

Services own business behavior. Routers should stay thin, repositories should stay data-focused, and services should coordinate validation, persistence, workflows, and events.

## Service Interaction Diagram

```mermaid
flowchart LR
    router[FastAPI Router]
    service[Service]
    repo[Repository]
    db[(PostgreSQL)]
    workflow[Temporal]
    events[Kafka]

    router --> service
    service --> repo
    repo --> db
    service --> workflow
    service --> events
```

## Core Service Responsibilities

### RecruiterService

- Create and fetch recruiter profiles.
- Enforce unique recruiter identity rules before persistence.

### CandidateService

- Create and fetch candidate records.
- Update and delete the authenticated candidate's own profile.
- Prevent duplicate candidate emails during create and update flows.
- Keep candidate profiles independent from application-specific resume variants.

### JobService

- Create draft jobs (status always `draft`, recruiter_id from auth context)
- Accept manual description content as a fallback while PDF parsing is pending
- Accept optional structured metadata overrides for employment type, seniority, location, compensation, experience, and deadlines
- Upload recruiter-provided JD PDFs and persist parsing lifecycle metadata
- Update jobs (PATCH) with authorization checks (only job owner can update)
- Delete jobs (only job owner can delete)
- Enforce recruiter ownership and status transition rules
- Support JD parsing lifecycle and normalize parsed metadata into first-class job columns

### ApplicationService

- Bind application creation to authenticated candidate (from X-User-ID header)
- Validate job exists and is in `ready` status
- Use `EligibilityService` to enforce a minimum skills match before application creation
- Prevent duplicate applications (unique constraint on job_id, candidate_id)
- Create application records with server-set candidate_id
- Require candidate-owned resume upload before final submission
- Submit candidate applications explicitly through a dedicated endpoint
- Resolve recruiter access through the job owner relationship instead of storing a duplicate recruiter FK on applications
- Handle resume uploads with file-size and content-type validation
- Authorize access: candidates see only their own apps, recruiters see apps for their jobs
- Initialize application workflow metadata and start the Temporal workflow only after submit
- Single unified workflow handles both application initialization and resume parsing (if resume exists at submit time)

### AnalyticsService

- Serve the analytics API through query-backed reads.
- Aggregate the required metrics directly from transactional tables.
- Count durable failure signals from job workflows, application workflows, event-processing records, and outbox publishing records.
- Keep reporting read-only; do not introduce a separate analytics store or projection pipeline.

### EligibilityService

- Confirms that the target job exists and is in `ready` status.
- Rejects duplicate applications before create.
- Evaluates candidate eligibility based on resume parsing at scoring time.
- Application scoring uses resume skills only (parsed from the uploaded resume file).
- Applications with resume match score ≤ 0.5 are automatically rejected; scores > 0.5 proceed to screening.

## Event and Worker Responsibilities

- `JobService` and `ApplicationService` persist their state changes before writing transactional outbox records.
- The outbox relay publishes durable domain events without coupling API success to Kafka availability.
- Kafka consumers stay thin and dispatch idempotent Celery tasks for analytics, notifications, and scoring.
- `AnalyticsService` exposes the reporting surface after those durable writes and task outcomes are persisted.

## Job Creation Flow

```mermaid
sequenceDiagram
    participant Client
    participant Router
    participant Service as JobService
    participant Repo as JobRepository
    participant DB as PostgreSQL
    participant ClientFallback as Recruiter Fallback

    Client->>Router: POST /jobs
    Router->>Service: create_job(payload)
    Service->>Repo: create(job)
    Repo->>DB: INSERT job
    DB-->>Repo: job row
    Repo-->>Service: job row
    Service-->>Router: response model
    Router-->>Client: 201 Created

    ClientFallback->>Router: PATCH /jobs/{id} {description=...}
    Router->>Service: update_job(job_id, payload, current_user)
    Service->>Service: mark source_type=manual_text, parsing_status=parsed
    Service->>Service: derive normalized job metadata and breakdown
    Service->>Repo: update(job_id, updates)
    Repo->>DB: UPDATE jobs
    Router-->>ClientFallback: 200 OK
```

## Job Description Upload Flow

```mermaid
sequenceDiagram
    participant Client
    participant Router as Router<br/>(File Size Limit)
    participant Service as JobService
    participant Repo as JobRepository
    participant Disk as Local Storage
    participant DB as PostgreSQL
    Client->>Router: POST /jobs/{id}/description-file (multipart/form-data)
    Router->>Router: Stream & check file size vs MAX_JD_SIZE_BYTES
    Router->>Service: upload_job_description(job_id, file_bytes, current_user)
    Service->>Service: Verify recruiter owns the draft job
    Service->>Service: Validate content-type (PDF only)
    Service->>Disk: write file to uploads/job_descriptions/{job_id}.pdf
    Service->>Repo: attach_job_description_file(...)
    Repo->>DB: UPDATE jobs (jd_file_name, jd_parsing_status='pending', clear parsed fields, ...)
    Service-->>Router: job response (NO jd_storage_path)
    Router-->>Client: 202 Accepted
```

## Job Publishing Workflow

```mermaid
sequenceDiagram
    participant Client
    participant Router
    participant Service as JobService
    participant Temporal as Temporal Workflow
    participant Activity as Breakdown Activity
    participant Repo as JobRepository
    participant DB as PostgreSQL

    Client->>Router: POST /jobs/{id}/publish
    Router->>Service: publish_job(job_id, current_user)
    Service->>Service: verify owner and publishable state
    Service->>Repo: update(job_id, {status='processing'})
    Service->>Temporal: start JobPublishingWorkflow
    Temporal->>Activity: finalize_job_breakdown(job_id)
    Activity->>Repo: persist description, breakdown, required_skills, and structured metadata
    Activity->>Repo: update(job_id, {status='ready'})
    Router-->>Client: 202 Accepted
```

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> processing: POST /jobs/{id}/publish
    processing --> ready: finalize_job_breakdown + mark_job_ready
    ready --> archived: future lifecycle transition
```

## Application Submission Flow

```mermaid
sequenceDiagram
    participant Client
    participant Router
    participant Service as ApplicationService
    participant JobRepo
    participant CandidateRepo
    participant AppRepo
    participant DB as PostgreSQL
    participant Temporal

    Client->>Router: POST /applications (with X-User-ID header)
    Router->>Service: apply_to_job(payload, current_user)
    Service->>Service: Extract candidate_id from X-User-ID
    Service->>JobRepo: get_by_id(job_id)
    JobRepo->>DB: SELECT job
    Service->>Service: Verify job.status == 'ready'
    Service->>CandidateRepo: get_by_id(candidate_id)
    CandidateRepo->>DB: SELECT candidate
    Service->>Service: check eligibility result and required skill overlap
    Service->>AppRepo: check for duplicate (job_id, candidate_id)
    Service->>AppRepo: create(application, candidate_id=extracted_id)
    AppRepo->>DB: INSERT application (if unique constraint passes)
    DB-->>AppRepo: application row
    Service-->>Router: response model
    Router-->>Client: 201 Created

    Client->>Router: POST /applications/{id}/submit
    Router->>Service: submit_application(application_id, current_user)
    Service->>Service: verify ownership + resume attached
    Service->>Temporal: start workflow
    Service-->>Router: submit response with workflow id
    Router-->>Client: 202 Accepted
```

**Key changes:**

- `candidate_id` comes from auth context (`X-User-ID`), not request body
- Job must be `ready` before allowing applications
- Database unique constraint `(job_id, candidate_id)` prevents duplicates at DB level
- Resume upload and submission are separated: candidates prepare data first, then explicitly submit
- Recruiters can move application status only after the candidate has submitted the application

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> screening
    pending --> rejected
    screening --> interview
    screening --> rejected
    interview --> offer
    interview --> rejected
    offer --> accepted
    offer --> rejected
```

## Resume Upload Flow

```mermaid
sequenceDiagram
    participant Client
    participant Router as Router<br/>(File Size Limit)
    participant Service as ApplicationService
    participant AppRepo
    participant ResumeRepo
    participant Disk as Local Storage
    participant DB as PostgreSQL

    Client->>Router: POST /applications/{id}/resume (multipart/form-data)
    Router->>Router: Stream & check file size vs MAX_RESUME_SIZE_BYTES
    Router->>Service: upload_resume(application_id, file_bytes, current_user)
    Service->>Service: Verify candidate_id from X-User-ID matches app.candidate_id
    Service->>AppRepo: get_by_id(application_id)
    AppRepo->>DB: SELECT application
    Service->>Service: Validate content-type (PDF/DOC/DOCX only)
    Service->>Disk: write file to uploads/resumes/{resume_id}{ext}
    Service->>ResumeRepo: create candidate resume snapshot
    ResumeRepo->>DB: INSERT candidate_resumes row
    Service->>AppRepo: attach application to resume snapshot
    AppRepo->>DB: UPDATE application (resume_id + workflow metadata)
    DB-->>AppRepo: updated application row
    Service-->>Router: application response with nested resume object (NO storage_path)
    Router-->>Client: 200 OK
```

**Key changes:**

- Router pre-checks file size before streaming to service (prevents OOM)
- Service verifies the authenticated candidate owns the application
- Parsed resume content and file metadata live on the candidate resume snapshot, not on the application row
- Internal `storage_path` is **not** included in API response

## Service Design Rules

1. **Raise domain exceptions, not HTTP exceptions.** Services should raise `NotFoundError`, `ForbiddenError`, `BadRequestError`, `ConflictError` from `app.services.exceptions`. Routers and FastAPI exception handlers convert these to HTTP responses (404, 403, 400, 409, etc.). This decouples services from HTTP and enables them to be called from workflows, background tasks, or other non-HTTP contexts.

2. **Bind ownership to auth context, not request bodies.** When creating jobs, use `current_user.id` (X-User-ID header) as the recruiter; similarly bind candidate applications to the authenticated candidate's UUID. This prevents authorization bypasses.

3. **Enforce server-controlled status transitions.** Job `status` is never accepted from the request body on creation; it always defaults to `draft`. Publishing happens through `POST /jobs/{id}/publish`, and subsequent transitions follow the explicit state machine.

4. **Keep JD parsing lifecycle separate from publication lifecycle.** `jd_parsing_status` tracks content-ingestion progress, while `status` tracks recruiter-facing publication state. Services should not overload one field to represent both concerns.

5. **Validate eligibility early.** Before creating an application, check that the job exists, is in `ready` status, and that no duplicate application exists. Prevent applications to draft/processing/archived jobs.

6. **Keep SQL construction in repositories, pagination in the database.** Repositories should compose `.limit()` and `.offset()` into queries, not return all records for Python-level slicing.

7. **Use services for orchestration and business decisions.** Return schema-friendly domain objects or response models. Prefer database constraints for hard integrity rules (unique constraints, foreign keys) and service validation for policy rules (authorization, status checks).

## Error Handling

Services raise domain exceptions from `app.services.exceptions`:

| Exception              | HTTP Code | Scenario                                              |
| ---------------------- | --------- | ----------------------------------------------------- |
| `BadRequestError`      | 400       | Invalid input, missing required fields, wrong status  |
| `ForbiddenError`       | 403       | Authorization denied (wrong role, not resource owner) |
| `NotFoundError`        | 404       | Resource doesn't exist                                |
| `ConflictError`        | 409       | Duplicate application, duplicate email                |
| `PayloadTooLargeError` | 413       | Resume or JD file exceeds max size                    |

**Conversion pattern:**

Routers and the FastAPI exception handlers in `app.main` convert these to JSON responses:

```python
@app.exception_handler(ForbiddenError)
async def handle_forbidden(_: object, exc: ForbiddenError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})
```

## Related Documentation

- [Architecture](ARCHITECTURE.md)
- [Database Design](DATABASE.md)
- [Setup Guide](SETUP.md)
