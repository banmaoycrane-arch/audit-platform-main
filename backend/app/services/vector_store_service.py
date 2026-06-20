import hashlib
import os
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import get_settings
from app.services.embedding_service import embed_text


def chunk_text(text: str, size: int = 500) -> list[str]:
    clean = " ".join(text.split())
    if not clean:
        return []
    return [clean[index : index + size] for index in range(0, len(clean), size)]


def chunk_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class VectorStore:
    def __init__(self) -> None:
        settings = get_settings()
        self.collection = settings.qdrant_collection
        self.dimension = settings.embedding_dimension
        self._local = False
        client = self._try_url(settings.qdrant_url)
        if client is None:
            client = self._try_local(settings.qdrant_local_path)
            self._local = True
        if client is None:
            raise RuntimeError("无法初始化 Qdrant 客户端（远程和本地模式均失败）")
        self.client = client

    @staticmethod
    def _try_url(url: str) -> QdrantClient | None:
        try:
            client = QdrantClient(url=url, timeout=3)
            client.get_collections()
            return client
        except Exception:
            return None

    @staticmethod
    def _try_local(path: str) -> QdrantClient | None:
        try:
            abs_path = str(Path(path).resolve())
            os.makedirs(abs_path, exist_ok=True)
            client = QdrantClient(path=abs_path)
            client.get_collections()
            return client
        except Exception:
            return None

    def ensure_collection(self) -> None:
        collections = self.client.get_collections().collections
        if not any(item.name == self.collection for item in collections):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=qmodels.VectorParams(size=self.dimension, distance=qmodels.Distance.COSINE),
            )

    def upsert_text(self, point_id: str, text: str, payload: dict) -> None:
        self.ensure_collection()
        self.client.upsert(
            collection_name=self.collection,
            points=[qmodels.PointStruct(id=point_id, vector=embed_text(text), payload=payload)],
        )

    def search(self, text: str, limit: int = 5) -> list[dict]:
        self.ensure_collection()
        resp = self.client.query_points(
            collection_name=self.collection,
            query=embed_text(text),
            limit=limit,
        )
        return [
            {"id": str(item.id), "score": item.score, "payload": item.payload}
            for item in resp.points
        ]


def safe_vector_store() -> VectorStore | None:
    try:
        return VectorStore()
    except Exception:
        return None
