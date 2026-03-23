"""
Celery task definitions for Ambient Code Reviewer.
"""
import logging
from .celery_app import celery_app
from .agents import run_review_workflow

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.trigger_review", bind=True, max_retries=3)
def trigger_review(self, pr_data: dict) -> dict:
    """
    Celery task: run the full LangGraph review workflow for a PR.
    Retries up to 3 times with exponential backoff on failure.
    """
    try:
        result = run_review_workflow(pr_data)
        logger.info("Review complete for PR #%s", pr_data.get("pr_number"))
        return result
    except Exception as exc:
        logger.error("Review failed: %s — retrying...", exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
