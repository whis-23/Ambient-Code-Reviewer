# ADR-07: Logging & Observability Standards

**Status:** Accepted  
**Phase:** Development / Operations  
**Date:** 2025-03-10  
**Author:** SRE Team

---

## Context

Inconsistent logging formats (plain strings, mixed levels, missing context) made debugging production incidents slow and costly. Correlation across services was impossible without standardization.

## Decision

All services **MUST** emit structured JSON logs with consistent fields.

### Log Format (Structured JSON)

```json
{
  "timestamp": "2025-03-01T12:00:00.123Z",
  "level": "ERROR",
  "service": "acr-api",
  "trace_id": "abc-123-xyz",
  "user_id": "usr_42",
  "message": "Failed to post GitHub comment",
  "error": "ConnectionTimeout",
  "duration_ms": 5032
}
```

### Python Implementation

```python
import structlog

logger = structlog.get_logger().bind(service="acr-api")

# ✅ Correct — structured, queryable
logger.error("github_comment_failed",
    pr_id=42, repo="org/repo", error=str(exc), duration_ms=elapsed)

# ❌ Incorrect — unstructured, unsearchable
logger.error(f"Failed to post comment for PR {pr_id}: {exc}")
```

### Log Levels — When to Use What

| Level | Use For |
|-------|---------|
| `DEBUG` | Detailed dev-only traces (disabled in prod) |
| `INFO` | Key business events (PR review started/completed) |
| `WARNING` | Recoverable issues (retry attempt, skipped event) |
| `ERROR` | Failures requiring investigation (task failed, API error) |
| `CRITICAL` | System-wide failure (DB down, service unresponsive) |

**Rule:** Never use `ERROR` for user-caused failures (bad input → use `WARNING`).

### Required Fields in Every Log

| Field | Required | Description |
|-------|----------|-------------|
| `timestamp` | ✅ | ISO 8601 UTC |
| `level` | ✅ | DEBUG/INFO/WARNING/ERROR/CRITICAL |
| `service` | ✅ | Service name |
| `message` | ✅ | Event slug (snake_case noun phrase) |
| `trace_id` | ✅ | Propagated from HTTP header `X-Trace-ID` |
| `duration_ms` | If timed operation | Execution time |
| `error` | If exception | Exception type + message |

### What Must NOT Be Logged

- Passwords, tokens, API keys — even partially
- Full request/response bodies containing PII
- Credit card numbers, SSNs, health data

### Metrics & Alerting

| Metric | Alert Threshold |
|--------|----------------|
| Error rate | > 1% of requests over 5 min |
| P95 response time | > 2 seconds |
| Task queue depth | > 500 pending |
| DB connection pool | > 80% utilization |

## Consequences

- **Positive:** Fast incident resolution; searchable logs in Grafana/CloudWatch.
- **Negative:** Structlog adds minor overhead vs. stdlib logging.
