"""
Safe file writer with atomic operations.

Prevents file corruption during write operations by using temp file + rename pattern.
"""

import os
import tempfile
from pathlib import Path
from typing import Union


async def atomic_write(target_path: Union[str, Path], content: str, encoding: str = "utf-8"):
    """
    Atomically write content to a file.

    Process:
    1. Preserve original file permissions
    2. Write to temporary file
    3. Flush to disk (fsync)
    4. Restore permissions
    5. Atomic rename (replaces target)

    Args:
        target_path: Target file path
        content: Content to write
        encoding: File encoding (default: utf-8)
    """
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    # 1. Preserve original permissions
    existing_mode = None
    if target.exists():
        existing_mode = target.stat().st_mode

    # 2. Create temp file in same directory (ensures same filesystem)
    temp_fd, temp_path = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp"
    )

    try:
        # 3. Write and flush
        with os.fdopen(temp_fd, 'w', encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk

        # 4. Restore permissions
        if existing_mode:
            os.chmod(temp_path, existing_mode)

        # 5. Atomic replace
        os.replace(temp_path, target)
    except Exception:
        # Cleanup on failure
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
