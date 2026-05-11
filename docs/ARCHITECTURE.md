# Architecture: SmartHire System Design

## System Overview

SmartHire is built as an async-first, event-driven platform with clear layer boundaries between HTTP handling, business logic, persistence, and asynchronous processing.

## System Context

```mermaid
flowchart TD
    user[Recruiters and Candidates]
    frontend[Next.js Frontend]
    api[FastAPI API Layer]
    services[Service Layer]
    repos[Repository Layer]
    postgres[(PostgreSQL)]
    temporal[Temporal Workflows]
    kafka[Kafka Event Bus]
    celery[Celery Workers]
    redis[(Redis Cache)]
    observe[Observability Stack: Prometheus, Grafana, Jaeger, OpenTelemetry]

    user --> frontend
    user --> api
    frontend --> api
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
        web[Next.js App]
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
    web --> routers
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

### Services Layer

- Location: `backend/app/services/`
- Responsibility: business rules, orchestration, workflow triggers, event emission
- Principle: services own behavior, repositories own queries

### Repository Layer

- Location: `backend/app/repositories/`
- Responsibility: CRUD and query composition with SQLAlchemy 2.0 async APIs

### Persistence Layer

- Primary store: PostgreSQL
- Flexible fields: JSONB for resume data, parsed job content, and application metadata
- Schema control: Alembic migrations committed to git

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
    participant Temporal as Temporal Workflow
    participant Kafka as Kafka
    participant Worker as Celery Worker

    Recruiter->>API: POST /jobs
    API->>Service: create_job(payload, current_user)
    Service->>Repo: create(job)
    Repo->>DB: INSERT jobs(status=draft)
    DB-->>Repo: job row
    Repo-->>Service: job
    Service->>Temporal: start publishing workflow
    Service->>Kafka: emit JobCreated
    Service-->>API: job response
    API-->>Recruiter: 201 Created
    Temporal->>DB: update status and breakdown
    Temporal->>Kafka: emit JobPublished
    Kafka->>Worker: consume event
    Worker->>DB: persist analytics or notifications state
```

## Candidate Application Flow

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

    Candidate->>API: POST /applications
    API->>Service: apply_to_job(payload, current_user)
    Service->>JobRepo: get_by_id(job_id)
    JobRepo->>DB: SELECT job
    DB-->>JobRepo: job row
    Service->>CandidateRepo: get_by_id(candidate_id)
    CandidateRepo->>DB: SELECT candidate
    DB-->>CandidateRepo: candidate row
    Service->>AppRepo: create(application)
    AppRepo->>DB: INSERT application
    DB-->>AppRepo: application row
    Service->>Kafka: emit ApplicationReceived
    Service->>Temporal: start application workflow
    Service-->>API: application response
    API-->>Candidate: 201 Created
```

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
3. Strong relational integrity for core entities, with JSONB only where schema flexibility is useful.
4. Event-driven side effects so slow or bursty work stays off the request path.
5. Observability across request handling, workflow execution, and background workers.

## Related Documentation

- [Database Design](DATABASE.md)
- [Service Layer](SERVICES.md)
- [Setup Guide](SETUP.md)
