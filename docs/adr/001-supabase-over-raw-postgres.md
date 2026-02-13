# ADR-001: Supabase over Raw PostgreSQL

## Status

Accepted

## Context

The Nexus AI Command platform needs a database backend for user management, document storage, chat history, and vector embeddings. The options considered were:

1. **Raw PostgreSQL** with SQLAlchemy/Alembic — full control, standard tooling
2. **Supabase** — managed Postgres with built-in auth, RLS, storage, and realtime
3. **Firebase** — NoSQL, real-time, Google ecosystem

The team is small (2-3 developers), and we need to move fast while maintaining security through row-level security (RLS) for multi-tenant isolation.

## Decision

We chose **Supabase** as the primary data layer because:

- Built-in Row Level Security (RLS) for multi-tenant data isolation
- Managed auth with JWT, eliminating custom auth server development
- pgvector extension support for vector embeddings (knowledge base)
- Supabase Storage for document uploads
- REST and Realtime APIs reduce backend boilerplate
- PostgreSQL underneath means we can always migrate to raw Postgres if needed

## Consequences

### Positive

- Multi-tenant isolation via RLS policies is enforced at the database level
- Auth, storage, and realtime come out of the box
- pgvector support enables semantic search without a separate vector DB
- Supabase's Python client provides async support

### Negative

- Vendor dependency on Supabase for managed services
- RPC functions must be written in PL/pgSQL (less familiar for some devs)
- Schema migrations are managed through Supabase CLI rather than Alembic
- Free tier limits may require upgrading for production workloads

### Neutral

- The `supabase-py` client wraps PostgREST — queries look different from raw SQL
- Monitoring and observability require Supabase dashboard + custom logging
