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

- Create and update candidate records.
- Coordinate resume-related enrichment work when needed.

### JobService

- Create draft jobs.
- Start publishing workflows.
- Emit job lifecycle events.
- Enforce recruiter ownership rules.

### ApplicationService

- Validate job and candidate existence.
- Prevent duplicate applications.
- Create application records.
- Start downstream scoring or notification workflows.

## Job Creation Flow

```mermaid
sequenceDiagram
    participant Client
    participant Router
    participant Service as JobService
    participant Repo as JobRepository
    participant DB as PostgreSQL
    participant Kafka

    Client->>Router: POST /jobs
    Router->>Service: create_job(payload)
    Service->>Repo: create(job)
    Repo->>DB: INSERT job
    DB-->>Repo: job row
    Repo-->>Service: job row
    Service->>Kafka: emit JobCreated
    Service-->>Router: response model
    Router-->>Client: 201 Created
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

    Client->>Router: POST /applications
    Router->>Service: apply_to_job(payload)
    Service->>JobRepo: get_by_id(job_id)
    JobRepo->>DB: SELECT job
    Service->>CandidateRepo: get_by_id(candidate_id)
    CandidateRepo->>DB: SELECT candidate
    Service->>AppRepo: create(application)
    AppRepo->>DB: INSERT application
    Service->>Temporal: start workflow
    Service-->>Router: response model
    Router-->>Client: 201 Created
```

## Service Design Rules

1. Keep HTTP-specific concerns in routers.
2. Keep SQL construction in repositories.
3. Use services for orchestration and business decisions.
4. Return schema-friendly domain objects or response models.
5. Prefer database constraints for hard integrity rules and service validation for policy rules.

## Related Documentation

- [Architecture](ARCHITECTURE.md)
- [Database Design](DATABASE.md)
- [Setup Guide](SETUP.md)
