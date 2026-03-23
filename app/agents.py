


import os
import re
import json
import logging
from typing import TypedDict, List, Annotated

import httpx
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from .database import query_similar_docs

load_dotenv()
logger = logging.getLogger(__name__)

# Configuration

GOOGLE_API_KEY      = os.getenv("GOOGLE_API_KEY", "")
GITHUB_TOKEN        = os.getenv("GITHUB_TOKEN", "")
EMBEDDING_PROVIDER  = os.getenv("EMBEDDING_PROVIDER", "gemini")

# Regex patterns for data masking (applied BEFORE sending content to LLM)
_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|password|token|auth)\s*[:=]\s*\S+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),              # AWS Access Key IDs
    re.compile(r"sk-[a-zA-Z0-9]{32,}"),            # OpenAI secret keys
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),            # GitHub PATs
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),          # SSNs
    re.compile(r"\b[\w._%+\-]+@[\w.\-]+\.\w{2,}\b"),  # Email addresses
]

REDACTED = "[REDACTED]"


# State Definition

class AgentState(TypedDict):
    pr_data:            dict            # {repo, diff_url, pr_id, pr_number, ...}
    diff_content:       str             # Raw diff text (fetched from GitHub)
    masked_diff:        str             # Diff after PII / secret scrubbing
    retrieved_context:  List[str]       # Top-k doc snippets from pgvector
    critique:           str             # LLM-generated architectural feedback
    posted_to_github:   bool


# Helper Functions

def _mask_secrets(text: str) -> str:
    for pattern in _SECRET_PATTERNS:

        text = pattern.sub(REDACTED, text)
    return text


def _fetch_diff(diff_url: str) -> str:
    headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

    try:
        # GitHub often redirects diff URLs to patch-diff.githubusercontent.com
        resp = httpx.get(diff_url, headers=headers, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        logger.warning("Failed to fetch diff from %s: %s", diff_url, exc)
        return ""



def _embed(text: str) -> List[float]:
    if not text.strip():

        # Return a zero vector if content is empty
        return [0.0] * 768
    import google.generativeai as genai
    genai.configure(api_key=GOOGLE_API_KEY)
    result = genai.embed_content(
        model="models/gemini-embedding-001",
        content=text[:8000],
        task_type="retrieval_query",
        output_dimensionality=768,
    )
    return result["embedding"]




def _call_llm(prompt: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash-lite",

        system_instruction=(
            "You are a Senior Software Architect performing a code review. "
            "Your goal is to identify violations of the team's internal architectural "
            "decisions (ADRs), design patterns, and best practices. "
            "Be concise, specific, and always cite the relevant ADR or doc."
        ),
    )
    resp = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(temperature=0.2),
    )
    return resp.text.strip()


def _post_github_comment(repo: str, pr_number: int, body: str) -> bool:
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        resp = httpx.post(url, headers=headers, json={"body": body}, timeout=20)
        resp.raise_for_status()
        logger.info("Posted PR comment → %s#%s", repo, pr_number)
        return True
    except Exception as exc:
        logger.error("Failed to post GitHub comment: %s", exc)
        return False


# Graph Nodes

def fetch_and_mask_diff(state: AgentState) -> dict:
    diff_url = state["pr_data"]["diff_url"]

    raw_diff = _fetch_diff(diff_url)
    masked   = _mask_secrets(raw_diff)
    logger.info("Diff fetched (%d chars). Masked version: %d chars.", len(raw_diff), len(masked))
    return {"diff_content": raw_diff, "masked_diff": masked}


def retrieve_context(state: AgentState) -> dict:
    diff_snippet = state["masked_diff"][:4096]

    embedding = _embed(diff_snippet)
    results   = query_similar_docs(embedding, top_k=5)

    snippets = []
    for content, metadata, score in results:
        title = metadata.get("title", "Untitled Doc")
        snippets.append(f"[{title} | score={score:.3f}]\n{content}")

    logger.info("Retrieved %d context docs from pgvector.", len(snippets))
    return {"retrieved_context": snippets}


def analyze_code(state: AgentState) -> dict:
    context_block = "\n\n---\n\n".join(state["retrieved_context"])

    if not context_block:
        context_block = "(No relevant ADRs or docs found in the knowledge base.)"

    prompt = f"""## Pull Request Diff
```diff
{state['masked_diff'][:6000]}
```

## Relevant Internal Documentation
{context_block}

## Task
Review the PR diff against the internal documentation above.
List any architectural concerns, ADR violations, or improvement suggestions.
Format your response as a GitHub Markdown comment with clear headings."""

    critique = _call_llm(prompt)
    logger.info("LLM critique generated (%d chars).", len(critique))
    return {"critique": critique}


def post_comment(state: AgentState) -> dict:
    pr    = state["pr_data"]

    body  = (
        "## 🤖 Ambient Code Reviewer\n\n"
        + state["critique"]
        + "\n\n---\n*Generated by Ambient Code Reviewer · Powered by LangGraph + pgvector*"
    )
    ok = _post_github_comment(
        repo=pr["repo"],
        pr_number=pr["pr_number"],
        body=body,
    )
    return {"posted_to_github": ok}


# Graph Construction

def build_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("fetcher",   fetch_and_mask_diff)
    workflow.add_node("retriever", retrieve_context)
    workflow.add_node("analyzer",  analyze_code)
    workflow.add_node("poster",    post_comment)

    workflow.set_entry_point("fetcher")
    workflow.add_edge("fetcher",   "retriever")
    workflow.add_edge("retriever", "analyzer")
    workflow.add_edge("analyzer",  "poster")
    workflow.add_edge("poster",    END)

    return workflow.compile()


# Compiled graph — imported by Celery task
app = build_graph()


def run_review_workflow(pr_data: dict) -> dict:
    initial_state: AgentState = {

        "pr_data":           pr_data,
        "diff_content":      "",
        "masked_diff":       "",
        "retrieved_context": [],
        "critique":          "",
        "posted_to_github":  False,
    }
    result = app.invoke(initial_state)
    logger.info(
        "Workflow complete. PR=%s posted=%s",
        pr_data.get("pr_id"),
        result.get("posted_to_github"),
    )
    return result
