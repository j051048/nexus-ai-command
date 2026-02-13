# Technical Debt Tracker

This document tracks known technical debt in the Nexus AI Command codebase.
Items are categorized by area and prioritized for resolution.

## Security

| ID | Description | Impact | Effort | Status |
|----|------------|--------|--------|--------|
| S-1 | Webhook secret validation uses in-memory store only | Medium — secrets lost on restart | Low | Open |
| S-2 | OAuth tokens stored in memory, not DB | High — tokens lost on restart | Medium | Open |
| S-3 | Rate limiting cache not shared across processes | Medium — limits bypass in multi-worker | Medium | Open |

## Performance

| ID | Description | Impact | Effort | Status |
|----|------------|--------|--------|--------|
| P-1 | Token usage tracker loads per-user from DB on first access | Low — cold first request | Low | Open |
| P-2 | Vector search LLM reranker uses extra API call | Medium — latency + cost | Medium | Open |
| P-3 | Event bus is in-process only, not distributed | High — events missed in multi-instance | High | Open |

## Architecture

| ID | Description | Impact | Effort | Status |
|----|------------|--------|--------|--------|
| A-1 | Singleton services use module-level instances | Medium — hard to test | Medium | Open |
| A-2 | Chat service has 600+ line stream_response method | High — hard to maintain | High | Open |
| A-3 | No database migration versioning tool (Alembic/supabase migrations) | Medium — manual schema changes | Medium | Open |
| A-4 | Plugin system hooks are in-process only | Low — can't distribute plugins | High | Open |

## Testing

| ID | Description | Impact | Effort | Status |
|----|------------|--------|--------|--------|
| T-1 | No integration tests for Supabase RPC functions | High — RPC bugs undetected | Medium | Open |
| T-2 | No end-to-end API tests for critical flows | High — regression risk | High | Open |
| T-3 | Frontend test coverage is minimal | Medium — UI regressions | Medium | Open |

## Documentation

| ID | Description | Impact | Effort | Status |
|----|------------|--------|--------|--------|
| D-1 | API documentation relies solely on auto-generated Swagger | Low — missing examples | Low | Open |
| D-2 | No onboarding guide for new developers | Medium — slow ramp-up | Low | Open |
| D-3 | Missing runbook for common operational tasks | Medium — incident response slower | Low | Open |

## Resolution Process

1. Review this document monthly
2. Pick items based on priority and available capacity
3. Create a GitHub issue for each item before starting work
4. Update status here when resolved
5. Add new items as they are discovered during development
