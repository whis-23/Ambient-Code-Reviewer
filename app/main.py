"""
FastAPI entrypoint for the Ambient Code Reviewer.

Endpoints:
  GET  /health                — Liveness probe
  POST /webhook/github        — Receives GitHub PR webhook events
"""
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Header
from dotenv import load_dotenv

from .agents import run_review_workflow
from .database import create_schema
from .tasks import trigger_review

load_dotenv()
logger = logging.getLogger(__name__)

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
APP_ENV        = os.getenv("APP_ENV", "development")

app = FastAPI(
    title="Ambient Code Reviewer",
    description="Real-time AI agent for GitHub PR architectural reviews.",
    version="1.0.0",
)


# ─────────────────── Startup ─────────────────────────────── #
@app.on_event("startup")
async def on_startup():
    """Ensure pgvector schema exists on startup."""
    try:
        create_schema()
        logger.info("Database schema ready.")
    except Exception as exc:
        logger.warning("Schema init skipped (DB may not be ready): %s", exc)


# ─────────────────── Health ───────────────────────────────── #
@app.get("/health", tags=["ops"])
async def health():
    return {"status": "ok", "env": APP_ENV}


# ─────────────────── HMAC Verification ───────────────────── #
def _verify_github_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """
    Validate GitHub's HMAC-SHA256 webhook signature.
    Header format: 'sha256=<hex_digest>'
    """
    if not WEBHOOK_SECRET:
        # Skip validation in dev if secret not configured
        logger.warning("GITHUB_WEBHOOK_SECRET not set — skipping HMAC check.")
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        WEBHOOK_SECRET.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)


# ─────────────────── Webhook Handler ─────────────────────── #
@app.post("/webhook/github", tags=["webhook"])
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
):
    """
    Receives GitHub webhook events.
    Only processes `pull_request` events with action `opened` or `synchronize`.
    """
    raw_body = await request.body()

    # ── HMAC validation ──────────────────────────────────── #
    if not _verify_github_signature(raw_body, x_hub_signature_256):
        logger.warning("Invalid webhook signature received.")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # ── Event filtering ──────────────────────────────────── #
    if x_github_event != "pull_request":
        logger.info("Ignored event type: %s", x_github_event)
        return {"status": "ignored", "reason": f"event={x_github_event}"}

    payload = json.loads(raw_body)
    action  = payload.get("action", "")

    if action not in ("opened", "synchronize", "reopened"):
        logger.info("Ignored PR action: %s", action)
        return {"status": "ignored", "reason": f"action={action}"}

    # ── Build PR data ─────────────────────────────────────── #
    pr      = payload["pull_request"]
    pr_data = {
        "repo":       payload["repository"]["full_name"],
        "diff_url":   pr["diff_url"],
        "pr_id":      pr["id"],
        "pr_number":  pr["number"],
        "pr_title":   pr.get("title"),
        "base_branch": pr["base"]["ref"],
        "head_sha":   pr["head"]["sha"],
    }

    logger.info(
        "Queuing review for PR #%s in %s", pr_data["pr_number"], pr_data["repo"]
    )

    # ── Dispatch to Celery worker ─────────────────────────── #
    trigger_review.delay(pr_data)

    return {
        "status":     "processing",
        "pr_id":      pr_data["pr_id"],
        "pr_number":  pr_data["pr_number"],
        "queued_at":  datetime.now(timezone.utc).isoformat(),
    }
