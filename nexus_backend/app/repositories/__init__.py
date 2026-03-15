"""
Repository Package

Provides the Repository Pattern for unified database access.
See docs/db-access-unification.md for the full design document.
"""

from app.repositories.base_repository import BaseRepository  # noqa: F401

__all__ = ["BaseRepository"]
