# ADR-06: CI/CD Pipeline Standards

**Status:** Accepted  
**Phase:** CI/CD  
**Date:** 2025-03-01  
**Author:** DevOps Team

---

## Context

Teams were using inconsistent CI setups — some ran only linting, others had no automated tests, and deployments were done manually via SSH. This created unpredictable release quality.

## Decision

All services **MUST** use the following standardized pipeline via **GitHub Actions**.

### Pipeline Stages (in order)

```
PR Opened / Updated
        │
        ▼
┌───────────────┐
│   1. Lint     │  ruff / eslint / prettier — fail fast
└──────┬────────┘
       │
       ▼
┌───────────────┐
│  2. Test      │  pytest / jest — unit + integration
│  (80% cov)   │
└──────┬────────┘
       │
       ▼
┌───────────────┐
│  3. Build     │  docker build — multi-stage
└──────┬────────┘
       │
       ▼
┌───────────────┐     ← PR merged to main
│  4. Deploy    │
│   Staging     │
└──────┬────────┘
       │ (manual approval gate)
       ▼
┌───────────────┐
│  5. Deploy    │
│  Production   │
└───────────────┘
```

### Required GitHub Actions Workflow File

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install ruff && ruff check .

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: ankane/pgvector
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: pytest --cov=app --cov-fail-under=80

  build:
    needs: [lint, test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t acr:${{ github.sha }} .
```

### Deployment Rules

| Branch | Environment | Gate |
|--------|-------------|------|
| `feature/*` | None | — |
| `main` | Staging | Automatic after tests pass |
| `main` | Production | **Manual approval required** |

### Prohibited Practices

- ❌ Merging to `main` without passing CI
- ❌ Bypassing branch protection rules even for "hotfixes"
- ❌ Deploying directly to production without staging validation
- ❌ Storing secrets in workflow files (use GitHub Secrets)

### Rollback Procedure

```bash
# Immediate rollback — redeploy previous image tag
docker pull acr:<previous-sha>
docker-compose up -d api worker
```

Always retain the last **3 production image tags** in the registry.

## Consequences

- **Positive:** Consistent release quality; traceable deployments.
- **Negative:** Longer feedback loop vs. direct push to main.
