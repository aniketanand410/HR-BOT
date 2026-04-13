"""Sync Google Drive folder tree into Pinecone."""

from __future__ import annotations

import os
import time
from typing import Any

from openai import OpenAI

from app.chunking import chunk_text
from app.config import Settings
from app.drive_client import download_file_bytes, iter_files_recursive
from app.embeddings import embed_texts
from app.text_extract import extract_text
from app.vector_store import PineconeStore


def sync_drive_to_pinecone(
    settings: Settings,
    client: OpenAI,
    store: PineconeStore,
    credentials_path: str | None = None,
) -> dict[str, Any]:
    creds = credentials_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds or not os.path.isfile(creds):
        raise ValueError(
            "Set GOOGLE_APPLICATION_CREDENTIALS to a service-account JSON file with Drive access."
        )

    stats = {"files_seen": 0, "files_indexed": 0, "chunks": 0, "skipped_empty": 0, "errors": []}

    embed_batch_size = 64
    pending_texts: list[str] = []
    pending_meta: list[dict[str, Any]] = []
    pending_fids: list[str] = []
    pending_idx: list[int] = []

    def flush():
        nonlocal pending_texts, pending_meta, pending_fids, pending_idx
        if not pending_texts:
            return
        vecs = embed_texts(client, settings, pending_texts)
        store.upsert_chunks(vecs, pending_meta, pending_fids, pending_idx)
        pending_texts, pending_meta, pending_fids, pending_idx = [], [], [], []

    for df in iter_files_recursive(creds, settings.google_drive_root_folder_id):
        stats["files_seen"] += 1
        try:
            raw, suffix = download_file_bytes(creds, df)
            text = extract_text(raw, suffix)
            if not text.strip():
                stats["skipped_empty"] += 1
                continue
            chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
            if not chunks:
                stats["skipped_empty"] += 1
                continue
            stats["files_indexed"] += 1
            for i, ch in enumerate(chunks):
                meta = {
                    "logical_path": df.logical_path,
                    "drive_file_id": df.file_id,
                    "chunk_index": i,
                    "text": ch[:3500],
                    "updated_at": int(time.time()),
                }
                pending_texts.append(ch)
                pending_meta.append(meta)
                pending_fids.append(df.file_id)
                pending_idx.append(i)
                stats["chunks"] += 1
                if len(pending_texts) >= embed_batch_size:
                    flush()
        except Exception as e:  # noqa: BLE001 - surface per-file errors in sync report
            stats["errors"].append({"file": df.logical_path, "error": str(e)})

    flush()
    return stats
