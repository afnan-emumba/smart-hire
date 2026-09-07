# Architecture: SmartHire System Design

## System Overview

SmartHire is a microservices platform: five independent async-first FastAPI services, each with its own PostgreSQL database, sitting behind a single nginx API gateway. Clear layer boundaries (HTTP handling → business logic → persistence) are enforced _within_ each service; boundaries _between_ services are enforced over HTTP, never by sharing a database or ORM session. New human-identity types (recruiters, candidates, and future types such as Admin or Employer) are added inside the consolidated **user-service** as additional tables/routers/services — not as new microservices.

## System Context

```mermaid
flowchart TD
    user[Recruiters and Candidates]
    gateway[nginx Gateway<br/>/api/v1/*]

    subgraph Services
        userSvc[user-service]
        jobSvc[job-service]
        resumeSvc[resume-service]
        applicationSvc[application-service]
        notificationSvc[notification-service<br/>Week 3 stub]
    end

    subgraph Workers
        jobWorker[job-service-worker<br/>job-publishing + job-deletion]
        resumeWorker[resume-service-worker]
        userWorker[user-service-worker<br/>user-deletion]
        notificationWorker[notification-service-worker<br/>notification-delivery]
    end

    temporal[Temporal Server]
    postgres[(PostgreSQL<br/>5 logical databases)]

    user --> gateway
    gateway --> userSvc
    gateway --> jobSvc
    gateway --> resumeSvc
    gateway --> applicationSvc
    gateway --> notificationSvc

    applicationSvc -.HTTP.-> jobSvc
    applicationSvc -.HTTP.-> userSvc
    applicationSvc -.HTTP.-> resumeSvc

    userSvc --> postgres
    jobSvc --> postgres
    resumeSvc --> postgres
    applicationSvc --> postgres
    notificationSvc --> postgres

    userSvc --> temporal
    jobSvc --> temporal
    resumeSvc --> temporal
    applicationSvc --> temporal
    temporal --> jobWorker
    temporal --> resumeWorker
    temporal --> userWorker
    temporal --> notificationWorker
    jobWorker --> postgres
    resumeWorker --> postgres
    userWorker --> postgres
    notificationWorker --> postgres

    userWorker -.HTTP.-> resumeSvc
    userWorker -.HTTP.-> applicationSvc
    userWorker -.HTTP.-> jobSvc
    jobWorker -.HTTP.-> applicationSvc
```

`application-service` connects to Temporal as a **client only** — it starts `NotificationDeliveryWorkflow` by name on notification-service's task queue and hosts no workflows itself.

`user-service-worker` reaches job-service two ways: an activity lists a recruiter's jobs over HTTP, then the workflow spawns child `JobDeletionWorkflow` executions directly onto job-service's `job-deletion` task queue. The task queue is a deliberate second integration surface alongside HTTP — the workflow name and queue live in `contracts/temporal.py` so the dependency is declared rather than re-typed as string literals.

Kafka, Celery/RabbitMQ, Redis, and the Prometheus/Grafana/Jaeger/OpenTelemetry observability stack are Part A's Week 3 scope (event-driven processing + observability) and are **not yet implemented**. See [PRD](PRD.md) for the full timeline.

## Layered Application Design (per service)

```mermaid
flowchart TB
    subgraph Presentation
        postman[Postman<br/>via gateway]
    end

    subgraph API["services/&lt;name&gt;/app/api/"]
        routers[Routers<br/>Validation and HTTP responses]
        auth[Shared Mock Auth<br/>X-User-ID, X-User-Role]
    end

    subgraph Domain["services/&lt;name&gt;/app/services/"]
        svc[Service<br/>business rules + orchestration]
        clients[HTTP Clients<br/>all but notification]
    end

    subgraph DataAccess["services/&lt;name&gt;/app/repositories/"]
        repo[Repository]
    end

    subgraph Infrastructure
        db[(This service's own<br/>logical PostgreSQL database)]
        workflow[Temporal<br/>every service has a client;<br/>job, resume, user, notification also run workers]
        other[Other services'<br/>gateway-routed endpoints]
    end

    postman --> routers
    routers --> auth
    routers --> svc
    svc --> repo
    repo --> db
    svc --> workflow
    svc -.application-service.-> clients
    clients -.HTTP.-> other
```

Every service repeats this same internal shape. The only structural difference between services is which of the optional pieces they use: `job/`, `resume/`, `user/`, and `notification/` add a full `app/temporal/` package (workflows, activities, worker entrypoint); `application/` has an `app/temporal/` with a client and DTOs but no worker, since it only *starts* workflows others own; `user/`, `job/`, and `application/` all use `app/clients/` for cross-service HTTP instead of any shared repository access.

## Core Components

### API Layer

- Location: `services/<name>/app/api/`
- Responsibility: request parsing, schema validation, dependency injection, response formatting
- Style: fully async FastAPI handlers
- Error handling: catches domain exceptions from services and converts to HTTP responses via centralized exception handlers
- **Auth scoping:** Guards endpoints with `require_role()` dependency; only authenticated users of the correct role can proceed
- **Gateway:** nginx (`infra/nginx/nginx.conf`) is the intended API entrypoint for real traffic, routing `/api/v1/<resource>/*` to the owning service's internal port. Each service additionally publishes its own host port (8001, 8003-8006) as a local-dev convenience for direct Swagger access — not something a real client should call.

### Services Layer

- Location: `services/<name>/app/services/`
- Responsibility: business rules, orchestration, workflow triggers
- Principle: services own behavior, repositories own queries
- **Exception pattern:** Services raise domain exceptions (`NotFoundError`, `ForbiddenError`, `BadRequestError`, `ConflictError`, `PayloadTooLargeError`, `ServiceUnavailableError`) from the shared `exceptions.http_exceptions` module, **not** `HTTPException`. This decouples services from HTTP and allows them to be called from workflows, background tasks, or other contexts.
- **Auth binding:** Services extract ownership IDs from `current_user` context (X-User-ID header), not from request bodies. Prevents authorization bypasses.
- **Cross-service calls:** no service has direct DB access to another service's tables — cross-service reads/writes go over HTTP via each service's own `app/clients/`, never a join across databases. application-service calls job-service, user-service, and resume-service (to validate jobs/candidates and cascade-delete on job/candidate removal); job-service calls user-service and application-service; user-service calls resume-service and application-service (to cascade-delete a candidate's resumes/applications on candidate deletion); resume-service calls user-service. Only `notification-service` makes no outbound service calls.

### Repository Layer

- Location: `services/<name>/app/repositories/`
- Responsibility: CRUD and query composition with SQLAlchemy 2.0 async APIs
- **Database-level pagination:** List methods accept `limit` and `offset` parameters and apply them in SQL queries, not Python
- **Database-level filtering:** Status filters, recruiter filters, etc. are applied in SQL WHERE clauses
- **Service-scoped database:** each service owns one logical Postgres database (see [Database Design](DATABASE.md)) — there are no cross-service foreign keys

### Persistence Layer

- Primary store: one shared PostgreSQL container, five logical databases — `user_db`, `job_db`, `resume_db`, `application_db`, `notification_db` (`infra/postgres/init.sql`)
- **Flexible fields:** JSONB for candidate master profiles, candidate resume parsing output, parsed job content, and application eligibility results
- **Schema control:** each service has its own Alembic migration history under `services/<name>/migrations/`
- **Transaction management:** Session commit/rollback is handled by each service's `get_db_session()` dependency. Repositories use `flush()` to get IDs without committing; the session commits only after the route handler completes successfully.
- **Resume storage:** Resume files and parsed output live entirely in resume-service's `candidate_resumes` table, independent of any application; internal `storage_path` is stored for internal use only and never exposed in API responses
- **JD storage:** Internal `jd_storage_path` is stored in job-service's database for internal use only; API responses **do not** include this path

### Manual Validation Surface

- The Postman collection (`postman/SmartHire.postman_collection.json`), driven entirely through the nginx gateway, is the primary validation surface.
- Each service exposes its own Swagger UI/ReDoc (`docs_url="/docs"`), reachable directly on its host port (user 8001, job 8003, resume 8004, application 8005, notification 8006) for interactive schema inspection — nginx doesn't proxy `/docs`, so it isn't reachable through the gateway itself.
- Resume files are uploaded independently of any application (`POST /resumes`) and stored on resume-service's local disk in development.
- Job description PDFs are uploaded per job and processed through the Temporal `JobPublishingWorkflow` when the job is published.

### Async Processing

- **Temporal** (implemented). Six workflows across four task queues:

| Workflow | Worker (task queue) | Purpose |
|---|---|---|
| `JobPublishingWorkflow` | job-service-worker (`job-publishing`) | Finalize the description breakdown, mark the job `ready` |
| `JobDeletionWorkflow` | job-service-worker (`job-deletion`) | Applications → JD file → job row |
| `ResumeParsingWorkflow` | resume-service-worker (`resume-parsing`) | Convert an uploaded resume to markdown, extract structured data |
| `CandidateDeletionWorkflow` | user-service-worker (`user-deletion`) | Resumes ∥ applications, then the candidate row |
| `RecruiterDeletionWorkflow` | user-service-worker (`user-deletion`) | Fan out child `JobDeletionWorkflow` per job, then the recruiter row |
| `NotificationDeliveryWorkflow` | notification-service-worker (`notification-delivery`) | Record the notification, then retry delivery for up to 24h |

  The publishing and parsing workflows use bounded retries (3 and 5 attempts). The delete cascades and notification delivery use **unbounded** retries capped only by the workflow execution timeout — a downstream service being down is an expected condition, not a failure. job-service-worker serves two task queues from one process via `asyncio.gather` over two `Worker` instances.

- **Kafka, Celery** (Week 3, not yet implemented): planned for domain events (`JobPublished`, `ApplicationReceived`) and isolated background work (analytics, scoring). A transactional outbox belongs with that work — today the delete endpoints and the notification trigger both commit and *then* start a workflow, a dual-write gap where a crash in between strands the record.

## Job Publishing Flow

```mermaid
sequenceDiagram
    participant Recruiter
    participant Gateway as nginx
    participant API as job-service Router
    participant Service as JobService
    participant Repo as JobRepository
    participant DB as job_db
    participant Worker as job-service-worker<br/>(JobPublishingWorkflow)

    Recruiter->>Gateway: POST /api/v1/jobs (X-User-ID, X-User-Role=RECRUITER)
    Gateway->>API: proxy to job-service
    API->>Service: create_job(payload, current_user)
    Service->>Service: Extract recruiter_id from X-User-ID
    Service->>Repo: create(job_data, recruiter_id=extracted_id)
    Repo->>DB: INSERT jobs(recruiter_id, status='draft', ...)
    DB-->>Repo: job row
    Repo-->>Service: job
    Service-->>API: job response (status='draft')
    API-->>Recruiter: 201 Created

    Recruiter->>Gateway: POST /api/v1/jobs/{id}/description-file (multipart/form-data)
    Gateway->>API: proxy to job-service
    API->>Service: upload_job_description(job_id, file_bytes, current_user)
    Service->>Service: verify owner, draft status, and PDF content type
    Service->>Repo: attach_job_description_file(...)
    Repo->>DB: UPDATE jobs SET jd_parsing_status='pending', jd_source_type='pdf_upload'
    Service-->>API: job response (jd_parsing_status='pending')
    API-->>Recruiter: 202 Accepted

    Recruiter->>Gateway: POST /api/v1/jobs/{id}/publish
    Gateway->>API: proxy to job-service
    API->>Service: publish_job(job_id, current_user)
    Service->>Service: Verify current_user.role=RECRUITER, owns the job, and source content is publishable
    Service->>Repo: update(job_id, {status='processing'})
    Service->>Worker: start_workflow(JobPublishingWorkflow)
    Service-->>API: publish response {workflow_id, status='processing'}
    API-->>Recruiter: 202 Accepted

    Note over Worker: async — decoupled from the request/response cycle
    Worker->>Repo: finalize_job_breakdown activity persists breakdown
    Worker->>Repo: mark_job_ready activity sets status='ready'
```

**Key points:**

- `recruiter_id` is bound to `X-User-ID` on creation; clients cannot override it
- `status` defaults to `draft` and cannot be set in the create request
- JD ingestion is a separate upload operation that tracks parsing state independently from publication state
- Publishing is a separate `POST /jobs/{id}/publish` operation with authorization scoping; the actual breakdown work happens asynchronously in job-service-worker, not on the request thread
- The publish workflow persists normalized metadata into top-level job fields and a richer `description_breakdown` JSONB payload

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> processing: publish requested
    processing --> ready: workflow completed
    ready --> archived: future lifecycle transition
```

## Application Submission Flow

```mermaid
sequenceDiagram
    participant Candidate
    participant Gateway as nginx
    participant API as application-service Router
    participant Service as ApplicationService
    participant Eligibility as EligibilityService
    participant JobSvc as job-service (HTTP)
    participant CandidateSvc as user-service (HTTP)
    participant ResumeSvc as resume-service (HTTP)
    participant AppRepo as ApplicationRepository
    participant DB as application_db

    Candidate->>Gateway: POST /api/v1/applications (X-User-ID, X-User-Role=CANDIDATE)
    Gateway->>API: proxy to application-service
    API->>Service: apply_to_job(payload, current_user)
    Service->>Service: Extract candidate_id from X-User-ID
    Service->>Eligibility: check_eligibility(candidate_id, job_id, current_user)
    Eligibility->>JobSvc: GET /jobs/{job_id} (verify status='ready')
    Eligibility->>AppRepo: check duplicate + active-application count
    Eligibility->>CandidateSvc: GET /candidates/{candidate_id} (skills)
    Eligibility->>ResumeSvc: GET latest parsed resume (fallback if profile has no skills)
    Eligibility->>Eligibility: compare skills vs job.required_skills (>=50% match)
    Eligibility-->>Service: EligibilityResult
    Service->>AppRepo: create(application, eligibility_result, resume_id)
    AppRepo->>DB: INSERT application (unique constraint on job_id+candidate_id)
    DB-->>AppRepo: application row
    Service-->>API: application response
    API-->>Candidate: 201 Created
```

**Key points:**

- `candidate_id` is bound to `X-User-ID`; clients cannot override it
- Job must be in `ready` status; applications to draft/processing/archived jobs are rejected
- Unique constraint `(job_id, candidate_id)` prevents duplicates at DB level
- Duplicate applications return `409 Conflict`
- Resume upload (`POST /resumes`, handled entirely by resume-service) is independent of application submission — a candidate can upload one before ever applying, and it's only linked by `resume_id` if the eligibility check needed to fall back to it

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

## Deployment View

```mermaid
flowchart LR
    subgraph Local Development
        compose[Docker Compose]
        nginxLocal[nginx Gateway Container]
        serviceContainers[5 Service Containers<br/>+ 4 Temporal Workers]
        localDb[(PostgreSQL Container<br/>5 logical DBs)]
        localTemporal[Temporal + Temporal UI Containers]
    end

    subgraph Production Target
        ingress[Ingress / Load Balancer]
        gatewayPods[API Gateway Pods]
        servicePods[Per-Service Pods<br/>independently scalable]
        managedDb[(Managed PostgreSQL<br/>one instance per service, or shared with strict schema isolation)]
        temporalCluster[Temporal Cluster]
        kafkaCluster[Kafka Cluster - Week 3]
        workerPool[Celery Worker Pool - Week 3]
        observability[Metrics and Tracing - Week 3]
    end

    compose --> nginxLocal
    compose --> serviceContainers
    compose --> localDb
    compose --> localTemporal
    ingress --> gatewayPods
    gatewayPods --> servicePods
    servicePods --> managedDb
    servicePods --> temporalCluster
    servicePods --> kafkaCluster
    kafkaCluster --> workerPool
    servicePods --> observability
    workerPool --> observability
```

## Design Principles

1. Async first across API, database access, and workflow integration.
2. Separation of concerns between routers, services, repositories, and infrastructure clients — enforced _within_ each service.
3. Separation of concerns _between_ services via HTTP only — no shared database, no cross-service ORM joins, no shared session.
4. Separate JD content-ingestion state from recruiter-visible publication state so future workflows can evolve independently.
5. Strong relational integrity within a service's own database, with JSONB only where schema flexibility is useful; cross-service references are validated at write-time via HTTP, not DB constraints.
6. Event-driven side effects (Week 3) so slow or bursty work stays off the request path.
7. Observability (Week 3) across request handling, workflow execution, and background workers.

## Related Documentation

- [Database Design](DATABASE.md)
- [Service Layer](SERVICES.md)
- [Setup Guide](SETUP.md)
