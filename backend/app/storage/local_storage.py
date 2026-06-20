from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile

from app.core.config import get_settings


def save_upload(file: UploadFile) -> str:
    upload_dir = Path(get_settings().upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "upload.bin").suffix
    target = upload_dir / f"{uuid4().hex}{suffix}"
    with target.open("wb") as buffer:
        while chunk := file.file.read(1024 * 1024):
            buffer.write(chunk)
    return str(target)
