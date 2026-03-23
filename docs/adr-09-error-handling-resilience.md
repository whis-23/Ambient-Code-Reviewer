# ADR-09: Error Handling & Resilience Patterns

**Status:** Accepted  
**Phase:** Development  
**Date:** 2025-04-01  
**Author:** Backend Guild

---

## Context

Unhandled exceptions caused silent failures in background workers, cascading errors when downstream services were slow, and user-facing 500 errors with no useful information.

## Decision

### Rule 1: Never Swallow Exceptions Silently

```python
# ✅ Correct — log and re-raise or handle explicitly
try:
    result = call_external_api()
except httpx.TimeoutException as exc:
    logger.warning("api_timeout", service="github", error=str(exc))
    raise ServiceUnavailableError("GitHub API timed out") from exc

# ❌ Incorrect — silent failure, impossible to debug
try:
    result = call_external_api()
except Exception:
    pass
```

### Rule 2: Retry with Exponential Backoff

External API calls and DB operations **MUST** use retries:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True
)
def call_github_api(url: str) -> dict:
    resp = httpx.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()
```

| Attempt | Wait Before |
|---------|------------|
| 1st retry | 2 seconds |
| 2nd retry | 4 seconds |
| 3rd retry | 8 seconds |
| Give up | Raise exception |

### Rule 3: Circuit Breaker for External Services

For services called > 100 times/minute, implement a circuit breaker:

```python
# Using `pybreaker`
import pybreaker

github_breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60)

@github_breaker
def post_github_comment(url, body):
    ...
```

States:
- **Closed** (normal): requests pass through
- **Open** (failing): requests immediately rejected for `reset_timeout` seconds
- **Half-open**: one test request to check recovery

### Rule 4: Structured Exception Hierarchy

```python
# Base exception
class ACRException(Exception):
    pass

# Specific exceptions
class DiffFetchError(ACRException):
    """Failed to fetch PR diff from GitHub."""

class EmbeddingError(ACRException):
    """Failed to generate embedding vector."""

class ReviewPostError(ACRException):
    """Failed to post review comment to GitHub."""
```

Never raise bare `Exception` — always use domain-specific exceptions.

### Rule 5: Graceful Degradation

If a non-critical step fails, continue with reduced functionality:

```python
def retrieve_context(state):
    try:
        return {"retrieved_context": query_pgvector(diff)}
    except Exception as exc:
        logger.warning("pgvector_unavailable", error=str(exc))
        # Degrade gracefully — review without RAG context
        return {"retrieved_context": []}
```

### Rule 6: Timeout on All External Calls

```python
# ✅ Always set timeouts
httpx.get(url, timeout=httpx.Timeout(connect=5, read=30, write=10))

# ❌ Never allow indefinite blocking
httpx.get(url)   # Can hang forever
```

| External Service | Connect Timeout | Read Timeout |
|-----------------|----------------|-------------|
| GitHub API | 5s | 15s |
| Gemini API | 5s | 60s |
| PostgreSQL | 3s | 30s |

## Consequences

- **Positive:** Resilient system; partial failures don't cause total outages.
- **Negative:** More complex code; requires discipline to maintain exception hierarchy.
