# 后端镜像：FastAPI + uvicorn（生产用）
# 说明：所有持久化数据（SQLite 数据库 / 上传文件 / 本地向量库）都写入 /data 卷，
#       镜像本身保持只读、可随时重建，升级不丢数据。
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 仅复制后端代码（利用 Docker 层缓存）
COPY backend/ ./backend/

# 安装后端依赖（pyproject.toml 已固定 bcrypt<4.1 等关键约束）
RUN pip install --upgrade pip && pip install -e ./backend

EXPOSE 8000

# 启动前先确保数据子目录存在（/data 是运行时挂载的空卷），再以生产方式启动 uvicorn
CMD ["sh", "-c", "mkdir -p /data/uploads /data/qdrant && exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000"]
