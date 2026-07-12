from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile

from app.core.config import BACKEND_DIR, get_settings



def resolve_storage_path(storage_path: str) -> str:
    """把上传文件路径统一解析为可读的实际路径（兼容本地与 Docker /data/uploads）。"""
    raw = Path(storage_path)
    if raw.is_absolute():
        return str(raw)

    upload_setting = get_settings().upload_dir
    upload_base = Path(upload_setting) if Path(upload_setting).is_absolute() else BACKEND_DIR / upload_setting

    candidates = [
        BACKEND_DIR / raw,
        upload_base / raw,
        upload_base / raw.name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return str((BACKEND_DIR / raw).resolve())


def save_upload(file: UploadFile) -> str:
    upload_dir = Path(resolve_storage_path(get_settings().upload_dir))
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "upload.bin").suffix
    target = upload_dir / f"{uuid4().hex}{suffix}"
    with target.open("wb") as buffer:
        while chunk := file.file.read(1024 * 1024):
            buffer.write(chunk)
    try:
        return str(target.relative_to(BACKEND_DIR))
    except ValueError:
        return str(target.resolve())
