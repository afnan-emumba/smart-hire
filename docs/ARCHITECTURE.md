# Architecture: SmartHire System Design

## System Overview

SmartHire is built as an async-first, event-driven platform with clear layer boundaries between HTTP handling, business logic, persistence, and asynchronous processing.

## System Context

```mermaid
flowchart TD
    user[Recruiters and Candidates]
    api[FastAPI API Layer]
    services[Service Layer]
    repos[Repository Layer]
    postgres[(PostgreSQL)]
    temporal[Temporal Workflows]
    kafka[Kafka Event Bus]
    celery[Celery Workers]
    redis[(Redis Cache)]
    observe[Observability Stack: Prometheus, Grafana, Jaeger, OpenTelemetry]

    user --> api
    api --> services
    services --> repos
    repos --> postgres
    services --> temporal
    services --> kafka
    kafka --> celery
    celery --> postgres
    celery --> redis
    api --> observe
    services --> observe
    temporal --> observe
    celery --> observe
```

## Layered Application Design

```mermaid
flowchart TB
    subgraph Presentation
        swagger[Swagger UI]
        postman[Postman]
    end

    subgraph API
        routers[Routers\nValidation and HTTP responses]
        auth[Mock Auth\nX-User-ID, X-User-Role]
    end

    subgraph Domain
        recruiterSvc[RecruiterService]
        candidateSvc[CandidateService]
        jobSvc[JobService]
        applicationSvc[ApplicationService]
    end

    subgraph DataAccess
        recruiterRepo[RecruiterRepository]
        candidateRepo[CandidateRepository]
        jobRepo[JobRepository]
        applicationRepo[ApplicationRepository]
    end

    subgraph Infrastructure
        db[(PostgreSQL)]
        workflow[Temporal]
        events[Kafka]
        workers[Celery and RabbitMQ]
    end

    swagger --> routers
    postman --> routers
    routers --> auth
    routers --> recruiterSvc
    routers --> candidateSvc
    routers --> jobSvc
    routers --> applicationSvc
    recruiterSvc --> recruiterRepo
    candidateSvc --> candidateRepo
    jobSvc --> jobRepo
    applicationSvc --> applicationRepo
    applicationSvc --> candidateRepo
    applicationSvc --> jobRepo
    recruiterRepo --> db
    candidateRepo --> db
    jobRepo --> db
    applicationRepo --> db
    jobSvc --> workflow
    jobSvc --> events
    applicationSvc --> workflow
    applicationSvc --> events
    events --> workers
```

## Core Components

### API Layer

- Location: `backend/app/api/`
- Responsibility: request parsing, schema validation, dependency injection, response formatting
- Style: fully async FastAPI handlers
- Error handling: catches domain exceptions from services and converts to HTTP responses via centralized exception handlers
- **Auth scoping:** Guards endpoints with `require_role()` dependency; only authenticated users of the correct role can proceed

### Services Layer

- Location: `backend/app/services/`
- Responsibility: business rules, orchestration, workflow triggers, event emission
- Principle: services own behavior, repositories own queries
- **Exception pattern:** Services raise domain exceptions (`NotFoundError`, `ForbiddenError`, `BadRequestError`, `ConflictError`, `PayloadTooLargeError`), **not** `HTTPException`. This decouples services from HTTP and allows them to be called from workflows, background tasks, or other contexts.
- **Auth binding:** Services extract ownership IDs from `current_user` context (X-User-ID header), not from request bodies. Prevents authorization bypasses.

### Repository Layer

- Location: `backend/app/repositories/`
- Responsibility: CRUD and query composition with SQLAlchemy 2.0 async APIs
- **Database-level pagination:** List methods accept `limit` and `offset` parameters and apply them in SQL queries, not Python
- **Database-level filtering:** Status filters, recruiter filters, etc. are applied in SQL WHERE clauses

### Persistence Layer

- Primary store: PostgreSQL
- **Flexible fields:** JSONB for candidate master profiles, candidate resume parsing output, parsed job content, and application metadata
- **Schema control:** Alembic migrations committed to git
- **Transaction management:** Session commit/rollback is handled by the `get_db_session()` dependency. Repositories use `flush()` to get IDs without committing; the session commits only after the route handler completes successfully.
- **Resume storage:** Resume files and parsed output live in candidate-owned resume snapshots; internal `storage_path` is stored for internal use only and API responses expose a nested resume object without that path
- **JD storage:** Internal `jd_storage_path` is stored in the database for internal use only; API responses **do not** include this path

### Manual Validation Surface

- Swagger UI and Postman are the primary clients for the current backend-only scope.
- Resume files are uploaded per application and stored locally in development.
- Job description PDFs are uploaded per job and stored locally until the Week 2 parser workflow is added.

### Async Processing

- Temporal: stateful workflows such as job publishing and application progression
- Kafka: domain events such as `JobPublished` and `ApplicationReceived`
- Celery: isolated, stateless background work such as notifications and analytics updates

## Job Publishing Flow

```mermaid
sequenceDiagram
    participant Recruiter
    participant API as FastAPI Router
    participant Service as JobService
    participant Repo as JobRepository
    participant DB as PostgreSQL
    participant Temporal as Future Temporal Workflow

    Recruiter->>API: POST /jobs (X-User-ID, X-User-Role=RECRUITER)
    API->>Service: create_job(payload, current_user)
    Service->>Service: Extract recruiter_id from X-User-ID
    Service->>Repo: create(job_data, recruiter_id=extracted_id)
    Repo->>DB: INSERT jobs(recruiter_id, status='draft', ...)
    DB-->>Repo: job row
    Repo-->>Service: job
    Service-->>API: job response (status='draft')
    API-->>Recruiter: 201 Created

    Recruiter->>API: POST /jobs/{id}/description-file (multipart/form-data)
    API->>Service: upload_job_description(job_id, file_bytes, current_user)
    Service->>Service: verify owner, draft status, and PDF content type
    Service->>Repo: attach_job_description_file(...)
    Repo->>DB: UPDATE jobs SET jd_parsing_status='pending', jd_source_type='pdf_upload'
    Service-->>API: job response (jd_parsing_status='pending')
    API-->>Recruiter: 202 Accepted

    Recruiter->>API: POST /jobs/{id}/publish
    API->>Service: publish_job(job_id, current_user)
    Service->>Service: Verify current_user.role=RECRUITER, owns the job, and source content is publishable
    Service->>Repo: update(job_id, {status='processing'})
    Service->>Temporal: start job publishing workflow
    Temporal-->>Service: workflow persists breakdown and marks job ready
    Service-->>API: publish response (status='processing')
    API-->>Recruiter: 202 Accepted
```

**Key points:**

- `recruiter_id` is bound to `X-User-ID` on creation; clients cannot override it
- `status` defaults to `draft` and cannot be set in the create request
- JD ingestion is a separate upload operation that tracks parsing state independently from publication state
- Publishing is a separate `POST /jobs/{id}/publish` operation with authorization scoping
- The publish workflow persists normalized metadata into top-level job fields and a richer `description_breakdown` JSONB payload

```mermaid
sequenceDiagram
    participant Candidate
    participant API as FastAPI Router
    participant Service as ApplicationService
    participant JobRepo as JobRepository
    participant CandidateRepo as CandidateRepository
    participant AppRepo as ApplicationRepository
    participant DB as PostgreSQL
    participant Kafka as Kafka
    participant Temporal as Temporal Workflow

    Candidate->>API: POST /applications (X-User-ID, X-User-Role=CANDIDATE)
    API->>Service: apply_to_job(payload, current_user)
    Service->>Service: Extract candidate_id from X-User-ID
    Service->>JobRepo: get_by_id(job_id)
    JobRepo->>DB: SELECT job
    Service->>Service: Verify job.status='ready'
    Service->>CandidateRepo: get_by_id(candidate_id)
    CandidateRepo->>DB: SELECT candidate
    Service->>AppRepo: get_by_job_and_candidate (check duplicate)
    Service->>AppRepo: create(job_id, candidate_id=extracted_id)
    AppRepo->>DB: INSERT application (unique constraint checked)
    DB-->>AppRepo: application row
    Service->>Kafka: emit ApplicationReceived
    Service->>Temporal: start application workflow
    Service-->>API: application response
    API-->>Candidate: 201 Created
```

**Key points:**

- `candidate_id` is bound to `X-User-ID`; clients cannot override it
- Job must be in `ready` status; applications to draft/processing/archived jobs are rejected
- Unique constraint `(job_id, candidate_id)` prevents duplicates at DB level
- Duplicate applications return `409 Conflict`

## Deployment View

```mermaid
flowchart LR
    subgraph Local Development
        compose[Docker Compose]
        localApi[FastAPI Container]
        localDb[(PostgreSQL Container)]
    end

    subgraph Production Target
        ingress[Ingress or API Gateway]
        apiPods[FastAPI Pods]
        managedDb[(Managed PostgreSQL)]
        temporalCluster[Temporal Cluster]
        kafkaCluster[Kafka Cluster]
        workerPool[Celery Worker Pool]
        observability[Metrics and Tracing]
    end

    compose --> localApi
    compose --> localDb
    ingress --> apiPods
    apiPods --> managedDb
    apiPods --> temporalCluster
    apiPods --> kafkaCluster
    kafkaCluster --> workerPool
    apiPods --> observability
    workerPool --> observability
```

## Design Principles

1. Async first across API, database access, and workflow integration.
2. Separation of concerns between routers, services, repositories, and infrastructure clients.
3. Separate JD content-ingestion state from recruiter-visible publication state so future workflows can evolve independently.
4. Strong relational integrity for core entities, with JSONB only where schema flexibility is useful.
5. Event-driven side effects so slow or bursty work stays off the request path.
6. Observability across request handling, workflow execution, and background workers.

## Related Documentation

- [Database Design](DATABASE.md)
- [Service Layer](SERVICES.md)
- [Setup Guide](SETUP.md)
