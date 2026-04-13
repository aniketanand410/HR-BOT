from __future__ import annotations

from openai import OpenAI

from app.config import Settings


def embed_texts(client: OpenAI, settings: Settings, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    resp = client.embeddings.create(model=settings.embedding_model, input=texts)
    # Preserve input order
    data = sorted(resp.data, key=lambda d: d.index)
    return [d.embedding for d in data]
