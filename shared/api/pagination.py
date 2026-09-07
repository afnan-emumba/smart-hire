from __future__ import annotations

from dataclasses import dataclass

from fastapi import Query


@dataclass
class PaginationParams:
    limit: int = Query(default=20, ge=1, le=100)
    offset: int = Query(default=0, ge=0)
