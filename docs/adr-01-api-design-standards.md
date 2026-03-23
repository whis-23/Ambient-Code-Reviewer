# ADR-01: REST API Design Standards

**Status:** Accepted  
**Phase:** Design  
**Date:** 2025-01-05  
**Author:** Platform Engineering Team

---

## Context

Inconsistent API design across services creates friction for frontend teams, increases integration bugs, and makes documentation harder to maintain. We need a unified standard.

## Decision

All internal and external REST APIs **MUST** follow these conventions.

### URL Structure

```
/api/v{N}/{resource}/{id}/{sub-resource}
```

| ✅ Correct | ❌ Incorrect |
|-----------|-------------|
| `GET /api/v1/users/42/orders` | `GET /api/getUserOrders?userId=42` |
| `POST /api/v1/orders` | `POST /api/createOrder` |
| `PATCH /api/v1/orders/7` | `PUT /api/updateOrder/7` |
| `DELETE /api/v1/orders/7` | `GET /api/deleteOrder?id=7` |

### HTTP Methods

| Action | Method | Idempotent |
|--------|--------|-----------|
| Read single | `GET` | ✅ |
| Read list | `GET` | ✅ |
| Create | `POST` | ❌ |
| Full replace | `PUT` | ✅ |
| Partial update | `PATCH` | ❌ |
| Delete | `DELETE` | ✅ |

### Response Shape

All responses **MUST** follow this envelope:

```json
{
  "data": { ... },
  "meta": { "page": 1, "total": 100 },
  "error": null
}
```

On error:
```json
{
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Field 'email' is required.",
    "details": [{ "field": "email", "issue": "missing" }]
  }
}
```

### Versioning

- Version via URL path: `/api/v1/`, `/api/v2/`
- **Never** version via headers or query params
- Old versions supported for **minimum 6 months** after deprecation notice

### Pagination

```
GET /api/v1/orders?page=2&page_size=20
```

Always include in `meta`: `page`, `page_size`, `total`, `total_pages`.

### Status Codes

| Situation | Code |
|-----------|------|
| Success (get/update) | `200` |
| Created | `201` |
| No content (delete) | `204` |
| Bad request | `400` |
| Unauthorized | `401` |
| Forbidden | `403` |
| Not found | `404` |
| Conflict | `409` |
| Server error | `500` |

## Consequences

- **Positive:** Predictable APIs reduce frontend integration errors.
- **Negative:** Migration effort for existing non-compliant endpoints.
