# ADR-05: Database Schema Migrations

**Status:** Accepted  
**Phase:** Development / Deployment  
**Date:** 2025-02-15  
**Author:** Backend Guild

---

## Context

Manual `ALTER TABLE` statements run by developers directly on production databases have caused data loss, downtime, and schema drift. A controlled, versioned migration process is required.

## Decision

All schema changes **MUST** go through **Alembic** migrations. Direct DDL on production is strictly prohibited.

### Migration Rules

#### 1. Every schema change = one migration file

```bash
# Generate a new migration
alembic revision --autogenerate -m "add_index_to_orders_created_at"
```

Never batch unrelated changes into one migration.

#### 2. Migrations must be reversible

Every migration **MUST** implement both `upgrade()` and `downgrade()`:

```python
# ✅ Correct
def upgrade():
    op.add_column("users", sa.Column("last_login", sa.DateTime, nullable=True))

def downgrade():
    op.drop_column("users", "last_login")

# ❌ Incorrect — no downgrade path
def downgrade():
    pass
```

#### 3. Non-breaking changes only in production

For production databases, all migrations **MUST** be backward-compatible:

| ✅ Safe | ❌ Unsafe (requires maintenance window) |
|--------|---------------------------------------|
| `ADD COLUMN` (nullable or with default) | `DROP COLUMN` immediately |
| `CREATE INDEX CONCURRENTLY` | `ALTER COLUMN` (type change) |
| `CREATE TABLE` | `RENAME COLUMN` |
| `ADD CONSTRAINT` (deferred) | `DROP TABLE` |

#### 4. Zero-downtime column renaming

```sql
-- Step 1 (deploy): Add new column, write to both
ALTER TABLE orders ADD COLUMN customer_id INT;

-- Step 2 (backfill): Copy data
UPDATE orders SET customer_id = user_id;

-- Step 3 (next deploy): Remove old column
ALTER TABLE orders DROP COLUMN user_id;
```

#### 5. Run migrations in CI before deployment

```yaml
# In CI pipeline — always run before app startup
- name: Run migrations
  run: alembic upgrade head
```

### Migration Review Checklist

Before merging any migration PR:
- [ ] `downgrade()` is implemented and tested
- [ ] `CREATE INDEX` uses `CONCURRENTLY` flag
- [ ] No `DROP COLUMN` without a deprecation window
- [ ] Migration runs in < 30 seconds on production data size
- [ ] Tested on a production-snapshot database

## Consequences

- **Positive:** Full audit trail of schema history; safe rollbacks.
- **Negative:** Migration PRs require additional review discipline.
