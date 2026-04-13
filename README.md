# HR RAG Agent

Internal HR assistant that answers from **your** Google Drive policy library using retrieval-augmented generation (RAG). Answers are grounded in indexed chunks; when retrieval confidence is low, the API **abstains** instead of guessing.

## Architecture

- **Ingestion**: A FastAPI job walks a **root Google Drive folder** recursively (nested paths like `HR/policies/...` or `HR/legal/remote work/...` are preserved as `logical_path` metadata).
- **Files**: PDF, Word (`.docx`), PowerPoint (`.pptx`), native Google Docs/Sheets/Slides (exported at sync time).
- **Embeddings + chat**: OpenAI (`text-embedding-3-small`, `gpt-4o-mini` by default).
- **Vector DB**: [Pinecone](https://www.pinecone.io/) (default in code). For **Databricks**, mirror the same metadata schema in a Databricks Vector Search index and swap the `PineconeStore` implementation—see `backend/app/vector_store.py`.
- **UI**: React + Vite chat that shows **citations** (Drive paths) and a **confidence** label.

## Prerequisites

1. **Google Cloud**: Create a service account, enable the **Google Drive API**, download JSON keys.
2. **Drive sharing**: Share your HR root folder (and subfolders) with the service account email (Viewer is enough).
3. **Pinecone**: Create an index with dimension **1536** (for `text-embedding-3-small`) and metric **cosine** (or dotproduct; tune `MIN_RETRIEVAL_SCORE` accordingly).
4. **OpenAI** API key with embedding + chat access.

## Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env` from `/workspace/env.example` (or export variables). **Important**: point `GOOGLE_APPLICATION_CREDENTIALS` at the service-account JSON file.

Run API:

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Initial indexing (pulls from Drive, chunks, embeds, upserts to Pinecone):

```bash
curl -X POST http://127.0.0.1:8000/api/sync
```

Schedule this on a timer (cron, GitHub Actions, etc.) when Drive content changes.

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The dev server proxies `/api` to `http://127.0.0.1:8000` (see `frontend/vite.config.ts`).

## Configuration notes

- **`GOOGLE_DRIVE_ROOT_FOLDER_ID`**: The Drive folder ID from the URL (`folders/<id>`). Everything under it is indexed; folder names become the citation path prefix.
- **`MIN_RETRIEVAL_SCORE`**: Raise for stricter answers (more abstention); lower if legitimate hits score below threshold on your index metric.
- **Security**: This repo is a starting point. Add authentication (SSO, API keys, VPN) before exposing beyond your network.

## API

- `POST /api/chat` — body `{ "message": "..." }` → `{ answer, citations, confidence, best_score }`
- `POST /api/sync` — re-index from Drive
- `GET /api/health` — liveness
