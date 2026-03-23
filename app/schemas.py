from typing import Optional, List
from pydantic import BaseModel, HttpUrl


class PRPayload(BaseModel):
    """Parsed GitHub webhook PR payload."""
    repo: str
    diff_url: str
    pr_id: int
    pr_number: int
    pr_title: Optional[str] = None
    base_branch: Optional[str] = "main"
    head_sha: Optional[str] = None


class ReviewRequest(BaseModel):
    """Internal task handed off to the LangGraph worker."""
    pr_data: PRPayload
    triggered_at: str


class RetrievedDoc(BaseModel):
    """A single document retrieved from pgvector."""
    content: str
    metadata: dict
    score: float


class ReviewResult(BaseModel):
    """Final review produced by the LLM critic."""
    pr_id: int
    critique: str
    docs_referenced: List[str]
    posted_to_github: bool = False
