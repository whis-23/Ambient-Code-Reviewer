# ADR-03: Testing Strategy & Coverage Requirements

**Status:** Accepted  
**Phase:** Development / QA  
**Date:** 2025-02-01  
**Author:** QA Guild

---

## Context

Services were shipped with ad-hoc test coverage, causing frequent regressions in production. We need a standardized testing pyramid with enforceable thresholds.

## Decision

### The Testing Pyramid

```
          /\
         /  \  E2E Tests (Playwright / Cypress)
        /    \  — Happy path only, max 10 per service
       /──────\
      / Integ. \  Integration Tests (pytest + testcontainers)
     /  Tests   \  — All API endpoints, DB interactions
    /────────────\
   /  Unit Tests  \  — All business logic, pure functions
  /────────────────\
```

### Coverage Thresholds (enforced in CI)

| Layer | Minimum Coverage |
|-------|-----------------|
| Unit tests | **80%** line coverage |
| Integration tests | All API routes exercised |
| E2E tests | Top 3 user flows |

```bash
# Enforced in CI — build fails below 80%
pytest --cov=app --cov-fail-under=80
```

### Test File Naming

```
app/
  services/
    order_service.py
tests/
  unit/
    test_order_service.py      # mirrors src structure
  integration/
    test_order_api.py
  e2e/
    test_checkout_flow.py
```

### Unit Test Rules

```python
# ✅ Correct — isolated, no I/O, mocked dependencies
def test_calculate_discount_for_premium_user():
    user = User(tier="premium")
    assert calculate_discount(user, amount=100) == 20.0

# ❌ Incorrect — hits real DB in a unit test
def test_get_user():
    user = db.session.get(User, 1)   # NEVER in unit tests
    assert user.name == "Alice"
```

### Integration Test Rules

- Use `testcontainers` to spin up a real PostgreSQL and Redis
- Each test gets a **fresh transaction** — rolled back after the test
- Never share state between tests

```python
@pytest.fixture(scope="function")
def db_session(pg_container):
    with transaction() as session:
        yield session
        session.rollback()   # Always clean up
```

### What Must Be Tested

| Component | Required Tests |
|-----------|---------------|
| API endpoints | All status codes (200, 400, 401, 404, 500) |
| Business logic | All branches (happy + sad paths) |
| Background tasks | Mock queue; assert task called with correct args |
| DB queries | Integration tests with real DB |
| Auth/permissions | Unauthorized access returns 401/403 |

## Consequences

- **Positive:** Prevents regressions; enables confident refactoring.
- **Negative:** Initial investment to write tests for existing code.
