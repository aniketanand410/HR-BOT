"""HR RAG API: Drive sync + cited chat."""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import get_settings
from app.rag import answer_question
from app.sync_service import sync_drive_to_pinecone
from app.vector_store import PineconeStore

app = FastAPI(title="HR RAG Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)


class ChatResponse(BaseModel):
    answer: str
    citations: list[dict[str, str]]
    confidence: str
    best_score: float


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    store = PineconeStore(settings)
    try:
        result = answer_question(client, settings, store, body.message.strip())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e
    return ChatResponse(**result)


@app.post("/api/sync")
def sync():
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    store = PineconeStore(settings)
    try:
        stats = sync_drive_to_pinecone(settings, client, store)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e
    return stats
