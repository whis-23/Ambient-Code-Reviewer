# ADR-12: Deployment & Release Strategy

**Status:** Accepted  
**Phase:** Deployment / Operations  
**Date:** 2025-04-20  
**Author:** DevOps / SRE Team

---

## Context

Big-bang deployments were causing 10–30 minute outages during releases. There was no standard rollback procedure, and rollbacks themselves caused secondary incidents due to DB schema incompatibilities.

## Decision

### Deployment Strategy: Blue/Green for APIs, Canary for Workers

#### API Services → Blue/Green Deployment

```
                    ┌─────────────────┐
                    │   Load Balancer  │
                    └────────┬────────┘
            ┌───────────────┤
            │               │
    ┌───────▼──────┐  ┌─────▼────────┐
    │   Blue (live) │  │ Green (new)  │
    │   v1.4.2      │  │  v1.4.3      │
    └──────────────┘  └──────────────┘

Step 1: Deploy v1.4.3 to Green (no traffic)
Step 2: Run smoke tests on Green
Step 3: Switch LB → 100% traffic to Green
Step 4: Keep Blue for 30 min (instant rollback)
Step 5: Decommission Blue
```

#### Celery Workers → Rolling Deployment

```bash
# Graceful rolling restart — workers finish current tasks before stopping
celery -A app.celery_app control shutdown
# New workers start automatically via docker-compose
docker-compose up -d --no-deps worker
```

### Release Checklist

Before any production deployment:

- [ ] All CI checks passing on `main`
- [ ] Deployed to staging and smoke-tested
- [ ] DB migrations have been verified (see ADR-05)
- [ ] Rollback plan documented
- [ ] On-call engineer notified
- [ ] Deploy during low-traffic window (avoid 9am–11am, 5pm–7pm local)

### Rollback Procedure

| Time Since Deploy | Action |
|-------------------|--------|
| < 30 min | Switch LB back to Blue (< 60 second rollback) |
| 30–120 min | Redeploy previous Docker image tag |
| > 120 min | Emergency patch with `hotfix/` branch; full CI |

```bash
# Immediate rollback — previous image is always tagged
docker pull acr-api:previous
docker tag acr-api:previous acr-api:live
docker-compose up -d api
```

### Environment Promotion Gates

```
feature branch
    │ ← CI passes
    ▼
main
    │ ← Auto-deploy
    ▼
Staging        ← Smoke tests + QA sign-off (max 24h)
    │ ← Manual approval
    ▼
Production     ← Blue/Green deploy during approved window
```

### Health Check Requirements

Every service **MUST** expose:

```python
# Required endpoint
@app.get("/health")
def health():
    return {"status": "ok", "version": os.getenv("APP_VERSION", "unknown")}

# Optional — deep health (checks DB, Redis)
@app.get("/health/ready")
def readiness():
    db_ok = check_db_connection()
    redis_ok = check_redis_connection()
    return {"db": db_ok, "redis": redis_ok, "ready": db_ok and redis_ok}
```

Docker/Kubernetes uses `/health` for liveness, `/health/ready` for readiness.

### Post-Deployment Monitoring (15-minute rule)

After every production deployment, actively monitor for 15 minutes:

| Metric | Alert Threshold |
|--------|----------------|
| Error rate | Spike > 2× baseline |
| P95 latency | > 2 seconds |
| Task failure rate | > 5% |
| Memory usage | > 85% |

If any threshold is breached → **immediate rollback**, investigate after system is stable.

## Consequences

- **Positive:** Zero-downtime deployments; fast, safe rollbacks.
- **Negative:** Requires running two environments simultaneously during Blue/Green switch.
