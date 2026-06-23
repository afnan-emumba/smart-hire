from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def is_unique_violation(error: IntegrityError) -> bool:
    orig = getattr(error, "orig", None)
    if orig is None:
        return False

    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    if sqlstate == "23505":
        return True

    return "unique constraint" in str(error).casefold() or "duplicate key" in str(error).casefold()
