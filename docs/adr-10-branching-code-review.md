# ADR-10: Git Branching & Code Review Strategy

**Status:** Accepted  
**Phase:** Planning / Development  
**Date:** 2025-01-20  
**Author:** Engineering Leadership

---

## Context

Multiple teams working on the same repo were merging directly to `main`, causing broken builds, untested features in production, and merge conflicts that blocked release.

## Decision

All repositories **MUST** follow **GitHub Flow** with enforced branch protection.

### Branch Structure

```
main          ← production-ready, always deployable
  └── feature/ACR-42-add-webhook-hmac
  └── fix/ACR-99-fix-embedding-dim-mismatch
  └── chore/update-dependencies
  └── docs/add-logging-adr
```

### Branch Naming Convention

```
{type}/{ticket-id}-{short-description}
```

| Type | When to Use |
|------|-------------|
| `feature/` | New functionality |
| `fix/` | Bug fixes |
| `hotfix/` | Urgent production fixes |
| `chore/` | Maintenance, tooling, non-functional |
| `docs/` | Documentation only |
| `refactor/` | Code restructuring, no behavior change |

### Branch Protection Rules (Enforced on `main`)

- ✅ Require pull request before merging
- ✅ Require **minimum 1 approving review**
- ✅ Require all CI status checks to pass
- ✅ Require branches to be up to date before merging
- ❌ Allow force pushes → **NEVER**
- ❌ Allow direct pushes → **NEVER**, including for admins

### Pull Request Rules

#### PR Size Limits

| Size | Lines Changed | Review Expected |
|------|---------------|----------------|
| XS | < 50 | Same day |
| S | 50–200 | Within 24h |
| M | 200–500 | Within 48h |
| L | > 500 | **Split into smaller PRs** |

PRs over **500 lines** will be returned for splitting without review.

#### PR Description Template

```markdown
## What
Brief description of what changed and why.

## How
Key implementation details reviewers should focus on.

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manually tested on staging

## Checklist
- [ ] No secrets in code
- [ ] Logging added for new code paths
- [ ] ADRs updated if architecture changed
```

### Code Review Standards

Reviewers **MUST** check:
- [ ] Business logic is correct
- [ ] Tests cover new code paths
- [ ] No ADR violations (the bot will help with this!)
- [ ] Error handling follows ADR-09
- [ ] No secrets or PII in code or logs

**Review comments should use the Conventional Comment format:**

```
suggestion: Consider using a set() here for O(1) lookup.
issue: This will throw KeyError if 'pr_id' is missing.
question: Why is this timeout set to 60s specifically?
nitpick: Trailing whitespace on line 42.
```

### Commit Message Convention (Conventional Commits)

```
{type}({scope}): {short description}

feat(webhook): add HMAC-SHA256 validation for GitHub events
fix(agent): handle empty diff gracefully
chore(deps): update langgraph to 0.0.15
docs(adr): add branching strategy ADR-10
```

## Consequences

- **Positive:** Clean history; traceable changes; no broken `main`.
- **Negative:** More overhead for urgent hotfixes — use `hotfix/` branch and expedited review.
