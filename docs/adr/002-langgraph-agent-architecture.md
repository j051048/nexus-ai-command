# ADR-002: LangGraph Agent Architecture

## Status

Accepted; user-facing explainability amended on 2026-09-04.

## Context

The platform needs an AI agent system that can:

- Execute multi-step reasoning (Plan → Execute → Reflect)
- Call external tools (CRM queries, document search, approval workflows)
- Support streaming responses for real-time user feedback
- Handle tool failures gracefully with retry and circuit breaker patterns
- Provide useful progress and decision evidence to users

Options considered:

1. **LangChain Agents** — well-known, broad ecosystem
2. **LangGraph** — graph-based agent execution with state management
3. **Custom agent loop** — full control, no framework dependency
4. **CrewAI / AutoGen** — multi-agent frameworks

## Decision

We chose **LangGraph** for the agent execution layer because:

- Explicit graph-based state machine provides clear control flow
- Built-in support for checkpointing and state persistence
- Conditional routing between plan/execute/reflect nodes
- Native streaming support via `astream_events`
- LangChain tool ecosystem compatibility for existing tools
- Better debuggability than implicit chain-based agents

The chat service (`chat_service.py`) handles the direct OpenAI streaming path for simple conversations, while the LangGraph agent (`agent/graph.py`, `agent/nodes.py`) handles complex multi-tool workflows.

## Consequences

### Positive

- Agent flow is explicit and visible as a graph — easier to debug
- State checkpointing allows resuming interrupted agent runs
- Conditional edges enable dynamic routing based on LLM decisions
- Circuit breaker integration protects against cascading LLM/tool failures

### Negative

- Two parallel execution paths (ChatService streaming + LangGraph) add complexity
- LangGraph is newer and has less community documentation than LangChain
- Graph definition requires understanding of LangGraph's state model
- Dependency on both `langgraph` and `langchain-core` packages

### Neutral

- Tool definitions are shared between both paths via `app/tools/`
- Token counting and cost tracking apply uniformly to both paths

## Current Implementation Note

LangGraph remains the complex-task execution layer, but raw chain-of-thought is not a product surface. Business users see the current stage, evidence references, confidence, result and available controls. Detailed traces are restricted to Agent Ops and authorized debugging workflows. The current node layout is maintained under `nexus_backend/app/agent/node_*.py`, `plan/` and `graph.py`; see `docs/handbook/05-agent-lifecycle.md` for the operational flow.
