from __future__ import annotations

from api.app_factory import make_app
from app.api.router import api_router
from app.core.config import get_settings

settings = get_settings()

app = make_app(app_name=settings.app_name)

app.include_router(api_router)
