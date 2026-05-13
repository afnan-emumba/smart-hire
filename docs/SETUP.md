# Setup: Installation and Local Development

## Environment Files

Tracked templates live here:

- `.env.example`
- `backend/.env.example`

Real `.env` files remain untracked and should stay local.

## Setup Flow

```mermaid
flowchart TD
    clone[Clone repository]
    copyRoot[Copy .env.example to .env]
    copyBackend[Copy backend/.env.example to backend/.env]
    start[Run docker compose up -d --build]
    migrate[Run alembic upgrade head]
    verify[Check /health, /docs, and Postman flow]

    clone --> copyRoot --> copyBackend --> start --> migrate --> verify
```

## Quick Start

```bash
cp .env.example .env
cp backend/.env.example backend/.env
docker compose up -d --build
cd backend
alembic upgrade head
```

## Local Services

| Service         | Default Port | Purpose                     |
| --------------- | ------------ | --------------------------- |
| FastAPI backend | 8000         | HTTP API and Swagger        |
| PostgreSQL      | 5432         | Primary relational database |

## Backend Local Run

```bash
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Docker Compose Run

```bash
docker compose up -d --build
docker compose logs -f backend
```

## Migration Workflow

```bash
cd backend
alembic upgrade head
alembic revision --autogenerate -m "describe change"
```

## Verification

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{ "status": "ok", "database": "up" }
```

## Manual API Testing

Use one of these entry points:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Postman collection: `backend/postman/SmartHire.postman_collection.json`

Required mock auth headers for most requests:

- `X-User-ID`
- `X-User-Role` with value `RECRUITER` or `CANDIDATE`

Recommended Day 5 validation order:

1. Create a recruiter.
2. Create a candidate.
3. Create a job as a recruiter.
4. Create an application as a candidate.
5. Upload a resume to that application with multipart form-data.
6. Re-run `GET /applications/{id}` and confirm the resume metadata is present.
7. Re-submit the same application payload and confirm duplicate rejection.

Resume upload notes:

- Local development stores files under `backend/uploads/resumes` by default.
- Override the location with `RESUME_UPLOAD_DIR` if needed.
- Supported upload types are PDF, DOC, and DOCX.

## Troubleshooting

### Database connection fails

- Confirm `smarthire-postgres` is running.
- Confirm `DATABASE_URL` points to `localhost` for local backend runs and `postgres` for compose-based runs.
- Re-run `alembic upgrade head` after the database is healthy.

### Alembic import fails

- Activate `backend/.venv`.
- Install dependencies from `backend/requirements.txt`.
- Keep `backend/alembic.ini` free of real connection strings; runtime settings are loaded from environment.

### Resume upload fails

- Confirm `python-multipart` is installed from `backend/requirements.txt`.
- Confirm the upload directory exists or that the backend process can create it.
- Confirm the request uses `multipart/form-data` with the field name `resume`.

## Related Documentation

- [Architecture](ARCHITECTURE.md)
- [Database Design](DATABASE.md)
- [Service Layer](SERVICES.md)
