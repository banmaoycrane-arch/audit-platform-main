from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile

from app.core.config import BACKEND_DIR, get_settings



def resolve_storage_path(storage_path: str) -> str:
    """把上传文件路径统一解析为后端目录下的实际路径。"""
    path = Path(storage_path)
    if path.is_absolute():
        return str(path)
    return str(BACKEND_DIR / path)


def save_upload(file: UploadFile) -> str:
    upload_dir = Path(resolve_storage_path(get_settings().upload_dir))
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "upload.bin").suffix
    target = upload_dir / f"{uuid4().hex}{suffix}"
    with target.open("wb") as buffer:
        while chunk := file.file.read(1024 * 1024):
            buffer.write(chunk)
    return str(target.relative_to(BACKEND_DIR))
