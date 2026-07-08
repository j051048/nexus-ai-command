"""Safety gate for LLM-generated SQL/Cypher-style queries."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

READ_ONLY_SQL_PREFIXES = ("select", "with", "explain")
READ_ONLY_CYPHER_PREFIXES = ("match", "with", "return", "unwind", "call db.")
MUTATION_TOKENS = (
    " insert ",
    " update ",
    " delete ",
    " merge ",
    " create ",
    " drop ",
    " alter ",
    " truncate ",
    " detach ",
    " remove ",
    " set ",
    " load csv ",
)


@dataclass(frozen=True)
class QuerySafetyDecision:
    allowed: bool
    reason: str
    dialect: str
    read_only: bool
    requires_human_review: bool = False
    safe_alternative: str | None = None
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "dialect": self.dialect,
            "read_only": self.read_only,
            "requires_human_review": self.requires_human_review,
            "safe_alternative": self.safe_alternative,
            "violations": list(self.violations),
        }


def _normalize_query(query: str) -> str:
    compact = re.sub(r"\s+", " ", query or "").strip().lower()
    return f" {compact} "


def _is_read_only(query: str, dialect: str) -> bool:
    compact = _normalize_query(query).strip()
    prefixes = (
        READ_ONLY_CYPHER_PREFIXES if dialect == "cypher" else READ_ONLY_SQL_PREFIXES
    )
    return compact.startswith(prefixes)


def evaluate_generated_query(
    query: str,
    *,
    dialect: str = "sql",
    allow_dangerous_requests: bool = False,
    require_read_only: bool = True,
    require_tenant_guard: bool = True,
) -> QuerySafetyDecision:
    """Decide whether an LLM-generated query may be executed."""

    if dialect not in {"sql", "cypher"}:
        return QuerySafetyDecision(
            allowed=False,
            reason="unsupported_dialect",
            dialect=dialect,
            read_only=False,
            safe_alternative="Use a supported read-only SQL or Cypher query.",
            violations=["unsupported_dialect"],
        )

    normalized = _normalize_query(query)
    violations = [token.strip() for token in MUTATION_TOKENS if token in normalized]
    read_only = _is_read_only(query, dialect) and not violations

    if require_read_only and not read_only and not allow_dangerous_requests:
        return QuerySafetyDecision(
            allowed=False,
            reason="dangerous_generated_query",
            dialect=dialect,
            read_only=False,
            requires_human_review=True,
            safe_alternative="Generate a read-only query and execute writes through RBAC/HITL tools.",
            violations=violations or ["not_read_only"],
        )

    tenant_tokens = ("organization_id", "org_id", "$org_id", ":org_id", "p_org_id")
    if require_tenant_guard and not any(token in normalized for token in tenant_tokens):
        return QuerySafetyDecision(
            allowed=False,
            reason="missing_tenant_guard",
            dialect=dialect,
            read_only=read_only,
            safe_alternative="Add an organization_id/org_id tenant predicate before execution.",
            violations=["missing_tenant_guard"],
        )

    return QuerySafetyDecision(
        allowed=True,
        reason="read_only_query_allowed" if read_only else "dangerous_query_opted_in",
        dialect=dialect,
        read_only=read_only,
        requires_human_review=not read_only,
        violations=[],
    )
