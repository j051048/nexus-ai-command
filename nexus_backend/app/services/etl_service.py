"""
ETL Service - Re-export Shim

This file preserves backward compatibility after the service was split into
the ``app.services.etl`` package (Item 37: Giant Service Split).

All public symbols are re-exported so that existing imports like

    from app.services.etl_service import etl_service

continue to work without changes.
"""

from app.services.etl import ETLService, etl_service  # noqa: F401

__all__ = ["ETLService", "etl_service"]
