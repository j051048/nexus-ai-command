# Private Deployment PgBouncer Guide

Use this guide when each customer receives an isolated local deployment. The goal is to keep PostgreSQL connection usage predictable when FastAPI, Celery workers, schedulers, and background Agent jobs run on the same customer infrastructure.

## Recommended Defaults

| Setting | Small customer | Notes |
| --- | ---: | --- |
| `pool_mode` | `transaction` | Best fit for Supabase/PostgREST-style short queries. |
| `default_pool_size` | `20` | Enough for 20-50 users plus background jobs. |
| `min_pool_size` | `5` | Keeps warm connections without exhausting Postgres. |
| `reserve_pool_size` | `5` | Absorbs approval bursts and scheduled jobs. |
| `max_client_conn` | `200` | Allows browser/API bursts while Postgres stays capped. |
| `server_idle_timeout` | `60` | Releases idle server connections quickly. |
| `query_timeout` | `30000` | Prevents stuck tenant queries from pinning the pool. |

## Environment Contract

Set the backend to use the pooler connection string for server-side database access:

```bash
DATABASE_URL=postgresql://app_user:***@pgbouncer:6432/postgres
SUPABASE_DB_POOLER_URL=postgresql://app_user:***@pgbouncer:6432/postgres
POSTGRES_POOL_MODE=transaction
POSTGRES_POOL_SIZE=20
POSTGRES_MAX_OVERFLOW=10
```

For Supabase-hosted deployments, prefer Supabase's transaction pooler URL. For fully offline deployments, run PgBouncer beside Postgres in Docker Compose or the customer's Kubernetes namespace.

## Guardrails

1. FastAPI request handlers should use short-lived DB calls and avoid long transactions.
2. Celery concurrency must be sized against the pool, not against CPU only.
3. Long ETL or vector indexing jobs should use a separate worker queue with lower concurrency.
4. Migration jobs should connect directly to Postgres, not through transaction pooling.
5. `/health/ready` should fail if Redis or the database pool is unavailable.
