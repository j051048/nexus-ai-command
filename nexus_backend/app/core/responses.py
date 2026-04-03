"""UTF-8 JSON response class for FastAPI.

Ensures Chinese (and all non-ASCII) characters are returned as literal UTF-8
instead of \\uXXXX escape sequences, and declares charset=utf-8 in Content-Type.
"""

import json
from typing import Any

from fastapi.responses import JSONResponse


class UTF8JSONResponse(JSONResponse):
    """JSONResponse that preserves non-ASCII characters and sets charset=utf-8."""

    media_type = "application/json; charset=utf-8"

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


# Re-export from canonical source to avoid import confusion
from app.core.errors import api_error, api_success  # noqa: F401, E402
