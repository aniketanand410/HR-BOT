"""Retrieval + generation with explicit citations and abstention when confidence is low."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from app.config import Settings
from app.embeddings import embed_texts
from app.vector_store import PineconeStore


SYSTEM_PROMPT = """You are an internal HR assistant for employees.
Rules:
- Answer ONLY using the provided CONTEXT snippets. Each snippet includes source_path and optional excerpt markers.
- If the context does not clearly support an answer, say you cannot find that in the official HR materials and suggest contacting HR.
- Always cite which source_path(s) you used for factual claims. Use short quotes or paraphrases tied to those paths.
- Do not invent policies, numbers, or legal interpretations.
"""


def answer_question(
    client: OpenAI,
    settings: Settings,
    store: PineconeStore,
    question: str,
) -> dict[str, Any]:
    q_vec = embed_texts(client, settings, [question])[0]
    hits = store.query(q_vec, top_k=settings.retrieval_top_k)
    best = hits[0]["score"] if hits else 0.0

    if not hits or best < settings.min_retrieval_score:
        return {
            "answer": (
                "I do not have enough high-confidence information in the indexed HR documents "
                "to answer that safely. Try rephrasing, or contact your HR team. "
                "If this topic should be covered, confirm the relevant folder in Google Drive has been synced."
            ),
            "citations": [],
            "confidence": "low",
            "best_score": best,
        }

    context_blocks = []
    citations: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for h in hits:
        md = h["metadata"]
        path = str(md.get("logical_path", "unknown"))
        snippet = str(md.get("text", ""))[:1200]
        context_blocks.append(
            json.dumps(
                {
                    "source_path": path,
                    "drive_file_id": md.get("drive_file_id", ""),
                    "chunk_index": md.get("chunk_index", 0),
                    "text": snippet,
                },
                ensure_ascii=False,
            )
        )
        if path not in seen_paths:
            seen_paths.add(path)
            citations.append(
                {
                    "path": path,
                    "drive_file_id": str(md.get("drive_file_id", "")),
                }
            )

    user_content = (
        f"QUESTION:\n{question}\n\nCONTEXT (JSON lines, one object per chunk):\n"
        + "\n".join(context_blocks)
    )

    completion = client.chat.completions.create(
        model=settings.chat_model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    answer = (completion.choices[0].message.content or "").strip()
    confidence = "medium" if best < (settings.min_retrieval_score + 0.12) else "high"
    return {
        "answer": answer,
        "citations": citations[:6],
        "confidence": confidence,
        "best_score": best,
    }
