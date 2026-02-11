"""
LangGraph-based Agentic Architecture for Project Nexus.

This module replaces the tool-augmented chat loop with a true
state-machine agent that follows:
  Plan → Execute → Reflect → Respond (with self-correction)

Key improvements over the old ChatService.stream_response:
- Explicit state graph with conditional edges
- Self-reflection & hallucination detection nodes
- Long-term memory (vector + structured hybrid)
- Dynamic model routing (simple queries → mini, complex → gpt-4o)
"""
