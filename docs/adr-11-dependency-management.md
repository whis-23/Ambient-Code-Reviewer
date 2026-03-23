# ADR-11: Dependency Management

**Status:** Accepted  
**Phase:** Development / Maintenance  
**Date:** 2025-04-10  
**Author:** Platform Engineering Team

---

## Context

Unpinned dependencies caused "works on my machine" failures when transitive packages updated overnight. Two production incidents in 2024 were traced to uncontrolled dependency upgrades.

## Decision

### Rule 1: All Dependencies Must Be Pinned

```text
# ✅ Correct — exact version pins
fastapi==0.109.0
pydantic==2.6.0

# ❌ Incorrect — floating versions cause non-deterministic builds
fastapi>=0.100.0
pydantic~=2.0
```

### Rule 2: Two-File Dependency Strategy

```
requirements.in        ← human-managed (top-level only, loose)
requirements.txt       ← machine-generated (all transitive, pinned)
```

```bash
# Generate pinned requirements
pip-compile requirements.in -o requirements.txt

# Upgrade a specific package
pip-compile --upgrade-package fastapi requirements.in
```

### Rule 3: Separate Dev Dependencies

```
requirements.in        ← production dependencies only
requirements-dev.in    ← dev/test tools (pytest, ruff, etc.)
```

```bash
# Install for development
pip install -r requirements.txt -r requirements-dev.txt
```

### Rule 4: Scheduled Dependency Updates

| Frequency | Action |
|-----------|--------|
| Weekly | Security patches (`pip-audit` in CI) |
| Monthly | Minor version upgrades |
| Quarterly | Major version upgrades (with testing) |

### Rule 5: Security Vulnerability Checks

```yaml
# In CI — runs on every PR
- name: Audit dependencies
  run: |
    pip install pip-audit
    pip-audit -r requirements.txt --fail-on HIGH
```

Any `HIGH` or `CRITICAL` CVE **must be patched before the PR can merge**.

### Rule 6: Adding a New Dependency Checklist

Before adding any package:
- [ ] Is this functionality available in the stdlib or an existing dep?
- [ ] What is the package's maintenance status? (last release, open issues)
- [ ] Does it have known CVEs? (`pip-audit`)
- [ ] What is the license? (GPL is incompatible with our proprietary code)
- [ ] What is the added size impact to the Docker image?

### Approved Package List for Common Tasks

| Task | Approved Package |
|------|-----------------|
| HTTP client | `httpx` |
| Data validation | `pydantic` |
| DB ORM | `sqlalchemy` |
| Task queue | `celery` |
| Retries | `tenacity` |
| Testing | `pytest` + `pytest-cov` |
| Linting | `ruff` |
| Env vars | `python-dotenv` |

Do not introduce alternative packages for these without an ADR.

## Consequences

- **Positive:** Reproducible builds; security visibility; no surprise upgrades.
- **Negative:** Manual maintenance of pinned files; requires regular update cycles.
