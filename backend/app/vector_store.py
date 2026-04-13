"""Pinecone vector store for HR policy chunks."""

from __future__ import annotations

import hashlib
import time
from typing import Any

from pinecone import Pinecone

from app.config import Settings


def _chunk_id(file_id: str, chunk_index: int) -> str:
    raw = f"{file_id}:{chunk_index}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


class PineconeStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        pc = Pinecone(api_key=settings.pinecone_api_key)
        if settings.pinecone_host:
            self._index = pc.Index(settings.pinecone_index_name, host=settings.pinecone_host)
        else:
            self._index = pc.Index(settings.pinecone_index_name)

    def upsert_chunks(
        self,
        vectors: list[list[float]],
        metadatas: list[dict[str, Any]],
        file_ids: list[str],
        chunk_indices: list[int],
    ) -> None:
        items = []
        for vec, meta, fid, idx in zip(vectors, metadatas, file_ids, chunk_indices, strict=True):
            items.append({"id": _chunk_id(fid, idx), "values": vec, "metadata": meta})
        # Pinecone batch limit
        batch = 100
        for i in range(0, len(items), batch):
            self._index.upsert(vectors=items[i : i + batch], namespace=self.settings.namespace)

    def query(self, vector: list[float], top_k: int) -> list[dict[str, Any]]:
        res = self._index.query(
            vector=vector,
            top_k=top_k,
            namespace=self.settings.namespace,
            include_metadata=True,
        )
        out: list[dict[str, Any]] = []
        for m in res.matches or []:
            out.append(
                {
                    "id": m.id,
                    "score": float(m.score or 0.0),
                    "metadata": dict(m.metadata or {}),
                }
            )
        return out
