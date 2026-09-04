# ADR-003: Singleton Service Pattern

## Status

Accepted for stateless service facades; partially superseded by lifecycle and domain governance on 2026-09-04.

## Context

At the time of this decision, the backend had a smaller set of service classes (TokenService, AuditLogger, CacheService, TenantCreditService, etc.) that needed to be shared across API routes. Options considered:

1. **Dependency injection (FastAPI Depends)** — create per-request instances
2. **Module-level singletons** — instantiate once at import time
3. **Application state (`app.state`)** — attach to FastAPI app instance
4. **DI container (dependency-injector)** — third-party DI framework

## Decision

We use **module-level singleton instances** for all services:

```python
# At bottom of each service module
tenant_credit_service = TenantCreditService()
```

Services are imported directly where needed:

```python
from app.services.tenant_credit_service import tenant_credit_service
```

## Consequences

### Positive

- Simple and idiomatic Python — no framework overhead
- Services are initialized once and shared across all requests
- In-memory caches (rate limits, credit cache) persist across requests
- Easy to import and use from anywhere in the codebase

### Negative

- Harder to mock in tests — must patch the module-level instance
- Services initialized at import time may fail if dependencies aren't ready
- No lifecycle management (init/shutdown) without explicit wiring in lifespan
- Circular import risk when services depend on each other

### Neutral

- Each service manages its own database client reference (passed as `db` parameter)
- Background tasks (monitoring) are wired in `main.py` lifespan, not in the services
- This pattern remains a tracked debt when mutable process-local state or import-time side effects make testing and multi-worker execution unsafe.

## Current Implementation Note

Module-level instances are still common, but this ADR does not authorize background schedulers, locks or tenant state to live only in process memory. Startup and shutdown belong in `nexus_backend/app/startup` and FastAPI lifespan; distributed coordination belongs in Redis/PostgreSQL/Celery; gradual ownership is recorded in `nexus_backend/app/domains/__init__.py`. See `docs/handbook/09-known-debt.md` for the current debt statement.
