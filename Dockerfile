# ─── Stage 1: Builder ────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --upgrade pip

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt



# ─── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.11-slim

LABEL org.opencontainers.image.title="Ambient Code Reviewer" \
      org.opencontainers.image.description="Real-time AI agent for GitHub PR architectural reviews." \
      org.opencontainers.image.version="1.0.0"

# Copy installed packages from builder
COPY --from=builder /install /usr/local

WORKDIR /acr
COPY app/    ./app/
COPY scripts/ ./scripts/
COPY docs/    ./docs/
COPY .env.example .env.example

# Expose FastAPI port
EXPOSE 8000

# Default: run the FastAPI app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
