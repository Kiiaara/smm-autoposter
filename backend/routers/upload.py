import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
from config import settings

router = APIRouter(prefix="/api/upload", tags=["upload"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".jfif", ".png", ".gif", ".mp4", ".mov", ".webp", ".heic"}
MAX_SIZE_BYTES = settings.max_upload_size_mb * 1024 * 1024


@router.post("")
async def upload_files(files: List[UploadFile] = File(...)):
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Max 10 files at once")

    os.makedirs(settings.upload_dir, exist_ok=True)
    saved = []

    for file in files:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"File type {ext} not allowed")

        content = await file.read()
        if len(content) > MAX_SIZE_BYTES:
            raise HTTPException(status_code=400, detail=f"File {file.filename} exceeds {settings.max_upload_size_mb}MB")

        # .jfif = jpeg с другим расширением. VK/TG нормально глотают только .jpg,
        # поэтому просто переименовываем при сохранении.
        save_ext = ".jpg" if ext == ".jfif" else ext
        filename = f"{uuid.uuid4()}{save_ext}"
        path = os.path.join(settings.upload_dir, filename)
        with open(path, "wb") as f:
            f.write(content)
        saved.append(f"uploads/{filename}")

    return {"paths": saved}
