# SmartHire: Intelligent Workforce Orchestration & Recruitment Platform

A next-generation recruitment automation platform built for fast-scaling enterprises, staffing agencies, and global HR teams. SmartHire handles job publishing, candidate applications, workflow orchestration, and intelligent matching at scale.

## 📋 About SmartHire

SmartHire is a **recruitment automation and workflow orchestration platform** designed for enterprises and staffing agencies. It streamlines job posting, candidate applications, and hiring workflows at scale.

**Key Capabilities:**

- **Job & Candidate Management:** Full CRUD for job postings and candidate profiles
- **Application Workflow:** Track candidate applications from submission to hiring decisions
- **Async Processing:** Reliable background task execution for notifications, scoring, and analytics
- **Scalable Architecture:** Event-driven design to handle high-volume hiring campaigns
- **Foundation for AI:** Built to integrate intelligent candidate matching and recommendations as a future layer

---

## 🛠️ Technology Stack & Rationale

### **Backend**

| Tool               | Purpose             | Why                                                                                    |
| ------------------ | ------------------- | -------------------------------------------------------------------------------------- |
| **Python 3.11+**   | Core language       | Strong async ecosystem, readable, industry-standard for data apps                      |
| **FastAPI**        | REST API framework  | Async-first, automatic OpenAPI docs, dependency injection, high performance            |
| **PostgreSQL 15**  | Primary database    | ACID compliance, JSON support (JSONB), proven at scale, excellent async driver support |
| **SQLAlchemy 2.0** | ORM                 | Async support, relationship management, migration-friendly, type hints                 |
| **Alembic**        | Database migrations | Version-controlled schema changes, reversible, integration with SQLAlchemy             |
| **Pydantic v2**    | Data validation     | Type checking, serialization, OpenAPI schema generation, email validation              |

### **Background Processing**

| Tool                  | Purpose                | Why                                                                       |
| --------------------- | ---------------------- | ------------------------------------------------------------------------- |
| **Temporal**          | Workflow orchestration | Stateful long-running processes (job publishing), retry logic, visibility |
| **Kafka**             | Event streaming        | Decoupled event publishing, reliable message ordering, horizontal scaling |
| **Celery + RabbitMQ** | Async task queue       | Simple isolated background tasks (notifications), auto-retry, monitoring  |

### **Observability**

| Tool              | Purpose                  | Why                                                                            |
| ----------------- | ------------------------ | ------------------------------------------------------------------------------ |
| **Prometheus**    | Metrics collection       | Industry standard, time-series data, excellent Grafana integration             |
| **Grafana**       | Metrics visualization    | Real-time dashboards, alerting, multi-source support                           |
| **Jaeger**        | Distributed tracing      | Understand request flows, identify latency bottlenecks, microservice debugging |
| **OpenTelemetry** | Instrumentation standard | Vendor-neutral, language-agnostic, integrates with Prometheus/Jaeger           |

### **Infrastructure & Deployment**

| Tool                        | Purpose                      | Why                                                                  |
| --------------------------- | ---------------------------- | -------------------------------------------------------------------- |
| **Docker & Docker Compose** | Containerization & local dev | Reproducible environments, easy onboarding, production-ready locally |

---

## 🗂️ Key Design Decisions

### Error Handling

The backend uses **domain exceptions** (not HTTP exceptions) in services, with centralized FastAPI exception handlers converting them to HTTP responses:

- `BadRequestError` (400), `ForbiddenError` (403), `NotFoundError` (404), `ConflictError` (409), `PayloadTooLargeError` (413)
- Services raise domain exceptions; routers/handlers define HTTP semantics
- This enables services to be called from workflows, background tasks, or other contexts without HTTP coupling

### Auth-Bound Creation

- **Job creation:** `recruiter_id` is derived from `X-User-ID` header, not from request body
- **Application submission:** `candidate_id` is derived from `X-User-ID` header, not from request body
- Job `status` is server-controlled (`draft` on creation, only recruiters can transition to `published` via PATCH)
- Prevents authorization bypass where a user could create resources on behalf of someone else

### Pagination & Filtering

- All list endpoints use `limit` and `offset` query parameters
- Filtering (e.g., job `status`) happens at the database level, not in Python
- Supports efficient queries on large datasets (thousands of jobs/applications)

### Resume Upload Safety

- Maximum file size enforced by config (`MAX_RESUME_SIZE_BYTES`, default 10 MB)
- Supported types: PDF, DOC, DOCX
- Internal storage path is **not** exposed in API responses (security best practice)
- Files are stored on resume-service's local filesystem under `RESUME_UPLOAD_DIR`, backed by a named Docker volume (`resume_uploads`) shared with resume-service-worker so uploads persist across container recreates and stay visible to the parsing worker
- Resumes are uploaded independently of any application (`POST /resumes`) and only referenced by `resume_id` from applications, not owned by them

### Job Description Ingestion

- Recruiters can upload JD PDFs through `POST /jobs/{id}/description-file`
- Job description parsing state is tracked separately from recruiter-facing publication status
- `jobs.description` represents canonical markdown content, whether provided manually as a fallback or produced later by the parser
- JD files are stored on job-service's local filesystem under `JD_UPLOAD_DIR`; internal storage paths stay out of API responses

### Structured Candidate Profiles

- Candidate-level `master_profile_data` is stored as structured JSONB
- Canonical profile sections are `summary`, `skills`, `contact`, `education`, `work_experience`, and `links`
- Uploaded resume files and parser output live in candidate-owned resume snapshots; applications only reference the specific resume used for that submission

---

## 🗂️ Project Structure

```
smart-hire/
├── README.md                          # Repository overview
├── CLAUDE.md                          # Coding conventions and architectural guidelines
├── docs/
│   ├── ARCHITECTURE.md                # System design and Mermaid diagrams
│   ├── DATABASE.md                    # Schema and ER diagrams
│   ├── SETUP.md                       # Installation guide
│   ├── SERVICES.md                    # Service layer patterns
│   └── PRD.md                         # Product requirements and traceability
├── docker-compose.yml                 # Local dev stack — postgres, temporal, nginx, all services
├── .env.example                       # Root env template (single source for the whole stack)
├── postman/                           # Postman collection for API validation
│
├── infra/
│   ├── nginx/                         # API gateway: nginx.conf routes /api/v1/<resource> per service
│   └── postgres/                      # init.sql — creates the six logical databases
│
├── shared/                            # Code shared across services (mounted read-only at /shared)
│   ├── api/                           # Generic FastAPI health-router factory
│   ├── auth/                          # Header-based mock auth (X-User-ID, X-User-Role)
│   ├── config/                        # Base Pydantic Settings class
│   ├── db/                            # DeclarativeBase, TimestampMixin, session/health helpers
│   ├── exceptions/                    # Domain exceptions → HTTP status mapping + handler registration
│   ├── pdf/                           # Shared PDF-to-markdown converter (job descriptions + resumes)
│   └── temporal/                      # Shared Temporal client singleton
│
└── services/
    ├── recruiter/                     # Recruiter CRUD (port 8001, recruiter_db)
    ├── candidate/                     # Candidate CRUD (port 8002, candidate_db)
    ├── job/                           # Job CRUD + JobPublishingWorkflow (port 8003, job_db)
    ├── resume/                        # Resume upload + ResumeParsingWorkflow (port 8004, resume_db)
    ├── application/                   # Application workflow, HTTP calls to other services (port 8005, application_db)
    └── notification/                  # Reserved for future event-driven work — health endpoint only (port 8006)
```

Each service under `services/<name>/` follows the same internal layout: `app/api/routers/` → `app/services/` → `app/repositories/` → `app/db/models.py`, plus its own `alembic.ini`, `migrations/`, `requirements.txt`, and `Dockerfile`. `job/` and `resume/` additionally have `app/temporal/` (workflows, activities, worker entrypoint).

---

## 🚀 Quick Start

### Prerequisites

- **Docker & Docker Compose** (for containerized development)
- **Python 3.11+** (for running a single service locally without Docker)
- **Git** (for version control)

### Environment Setup

A single tracked template covers the whole stack:

```bash
cp .env.example .env
# Contains: Postgres credentials, NGINX_PORT, TEMPORAL_UI_PORT, per-service DATABASE_URLs,
# upload directories/limits, and MAX_APPLICATIONS_PER_CANDIDATE
```

⚠️ **Important:** `.env` is **never committed**. Use `.env.example` as the template.

### Docker Setup (Recommended)

```bash
# Start the full stack (postgres, temporal, nginx gateway, and all 6 services + their workers)
docker compose up -d --build

# View logs for a specific service
docker compose logs -f job-service
docker compose logs -f job-service-worker

# Verify the gateway and a service are healthy
curl http://localhost/health
curl http://localhost/api/v1/health/recruiter

# Stop the stack
docker compose down
```

Every service's `Dockerfile` runs `alembic upgrade head` before starting `uvicorn`, so `docker compose up --build` alone is enough — no manual migration step is required.

**Services:**

- **Gateway:** http://localhost/api/v1 (nginx — use this for real API requests)
- **Database:** localhost:5432 (PostgreSQL, six logical databases)
- **Temporal UI:** http://localhost:8080

Each service also publishes its own host port purely so its Swagger UI is reachable directly for local dev (recruiter 8001, candidate 8002, job 8003, resume 8004, application 8005, notification 8006) — actual API traffic should still go through the gateway so routing and auth-header forwarding match production shape.

### Local Development (Without Docker)

```bash
# Set up a shared Python environment at the repo root
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # macOS/Linux: source .venv/bin/activate
pip install -r services/<name>/requirements.txt

cd services/<name>
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port <service-port>
```

For detailed setup, port mappings, and the full manual validation walkthrough, see [docs/SETUP.md](docs/SETUP.md).

---

## 📡 API & Endpoints

All endpoints are served behind the nginx gateway under `http://localhost/api/v1`, which routes each `/api/v1/<resource>/*` prefix to the owning service — use this for real requests. Each service also publishes its own host port (8001-8006) directly, but that's a local-dev convenience for Swagger UI access, not the intended API surface.

**Health:**

- `GET /health` — gateway liveness check (nginx only, no backend dependency)
- `GET /api/v1/health/{recruiter,candidate,job,resume,application,notification}` — per-service deep health check (DB connectivity)

**Recruiters** (recruiter-service):

- `POST /api/v1/recruiters` — Create recruiter
- `GET /api/v1/recruiters/{id}` — Retrieve recruiter
- `GET /api/v1/recruiters` — List recruiters with pagination

**Candidates** (candidate-service):

- `POST /api/v1/candidates` — Register candidate
- `GET /api/v1/candidates/{id}` — Retrieve candidate profile
- `GET /api/v1/candidates` — List candidates with pagination
- `PATCH /api/v1/candidates/{id}` — Update candidate profile
- `DELETE /api/v1/candidates/{id}` — Delete candidate profile

**Jobs** (job-service):

- `POST /api/v1/jobs` — Create a draft job shell
- `GET /api/v1/jobs/{id}` — Retrieve job details
- `GET /api/v1/jobs` — List jobs (with filters)
- `PATCH /api/v1/jobs/{id}` — Update job details
- `POST /api/v1/jobs/{id}/description-file` — Upload a PDF job description for parsing
- `POST /api/v1/jobs/{id}/publish` — Publish the job (starts `JobPublishingWorkflow` in Temporal)
- `DELETE /api/v1/jobs/{id}` — Delete job

**Resumes** (resume-service):

- `POST /api/v1/resumes` — Upload a resume, independent of any application (starts `ResumeParsingWorkflow`)
- `GET /api/v1/resumes/{id}` — Retrieve a resume and its parsed data
- `GET /api/v1/resumes` — List a candidate's resumes
- `DELETE /api/v1/resumes?candidate_id={id}` — Bulk delete all resumes for a candidate

**Applications** (application-service):

- `POST /api/v1/applications` — Submit application (runs eligibility checks against job/candidate/resume services)
- `GET /api/v1/applications/{id}` — Retrieve application
- `GET /api/v1/applications` — List applications with filters
- `PATCH /api/v1/applications/{id}/status` — Recruiter transitions application status
- `DELETE /api/v1/applications?job_id={id}|candidate_id={id}` — Bulk delete applications for a job or candidate

**Manual API Testing:**

- Use the Postman collection at `postman/SmartHire.postman_collection.json` for the full validation flow through the gateway.
- Each service also exposes its own Swagger UI directly on its host port for interactive schema inspection: recruiter `:8001/docs`, candidate `:8002/docs`, job `:8003/docs`, resume `:8004/docs`, application `:8005/docs`, notification `:8006/docs`. It's a local-dev convenience — nginx doesn't proxy `/docs`, so it isn't reachable through the gateway.
- Resume and JD uploads are stored on each owning service's local filesystem, backed by named Docker volumes (`resume_uploads`, `job_uploads`) so they persist across `docker compose down`/recreate, and should remain untracked in git.

**Authentication:**

Mock auth via request headers:

- `X-User-ID` — Unique user identifier
- `X-User-Role` — User role (RECRUITER or CANDIDATE)

Example:

```bash
curl -X POST http://localhost/api/v1/jobs \
  -H "X-User-ID: 11111111-1111-1111-1111-111111111111" \
  -H "X-User-Role: RECRUITER" \
  -H "Content-Type: application/json" \
  -d '{"title": "Backend Engineer", "description": "Interim manual markdown while JD parsing is pending.", "required_skills": ["python", "fastapi"]}'
```

Resume upload example (independent of any application):

```bash
curl -X POST http://localhost/api/v1/resumes \
  -H "X-User-ID: candidate-123" \
  -H "X-User-Role: CANDIDATE" \
  -F "resume=@resume.pdf"
```

---

## 💾 Database Schema

One PostgreSQL container hosts **six independent logical databases**, one per service (`infra/postgres/init.sql`). Each service only ever connects to its own database — there are no cross-database foreign keys; cross-service references (e.g. an application's `job_id`) are indexed UUID columns validated at write-time via HTTP calls, not DB-level constraints.

| Database          | Owning Service        | Tables                                       | Key Fields                                                                                                                     |
| ------------------ | ---------------------- | --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `recruiter_db`     | recruiter-service      | `recruiters`                                 | id (UUID), email, name, timestamps                                                                                             |
| `candidate_db`     | candidate-service      | `candidates`                                 | id (UUID), email, name, master_profile_data (JSONB), timestamps                                                                |
| `job_db`           | job-service            | `jobs`, `job_status_history`                 | id (UUID), recruiter_id, title, description, description_breakdown (JSONB), required_skills (JSONB), status, jd_parsing_status |
| `resume_db`        | resume-service         | `candidate_resumes`                          | id (UUID), candidate_id, file_name, storage_path, parsing_status, structured_data (JSONB), timestamps                          |
| `application_db`   | application-service    | `applications`, `application_status_history` | id (UUID), job_id, candidate_id, resume_id, status, eligibility_result (JSONB), metadata (JSONB)                               |
| `notification_db`  | notification-service   | *(none yet — reserved for future event-driven work)*                   | —                                                                                                                                |

**Key Design Features:**

- **UUID Primary Keys:** All entities use UUID for global uniqueness (required once IDs cross service boundaries over HTTP)
- **JSONB Columns:** Flexible data storage for canonical candidate profiles, resume parsing output, job requirements, and eligibility results
- **Foreign Keys within a service only:** e.g. `job_status_history.job_id → jobs.id` and `application_status_history.application_id → applications.id`; `applications.job_id`/`candidate_id`/`resume_id` are plain indexed UUIDs since those tables live in other services' databases
- **Timestamps:** Automatic `created_at` and `updated_at` tracking
- **Unique Constraints:** Duplicate application prevention (`job_id`, `candidate_id`) inside `application_db`
- **Independent Resumes:** Resumes belong to a candidate, not an application — an application only stores the `resume_id` it was evaluated against

For schema diagrams and migration instructions, see [docs/DATABASE.md](docs/DATABASE.md).

---

## 🔧 Development Guide

### Common Commands

**Docker:**

See [Docker Setup](#docker-setup-recommended) section for startup instructions. Additional utilities:

```bash
# Access a specific logical database (recruiter_db, candidate_db, job_db, resume_db, application_db, notification_db)
docker exec -it smarthire-postgres psql -U smarthire -d recruiter_db
```

**Database Migrations** (run inside a specific service):

```bash
cd services/<name>

# Create a new migration
alembic revision --autogenerate -m "Describe your change"

# Apply pending migrations
alembic upgrade head

# View migration history
alembic history --verbose
```

Each service's `Dockerfile` also runs `alembic upgrade head` automatically on container start, so this is mainly needed for local (non-Docker) development or generating new revisions.

**Service Development:**

```bash
cd services/<name>
source ../../.venv/bin/activate   # Windows: ..\..\.venv\Scripts\Activate.ps1

# Run with hot reload
uvicorn app.main:app --reload --port <service-port>
```

### Code Organization

- **Routers** (`api/routers/`) — HTTP request/response handling, validation
- **Services** (`services/`) — Business logic, orchestration, validation
- **Repositories** (`repositories/`) — Database queries, no business logic
- **Schemas** (`schemas/`) — Pydantic models for validation and serialization

This layered approach ensures:

- **Testability:** Each layer can be tested independently
- **Reusability:** Services can be called from multiple routers
- **Maintainability:** Clear responsibility separation

For detailed patterns, see [docs/SERVICES.md](docs/SERVICES.md).

---

## 📚 Documentation

- **[docs/SETUP.md](docs/SETUP.md)** — Installation, configuration, and local development flow
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — System design and Mermaid architecture diagrams
- **[docs/DATABASE.md](docs/DATABASE.md)** — Schema design, ER diagram, and migrations
- **[docs/SERVICES.md](docs/SERVICES.md)** — Service patterns, orchestration boundaries, and request flows
- **[docs/PRD.md](docs/PRD.md)** — Product requirements, use cases, functional and non-functional requirements, milestones, and traceability

---

## 📖 Key Design Principles

1. **Async-First:** All I/O is async (FastAPI, SQLAlchemy, Alembic)
2. **No Hardcoded Secrets:** Real credentials always come from environment variables
3. **Separation of Concerns:** Routers → Services → Repositories
4. **Event-Driven:** Jobs and applications trigger domain events
5. **Reproducible:** Migrations ensure schema consistency across environments
