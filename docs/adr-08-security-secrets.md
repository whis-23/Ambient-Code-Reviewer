# ADR-08: Security & Secrets Management

**Status:** Accepted  
**Phase:** All Phases  
**Date:** 2025-03-15  
**Author:** Security Team

---

## Context

Hardcoded secrets were found in source code and Docker images during a security audit in Q1 2025. Several leaked GitHub tokens were used to push malicious commits to public forks.

## Decision

### Rule 1: Zero Secrets in Code

No secret, credential, API key, or token of any kind may appear in:
- Source code
- Dockerfile or docker-compose files
- Commit history (even if later deleted)
- Log output

```python
# ✅ Correct — always from environment
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not set")

# ❌ CRITICAL VIOLATION — immediate revocation required
API_KEY = "AIzaSyD-abc123..."
```

### Rule 2: Secrets Rotation Schedule

| Secret Type | Max Age | Rotation Trigger |
|-------------|---------|-----------------|
| API Keys (LLM, external) | 90 days | Any team member departure |
| Webhook secrets | 180 days | Any breach or suspicion |
| GitHub PATs | 90 days | Scope change or departure |
| DB passwords | 180 days | Any breach |
| JWT signing keys | 30 days | Always short-lived |

### Rule 3: Principle of Least Privilege

Each service account / API key **MUST** have only the permissions it needs:

| Service | Required GitHub Scopes |
|---------|----------------------|
| Webhook listener | None (receive only) |
| Comment poster | `repo` → `issues:write` only |
| Code reader (diff) | `repo:read` |

Never use a personal admin token as a service credential.

### Rule 4: Secret Detection in CI

Pre-commit hooks and CI **MUST** scan for secrets:

```yaml
# .github/workflows/security.yml
- name: Scan for secrets
  uses: trufflesecurity/trufflehog@main
  with:
    path: ./
    base: main
    head: HEAD
```

Local pre-commit:
```bash
pip install detect-secrets
detect-secrets scan > .secrets.baseline
```

### Rule 5: Input Validation & Injection Prevention

```python
# ✅ Correct — parameterized queries
cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))

# ❌ Incorrect — SQL injection vulnerability
cur.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

- All user-supplied input **MUST** be validated with Pydantic before processing
- File paths from user input must be resolved and checked against an allowlist
- Webhook HMAC signatures **MUST** be validated before processing payload

### Rule 6: Dependency Security

```bash
# Run weekly in CI
pip-audit --requirement requirements.txt

# Fail CI on HIGH or CRITICAL CVEs
pip-audit --requirement requirements.txt --vulnerability-service pypi \
  --fail-on HIGH
```

## Incident Response

If a secret is accidentally committed:
1. **Immediately revoke** the secret at the provider (GitHub, Google AI, etc.)
2. Rotate all secrets in the same credential family
3. Use `git filter-repo` to purge from history
4. File an internal security report within 24 hours

## Consequences

- **Positive:** Prevents credential exposure incidents.
- **Negative:** Secret rotation requires coordination across deployment environments.
