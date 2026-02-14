# Nexus AI Command - Rollback Procedures

This document describes how to roll back each layer of the Nexus AI Command
stack when a deployment introduces a regression or critical bug.

---

## Table of Contents

1. [Frontend Rollback (Vercel)](#1-frontend-rollback-vercel)
2. [Backend Rollback (Docker Image)](#2-backend-rollback-docker-image)
3. [Database Rollback (Supabase SQL Migrations)](#3-database-rollback-supabase-sql-migrations)
4. [Feature Flag Rollback (Environment Variables)](#4-feature-flag-rollback-environment-variables)
5. [Full-Stack Rollback Checklist](#5-full-stack-rollback-checklist)

---

## 1. Frontend Rollback (Vercel)

Vercel keeps an immutable deployment for every push. Rolling back is
instant because no rebuild is required.

### Via the Vercel Dashboard

1. Open the Vercel project dashboard.
2. Navigate to **Deployments**.
3. Locate the last known-good deployment (identified by commit SHA or date).
4. Click the three-dot menu and select **Promote to Production**.
5. Verify the production URL serves the correct version.

### Via the Vercel CLI

```bash
# List recent deployments
vercel ls --prod

# Promote a specific deployment URL back to production
vercel promote <deployment-url> --yes
```

### Verification

- Open the production URL and confirm the UI renders correctly.
- Check the browser console for JavaScript errors.
- Run a quick smoke test against critical user flows (login, chat, settings).

---

## 2. Backend Rollback (Docker Image)

The backend is containerized and deployed as a Docker image. Each CI build
tags images with the Git commit SHA, so any previous version can be restored.

### Identify the target image

```bash
# List available image tags in the registry
docker images registry/nexus-backend --format "{{.Tag}}  {{.CreatedAt}}"

# Or query the remote registry
docker manifest inspect registry/nexus-backend:<previous-sha>
```

### Roll back the running service

```bash
# Pull the known-good image
docker pull registry/nexus-backend:<previous-sha>

# Stop the current container and start the previous version
docker stop nexus-backend-current
docker run -d --name nexus-backend-rollback \
  --env-file .env.production \
  -p 8000:8000 \
  registry/nexus-backend:<previous-sha>
```

If using Docker Compose or an orchestrator (e.g., Kubernetes), update the
image tag in the manifest and re-apply:

```bash
# Docker Compose
sed -i "s|nexus-backend:.*|nexus-backend:<previous-sha>|" docker-compose.prod.yml
docker compose -f docker-compose.prod.yml up -d

# Kubernetes
kubectl set image deployment/nexus-backend \
  nexus-backend=registry/nexus-backend:<previous-sha> \
  --record
kubectl rollout status deployment/nexus-backend
```

### Verification

- Hit the health endpoint: `curl https://api.example.com/health`
- Confirm the returned version or commit SHA matches the rollback target.
- Monitor application logs for startup errors.

---

## 3. Database Rollback (Supabase SQL Migrations)

This project uses **Supabase** for its database layer. Migrations are plain
SQL files managed through the Supabase CLI, not Alembic. Every migration
should have a corresponding "down" (rollback) script.

### Migration file conventions

```
supabase/migrations/
  20250101000000_create_users.sql
  20250101000001_add_feature_flags.sql
  ...
```

Each migration file should contain an `-- UP` section and a corresponding
`-- DOWN` section (or a separate `_down.sql` file) so rollbacks are explicit.

### Rolling back via the Supabase CLI

```bash
# Check which migrations have been applied
supabase migration list

# Roll back the most recent migration by running its DOWN script manually
supabase db execute --file supabase/migrations/<timestamp>_down.sql
```

### Rolling back manually via SQL

If the down script is embedded inside the migration file, extract and run it:

```sql
-- Example: reverse a column addition
ALTER TABLE public.conversations DROP COLUMN IF EXISTS metadata;

-- Example: reverse a table creation
DROP TABLE IF EXISTS public.audit_logs;
```

Connect to the Supabase SQL editor or use `psql`:

```bash
psql "$SUPABASE_DB_URL" -f supabase/migrations/<timestamp>_down.sql
```

### Important safeguards

- Always back up the database before running destructive rollback SQL.
- Test rollback scripts in the staging environment first.
- Coordinate database rollbacks with backend image rollbacks so the
  application code matches the schema.

---

## 4. Feature Flag Rollback (Environment Variables)

Several features are gated behind environment variables. Disabling a flag
instantly reverts behavior without redeploying code.

### Key feature flags

| Variable               | Purpose                                      | Safe default |
|------------------------|----------------------------------------------|--------------|
| `USE_LANGGRAPH_AGENT`  | Enables the LangGraph-based AI agent flow    | `false`      |
| `SENTRY_DSN`           | Sentry error tracking DSN; unset to disable  | (unset)      |
| `REDIS_URL`            | Redis connection for caching and rate limits  | (unset)      |

### Disabling a feature

**Backend (Docker / hosting platform):**

```bash
# Disable LangGraph agent, fall back to basic agent
export USE_LANGGRAPH_AGENT=false

# Disable Sentry reporting
unset SENTRY_DSN

# Disable Redis-backed caching (falls back to in-memory)
unset REDIS_URL
```

After changing environment variables, restart the backend process:

```bash
docker restart nexus-backend
# or, if using a PaaS:
# heroku config:set USE_LANGGRAPH_AGENT=false
# railway variables set USE_LANGGRAPH_AGENT=false
```

**Frontend (Vercel environment variables):**

1. Go to the Vercel project settings.
2. Navigate to **Environment Variables**.
3. Update or remove the variable for the target environment (Production,
   Preview, or Development).
4. Trigger a redeployment for the change to take effect.

### Verification

- Confirm the application starts without errors after the variable change.
- Test the affected feature to ensure it is properly disabled or reverted.
- Check logs to confirm the flag value was read correctly at startup.

---

## 5. Full-Stack Rollback Checklist

Use this checklist when a deployment must be fully reverted.

- [ ] **Identify the last known-good state** -- note the commit SHA and
      deployment timestamp for both frontend and backend.
- [ ] **Roll back the frontend** via Vercel promotion (Section 1).
- [ ] **Roll back the backend** Docker image to the previous SHA (Section 2).
- [ ] **Roll back the database** if schema migrations were included in the
      faulty release (Section 3).
- [ ] **Disable feature flags** for any newly introduced features that may
      be causing issues (Section 4).
- [ ] **Verify health** across all services (API health endpoint, frontend
      smoke test, Sentry for new errors).
- [ ] **Notify the team** in the incident channel with the rollback summary.
- [ ] **Create a post-mortem** documenting the root cause, timeline, and
      corrective actions.
