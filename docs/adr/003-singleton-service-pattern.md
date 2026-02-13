# ADR-003: Singleton Service Pattern

## Status

Accepted

## Context

The backend has ~15 service classes (TokenService, AuditLogger, CacheService, TenantCreditService, etc.) that need to be shared across API routes. Options considered:

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
- This pattern is a known technical debt item (see TECH_DEBT.md A-1) that may be revisited if testing complexity grows
