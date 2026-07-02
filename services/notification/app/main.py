from __future__ import annotations

from fastapi import FastAPI, status

app = FastAPI(title="Notification Service", docs_url="/docs", redoc_url="/redoc")


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
