from app.main import app
from __future__ import annotations

from fastapi import FastAPI, status

from core.database import ping_database


app = FastAPI(title="SmartHire API")


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, str]:
    database_ok = await ping_database()
    return {
        "status": "ok" if database_ok else "degraded",
        "database": "up" if database_ok else "down",
    }