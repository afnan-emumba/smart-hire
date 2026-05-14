# SmartHire: Intelligent Workforce Orchestration & Recruitment Platform

A next-generation recruitment automation platform built for fast-scaling enterprises, staffing agencies, and global HR teams. SmartHire handles job publishing, candidate applications, workflow orchestration, and intelligent matching at scale.

## 📋 About SmartHire

SmartHire is a **recruitment automation and workflow orchestration platform** designed for enterprises and staffing agencies. It streamlines job posting, candidate applications, and hiring workflows at scale.

**Key Capabilities:**

- **Job & Candidate Management:** Full CRUD for job postings and candidate profiles
- **Application Workflow:** Track candidate applications from submission to hiring decisions
- **Async Processing:** Reliable background task execution for notifications, scoring, and analytics
- **Scalable Architecture:** Event-driven design to handle high-volume hiring campaigns
- **Foundation for AI:** Built to integrate intelligent candidate matching and recommendations (Phase B)

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
- Files are stored locally in `uploads/resumes/` (git-ignored) during development

---

## 🗂️ Project Structure

```
smart-hire/
├── README.md                          # Repository overview
├── docs/
│   ├── ARCHITECTURE.md                # System design and Mermaid diagrams
│   ├── DATABASE.md                    # Schema and ER diagrams
│   ├── SETUP.md                       # Installation guide
│   └── SERVICES.md                    # Service layer patterns
├── docker-compose.yml                 # Local dev stack
├── .env.example                       # Root env template
│
├── backend/
│   ├── requirements.txt               # Python dependencies
│   ├── .env.example                   # Backend env template
│   ├── Dockerfile
│   ├── alembic.ini                    # Migration config
│   ├── migrations/                    # Alembic migration files
│   └── app/
│       ├── main.py                    # FastAPI entry point
│       ├── core/
│       │   ├── config.py              # Settings management
│       │   └── auth.py                # Mock auth
│       ├── db/
│       │   ├── models.py              # SQLAlchemy ORM
│       │   └── session.py             # DB connection
│       ├── schemas/                   # Pydantic validation
│       ├── repositories/              # Data access layer
│       ├── services/                  # Business logic
│       └── api/
│           ├── router.py              # Main router
│           └── routers/               # Endpoint groups
├── backend/postman/                   # Postman collection for API validation
└── backend/uploads/                   # Local dev resume storage (git-ignored)
```

---

## 🚀 Quick Start

### Prerequisites

- **Docker & Docker Compose** (for containerized development)
- **Python 3.11+** (for local backend development without Docker)
- **Git** (for version control)

### Environment Setup

SmartHire uses environment variables for configuration. Two levels of `.env` files:

**1. Root `.env` (Docker Compose):**

```bash
cp .env.example .env
# Contains: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST_PORT, BACKEND_PORT, APP_ENV, RESUME_UPLOAD_DIR
```

**2. Backend `.env` (App Runtime):**

```bash
cp backend/.env.example backend/.env
# Contains: DATABASE_URL, APP_ENV, APP_HOST, APP_PORT, RESUME_UPLOAD_DIR, PYTHONDONTWRITEBYTECODE, PYTHONUNBUFFERED
```

⚠️ **Important:** `.env` files are **never committed**. Use `.env.example` as templates.

### Docker Setup (Recommended)

```bash
# Start the full stack (PostgreSQL + FastAPI)
docker compose up -d --build

# View logs
docker compose logs -f backend

# Verify health
curl http://localhost:8000/health
# Expected: {"status":"ok","database":"up"}

# Stop the stack
docker compose down
```

**Services:**

- **Backend:** http://localhost:8000 (FastAPI)
- **Database:** localhost:5432 (PostgreSQL)
- **API Docs:** http://localhost:8000/docs (Swagger UI)

### Local Development (Without Docker)

```bash
# Set up Python environment
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Configure database
cp .env.example .env
# Edit .env with your local database credentials

# Run migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

For detailed setup including database migrations, see [docs/SETUP.md](docs/SETUP.md).

---

## 📡 API & Endpoints

SmartHire exposes RESTful endpoints for managing recruiters, candidates, jobs, and applications.

**Available Endpoints:**

- `GET /health` — System health check
- `POST /recruiters` — Create recruiter
- `POST /candidates` — Register candidate
- `GET /candidates/{id}` — Retrieve candidate profile
- `GET /candidates` — List candidates with pagination
- `POST /jobs` — Post a job opening
- `GET /jobs/{id}` — Retrieve job details
- `GET /jobs` — List jobs (with filters)
- `POST /applications` — Submit application
- `POST /applications/{id}/resume` — Upload a resume file for a specific application
- `GET /applications/{id}` — Retrieve application
- `GET /applications` — List applications with filters
- `GET /docs` — Interactive Swagger UI
- `GET /redoc` — Alternate API documentation

**Manual API Testing:**

- Use Swagger UI at `/docs` for quick request/response inspection.
- Use Postman for the full Day 5 validation flow. A starter collection lives in `backend/postman/`.
- For local development, resume uploads are stored on disk under `backend/uploads/` and should remain untracked.

**Authentication:**

Mock auth via request headers:

- `X-User-ID` — Unique user identifier
- `X-User-Role` — User role (RECRUITER or CANDIDATE)

Example:

```bash
curl -X POST http://localhost:8000/jobs \
  -H "X-User-ID: recruiter-123" \
  -H "X-User-Role: RECRUITER" \
  -H "Content-Type: application/json" \
  -d '{"title": "Backend Engineer", "description": "...", "recruiter_id": "..."}'
```

Resume upload example:

```bash
curl -X POST http://localhost:8000/applications/<application-id>/resume \
  -H "X-User-ID: candidate-123" \
  -H "X-User-Role: CANDIDATE" \
  -F "resume=@resume.pdf"
```

---

## 💾 Database Schema

SmartHire uses PostgreSQL with async SQLAlchemy ORM. The schema includes four core entities:

| Table            | Purpose               | Key Fields                                                                                                                                    |
| ---------------- | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **recruiters**   | Hiring team members   | id (UUID), email, name, timestamps                                                                                                            |
| **candidates**   | Job seekers           | id (UUID), email, name, timestamps                                                                                                            |
| **jobs**         | Job postings          | id (UUID), recruiter_id (FK), title, description, status, required_skills (JSONB), timestamps                                                 |
| **applications** | Candidate submissions | id (UUID), job_id (FK), candidate_id (FK), recruiter_id (FK), status, metadata (JSONB), resume file metadata, resume_data (JSONB), timestamps |

**Key Design Features:**

- **UUID Primary Keys:** All entities use UUID for global uniqueness
- **JSONB Columns:** Flexible data storage for application resume parsing output, job requirements, and application scores
- **Foreign Keys:** Strict referential integrity between entities
- **Timestamps:** Automatic `created_at` and `updated_at` tracking
- **Unique Constraints:** Duplicate application prevention (job_id, candidate_id)
- **Application-Scoped Resumes:** Each application can store a different uploaded resume for the target role

For schema diagrams and migration instructions, see [docs/DATABASE.md](docs/DATABASE.md).

---

## 🔧 Development Guide

### Common Commands

**Docker:**

See [Docker Setup](#docker-setup-recommended) section for startup instructions. Additional utilities:

```bash
# Access database CLI
docker exec -it smarthire-postgres psql -U smarthire -d smarthire
```

**Database Migrations:**

```bash
cd backend

# Create a new migration
alembic revision --autogenerate -m "Describe your change"

# Apply pending migrations
alembic upgrade head

# View migration history
alembic history --verbose
```

**Backend Development:**

```bash
cd backend
source .venv/bin/activate

# Run tests or linting (if configured)
pytest
flake8 app

# Run with hot reload
uvicorn app.main:app --reload --port 8000
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
