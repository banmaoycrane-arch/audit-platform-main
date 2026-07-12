# 后端镜像：FastAPI + uvicorn（生产用 · Excel-only 精简版）
# 默认只装 pyproject 核心依赖，不含 OpenCV / easyocr / torch。
# 需要印章 CV：pip install -e "./backend[vision]" 并在 Dockerfile 增加 libxcb 等 apt 包。
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_TRUSTED_HOST=mirrors.aliyun.com

WORKDIR /app

COPY backend/ ./backend/

RUN pip install --upgrade pip setuptools wheel \
    && pip install -e ./backend

EXPOSE 8000

CMD ["sh", "-c", "mkdir -p /data/uploads /data/qdrant && exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000"]
