from __future__ import annotations

from api.health import make_health_router

from app.db.session import get_db_session, ping_database


router = make_health_router(get_db_session, ping_database)
