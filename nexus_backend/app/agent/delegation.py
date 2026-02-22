"""
Agent Delegation Protocol.

When a user query falls outside the scope of the currently active agent, this
module can suggest handing the conversation off to a more specialised agent.
The delegation is purely advisory -- it produces hints that the orchestration
layer can choose to act on (or surface to the user).

Usage::

    from app.agent.delegation import suggest_delegation, get_delegation_hint

    target = suggest_delegation(query="Show me this quarter's pipeline", current_agent="approval")
    if target:
        hint = get_delegation_hint(query, current_agent="approval")
        # inject *hint* into the system prompt before the next LLM call
"""

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Capability map -- keywords that each specialist agent "owns"
# ---------------------------------------------------------------------------

AGENT_CAPABILITIES: dict[str, list[str]] = {
    "sales": [
        "sales", "deal", "pipeline", "revenue", "customer",
        "forecast", "opportunity", "lead", "quote",
    ],
    "performance": [
        "KPI", "score", "badge", "ranking", "bonus",
        "target", "incentive", "gamification",
    ],
    "approval": [
        "expense", "leave", "approval", "workflow",
        "reimburse", "vacation", "overtime",
    ],
    "knowledge": [
        "document", "search", "knowledge", "file",
        "PDF", "RAG", "embedding", "policy",
    ],
}


def _score_agent(query_lower: str, keywords: list[str]) -> int:
    """Return the number of keyword hits for a given agent.

    Args:
        query_lower: The user query, already lowercased.
        keywords: The keyword list associated with an agent.

    Returns:
        An integer count of how many keywords appear in the query.
    """
    return sum(1 for kw in keywords if kw.lower() in query_lower)


def suggest_delegation(query: str, current_agent: str) -> str | None:
    """Suggest another agent if the query is outside the current agent's scope.

    The function scores every registered agent by counting keyword matches.
    If another agent scores higher than the *current_agent* (and has at least
    one match), that agent is returned as the delegation target.

    Args:
        query: The raw user query string.
        current_agent: Name of the agent currently handling the conversation.

    Returns:
        The name of the agent best suited to handle the query, or ``None`` if
        the current agent is already the best match (or no clear match exists).
    """
    query_lower = query.lower()

    scores: dict[str, int] = {}
    for agent_name, keywords in AGENT_CAPABILITIES.items():
        scores[agent_name] = _score_agent(query_lower, keywords)

    current_score = scores.get(current_agent, 0)

    # Find the best scoring agent (excluding the current one)
    best_agent: str | None = None
    best_score = 0
    for agent_name, score in scores.items():
        if agent_name == current_agent:
            continue
        if score > best_score:
            best_score = score
            best_agent = agent_name

    # Only suggest delegation if the other agent clearly scores better
    if best_agent and best_score > current_score and best_score >= 1:
        logger.info(
            "[Delegation] suggest %s -> %s for query (score %d vs %d): %.80s",
            current_agent,
            best_agent,
            best_score,
            current_score,
            query,
        )
        return best_agent

    return None


def get_delegation_hint(query: str, current_agent: str) -> str:
    """Return a system-prompt hint about available agents if delegation is suggested.

    If the query would be better served by a different agent, the returned
    string contains a note that the orchestration layer can append to the
    system prompt.  If no delegation is needed, an empty string is returned.

    Args:
        query: The raw user query string.
        current_agent: Name of the agent currently handling the conversation.

    Returns:
        A system-prompt hint string, or ``""`` if no delegation is recommended.
    """
    target = suggest_delegation(query, current_agent)
    if target is None:
        return ""

    available = ", ".join(
        f"{name} ({', '.join(kws[:4])}...)"
        for name, kws in AGENT_CAPABILITIES.items()
        if name != current_agent
    )

    hint = (
        f"[Delegation Notice] The user's query may be better handled by the "
        f"'{target}' agent.  Available specialist agents: {available}.  "
        f"Consider informing the user that a more specialised agent can assist, "
        f"or route the request internally."
    )
    return hint
