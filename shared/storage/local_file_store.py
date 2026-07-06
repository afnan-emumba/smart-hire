from __future__ import annotations

import asyncio
import os
from pathlib import Path


async def write_file(*, directory: str, file_name: str, file_bytes: bytes) -> str:
    upload_dir = Path(directory)
    await asyncio.to_thread(upload_dir.mkdir, parents=True, exist_ok=True)

    file_path = upload_dir / file_name
    await asyncio.to_thread(file_path.write_bytes, file_bytes)
    return file_path.as_posix()


async def remove_if_exists(storage_path: str | None) -> None:
    if not storage_path:
        return

    path = Path(storage_path)
    if path.exists():
        await asyncio.to_thread(os.remove, path)
