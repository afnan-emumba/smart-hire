from __future__ import annotations

from fastapi import HTTPException, UploadFile, status


async def read_limited_upload(
    upload: UploadFile,
    max_bytes: int,
    *,
    error_detail: str,
) -> bytes:
    chunks: list[bytes] = []
    total_size = 0

    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=error_detail,
            )
        chunks.append(chunk)

    return b"".join(chunks)
