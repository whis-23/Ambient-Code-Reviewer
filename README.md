# Ambient Code Reviewer

> **Real-time AI agent for GitHub Pull Request architectural reviews.**  
> Powered by **FastAPI · LangGraph · pgvector · Redis · Celery**

---

## What It Does

When a developer opens or updates a Pull Request, the Ambient Code Reviewer:

1. **Receives** the GitHub webhook event (HMAC-validated)
2. **Fetches** the raw diff (secrets/PII auto-redacted before LLM contact)
3. **Retrieves** the most relevant internal ADRs and docs via **pgvector** semantic search
4. **Critiques** the diff against those docs using an LLM (Gemini 2.0 Flash by default)
5. **Posts** a consolidated architectural review comment directly on the PR thread

## Architecture

```
GitHub Webhook
      │
      ▼
┌─────────────┐     HMAC validate     ┌──────────────────┐
│  FastAPI    │──────────────────────▶│  Celery Worker   │
│  /webhook   │    enqueue task       │  (Redis broker)  │
└─────────────┘                       └────────┬─────────┘
                                               │
                              ┌────────────────▼──────────────────┐
                              │         LangGraph Graph            │
                              │  fetcher → retriever → analyzer   │
                              │           → poster                 │
                              └──────────┬──────────┬─────────────┘
                                         │          │
                                   pgvector DB   GitHub API
```

## Directory Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI webhook + health endpoint
│   ├── agents.py        # LangGraph workflow (4 nodes)
│   ├── celery_app.py    # Celery app instance
│   ├── tasks.py         # Celery task definitions
│   ├── database.py      # pgvector connection + similarity search
│   └── schemas.py       # Pydantic models
├── scripts/
│   └── ingest_docs.py   # RAG ingestion CLI
├── docs/                # Your ADR / engineering docs (seed data)
│   ├── adr-04-redis-caching.md
│   └── adr-02-pandas-vectorization.md
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Quick Start

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in:
#   GOOGLE_API_KEY, GITHUB_WEBHOOK_SECRET, GITHUB_TOKEN
```

### 2. Start all services

```bash
docker-compose up --build
```

| Service | Port  |
|---------|-------|
| FastAPI API | `8000` |
| PostgreSQL + pgvector | `5432` |
| Redis | `6379` |

### 3. Ingest your documentation

Place your ADRs, Confluence exports, or design patterns as `.md`/`.txt` files in the `docs/` directory, then run:

```bash
# Local (direct DB connection)
python -m scripts.ingest_docs --docs-dir docs/

# Inside Docker
docker-compose exec api python -m scripts.ingest_docs --docs-dir docs/
```

### 4. Register the GitHub Webhook

In your GitHub repo → **Settings → Webhooks → Add webhook**:

| Field | Value |
|-------|-------|
| Payload URL | `https://your-server.com/webhook/github` |
| Content type | `application/json` |
| Secret | *(match `GITHUB_WEBHOOK_SECRET` in .env)* |
| Events | `Pull requests` |

## Security

- **HMAC-SHA256** validation on all incoming webhook payloads
- **Data masking** pre-processor strips API keys, tokens, SSNs, and emails before sending to the LLM
- **Local embeddings** option (`EMBEDDING_PROVIDER=local`) keeps code vectors inside your private VPC

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe |
| `POST` | `/webhook/github` | GitHub PR webhook receiver |
| `GET` | `/docs` | Swagger UI (dev only) |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | — | Google AI API key for Gemini LLM + embeddings |
| `DATABASE_URL` | postgres://... | pgvector DB connection string |
| `REDIS_URL` | redis://... | Redis broker URL |
| `GITHUB_WEBHOOK_SECRET` | — | GitHub webhook HMAC secret |
| `GITHUB_TOKEN` | — | GitHub PAT for posting comments |
| `EMBEDDING_PROVIDER` | `gemini` | `gemini` (gemini-embedding-001) or `local` (sentence-transformers) |

## License

MIT
