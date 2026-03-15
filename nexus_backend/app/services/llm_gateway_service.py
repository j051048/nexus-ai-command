"""
LLM Model Adaptation Gateway - Re-export Shim

This file preserves backward compatibility after the service was split into
the ``app.services.llm_gateway`` package (Item 37: Giant Service Split).

All public symbols are re-exported so that existing imports like

    from app.services.llm_gateway_service import llm_gateway

continue to work without changes.
"""

from app.services.llm_gateway import LLMGatewayService, llm_gateway  # noqa: F401

__all__ = ["LLMGatewayService", "llm_gateway"]
