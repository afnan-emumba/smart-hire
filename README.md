# SmartHire: Intelligent Workforce Orchestration & Recruitment Platform

A next-generation recruitment automation platform built for fast-scaling enterprises, staffing agencies, and global HR teams. SmartHire handles job publishing, candidate applications, workflow orchestration, and intelligent matching at scale.

## 📋 Project Status

**Phase A (Week 1-3):** Core Recruitment Platform ✅ _In Progress_

- ✅ Week 1: Foundation & Core Management
- 🔄 Week 2: Application Workflow & Publishing Pipeline
- ⏳ Week 3: Event-Driven System & Observability

**Phase B (Week 4-5):** AI-Powered Intelligence (Future)

---

## 🏗️ Architecture Overview

SmartHire is built on an **async-first, event-driven architecture** with clear separation of concerns:

- **API Layer:** FastAPI (async)
- **Data Layer:** SQLAlchemy 2.0 + PostgreSQL
- **Workflows:** Temporal (stateful processes)
- **Events:** Kafka + Schema Registry
- **Background Tasks:** Celery + RabbitMQ
- **Observability:** Prometheus, Grafana, Jaeger, OpenTelemetry

For detailed architecture, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

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
│
└── frontend/
    ├── package.json
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx
    │   └── components/
    └── lib/
```

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- PostgreSQL (handled by Docker)

### Setup

1. **Clone and configure:**

   ```bash
   cp .env.example .env
   cp backend/.env.example backend/.env
   # Edit .env files with your local values
   ```

2. **Start the stack:**

   ```bash
   docker compose up -d --build
   ```

3. **Verify health:**
   ```bash
   curl http://localhost:8000/health
   # Expected: {"status":"ok","database":"up"}
   ```

For detailed setup instructions, see [docs/SETUP.md](docs/SETUP.md).

---

## 📡 API Overview

- `GET /health` — System health check
- `POST /recruiters` — Create recruiter
- `POST /candidates` — Create candidate
- `POST /jobs` — Post job opening
- `POST /applications` — Submit application
- `GET /docs` — Swagger UI

The interactive API reference is available at `/docs` when the backend is running.

---

## 💾 Database Schema

SmartHire uses PostgreSQL with async SQLAlchemy. Core entities:

- **recruiters** — Hiring team members
- **candidates** — Job seekers
- **jobs** — Job postings with workflow stages
- **applications** — Candidate applications with tracking

For schema details and ER diagram, see [docs/DATABASE.md](docs/DATABASE.md).

---

## 🔧 Development

### Run locally with Docker:

```bash
docker compose up -d --build
docker compose logs -f backend
```

### Run backend only (with local DB):

```bash
cd backend
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Database migrations:

```bash
cd backend
alembic upgrade head      # Apply migrations
alembic revision --autogenerate -m "Description"  # Create new migration
```

---

## 🏛️ Architecture & Services

For comprehensive service layer patterns and workflow orchestration, see [docs/SERVICES.md](docs/SERVICES.md).

---

## 📚 Documentation

- **[docs/SETUP.md](docs/SETUP.md)** — Installation, configuration, and local development flow
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — System design and Mermaid architecture diagrams
- **[docs/DATABASE.md](docs/DATABASE.md)** — Schema design, Mermaid ER diagram, and migrations
- **[docs/SERVICES.md](docs/SERVICES.md)** — Service patterns, orchestration boundaries, and request flows

---

## 📖 Key Design Principles

1. **Async-First:** All I/O is async (FastAPI, SQLAlchemy, Alembic)
2. **No Hardcoded Secrets:** Real credentials always come from environment variables
3. **Separation of Concerns:** Routers → Services → Repositories
4. **Event-Driven:** Jobs and applications trigger domain events
5. **Reproducible:** Migrations ensure schema consistency across environments

---

## 🤝 Contributing

Follow the patterns established in Week 1:

- Use type hints and async throughout
- Keep repositories data-focused
- Put business logic in services
- Add migrations for schema changes
- Minimal inline comments (let code speak for itself)

---

## 📝 License

Internal project for TalentSphere Inc.
