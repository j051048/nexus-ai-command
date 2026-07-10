# ADR-004: Converge Runtime Contracts Before Vertical Expansion

## Status

Accepted - 2026-07-10

## Context

Nexus has a broad enterprise operating foundation and a proposed scientific-
instrument vertical. The vertical thesis is promising, but device protocols,
regulated-lab workflows and willingness to pay are not proven by source code.
At the same time, production contracts had drifted across LLM logging, quotas,
audit retention, offline mutation replay and multi-process scheduling.

## Decision

1. Treat the existing five-space Enterprise OS as the stable product core.
2. Converge runtime/database contracts and production safety before adding
   instrument protocols or regulated-lab claims.
3. Keep legacy in-process schedulers disabled by default; Celery Beat and an
   atomic PostgreSQL claim RPC are authoritative.
4. Persist no authentication secrets in the offline queue. Bind every mutation
   to organization, user and session; require fresh credentials at replay.
5. Require explicit tool action/risk policy. Undeclared tools fail closed and
   are never considered cache-safe.
6. Do not claim the scientific-instrument ICP is validated from synthetic data.
   Use anonymized, artifact-backed evidence and the discovery gate implemented
   by `vertical_icp_validation_service.py`.

## Vertical Discovery Gate

Expansion into SCPI/VISA, OPC-UA or regulated-lab workflows requires at least:

- 8 distinct customer interviews;
- 2 repeated workflows, each confirmed by 3 distinct candidates;
- 2 design partners;
- access to device or telemetry data from 1 candidate;
- 1 named domain expert participating in review.

A paid pilot is tracked as a separate commercialization gate. Evidence files
must contain anonymized `candidate_id`, `evidence_type`, `artifact_ref`, and an
optional `workflow_key`. Interview contents and customer names stay outside the
repository.

## Consequences

- P0/P1 infrastructure work remains valuable whichever product direction wins.
- Horizontal modules are maintained, not expanded indiscriminately.
- Instrument-specific engineering starts only after evidence supports it.
- Capacity and compliance targets are set from pilot workloads and expert
  review, not invented before a real device is connected.
