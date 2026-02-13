# Disaster Recovery Plan

## Overview

This document describes the disaster recovery (DR) procedures for Nexus AI Command.
It covers backup strategies, recovery procedures, and RTO/RPO targets.

## Architecture Summary

| Component       | Technology       | Backup Method                  |
|-----------------|------------------|--------------------------------|
| Database        | Supabase (Postgres) | Supabase automatic backups + pg_dump |
| File Storage    | Supabase Storage | Supabase Storage replication   |
| Vector Store    | pgvector         | Included in Postgres backup    |
| Application     | FastAPI + Next.js | Git repository + CI/CD         |
| Configuration   | Environment vars | Encrypted vault / .env backup  |

## Recovery Objectives

| Metric | Target   | Notes                              |
|--------|----------|------------------------------------|
| RPO    | 1 hour   | Maximum acceptable data loss       |
| RTO    | 4 hours  | Maximum acceptable downtime        |

## Backup Strategy

### 1. Supabase Automatic Backups

Supabase Pro plans include automatic daily backups with 7-day retention.
Verify backup status in Supabase Dashboard > Settings > Database > Backups.

### 2. Manual pg_dump Backups

For additional protection, run scheduled `pg_dump` exports:

```bash
# Daily backup via cron or CI
./scripts/backup_supabase.sh
```

Schedule recommendation:
- **Production**: Every 6 hours
- **Staging**: Daily

### 3. Application Code

All application code is stored in Git. Ensure:
- All branches are pushed to remote (GitHub)
- CI/CD pipeline can redeploy from any tagged commit
- Database migrations are version-controlled in `supabase/migrations/`

### 4. Environment Configuration

- Store all secrets in a secure vault (e.g., GitHub Secrets, AWS Secrets Manager)
- Maintain an encrypted backup of `.env.production` offline
- Document all required environment variables in `.env.example`

## Recovery Procedures

### Scenario 1: Database Corruption / Data Loss

1. **Assess** — Identify scope of data loss via audit logs
2. **Stop** — Halt application traffic (set maintenance mode)
3. **Restore** — Use Supabase Dashboard to restore from the latest clean backup, OR:
   ```bash
   # Restore from pg_dump backup
   psql $DATABASE_URL < backups/nexus_backup_YYYYMMDD_HHMMSS.sql
   ```
4. **Verify** — Run data integrity checks
5. **Resume** — Remove maintenance mode, monitor closely

### Scenario 2: Application Failure

1. **Identify** — Check application logs and health endpoints
2. **Rollback** — Deploy previous known-good version:
   ```bash
   git checkout <last-good-tag>
   # Trigger deployment via CI/CD
   ```
3. **Verify** — Confirm health check passes at `/api/health`

### Scenario 3: Complete Infrastructure Loss

1. **Provision** — Create new Supabase project (or restore from backup)
2. **Migrate** — Run all database migrations:
   ```bash
   supabase db push
   ```
3. **Restore Data** — Import latest pg_dump backup
4. **Deploy** — Deploy application from Git main branch
5. **Configure** — Set all environment variables from secure vault
6. **Verify** — Run full integration test suite

### Scenario 4: Security Breach

1. **Isolate** — Revoke all API keys and tokens immediately
2. **Assess** — Review audit logs to determine breach scope
3. **Rotate** — Generate new credentials for all services:
   - Supabase service role key
   - OpenAI API key
   - JWT signing secret
   - Stripe API keys
4. **Patch** — Fix the vulnerability
5. **Notify** — Inform affected users per GDPR requirements
6. **Deploy** — Push fix and rotate all secrets

## Monitoring & Alerting

- Health endpoint: `GET /api/health` — returns service status
- Tenant credit monitoring runs every 5 minutes (built-in)
- Set up external uptime monitoring (e.g., UptimeRobot, Pingdom) for:
  - `/api/health` — 1-minute interval
  - Frontend home page — 5-minute interval

## Testing the DR Plan

- **Quarterly**: Perform a tabletop exercise walking through each scenario
- **Semi-annually**: Restore a backup to a staging environment and verify data integrity
- **After major changes**: Review and update this document

## Contacts

| Role                | Responsibility                |
|---------------------|-------------------------------|
| DevOps Lead         | Infrastructure recovery       |
| Backend Lead        | Database restore & migrations |
| Security Lead       | Breach response coordination  |
| Product Owner       | Communication & prioritization|
