"""慢查询分析"""
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def profile_query(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        duration = time.time() - start
        if duration > 1.0:
            logger.warning(f"慢查询: {func.__name__} took {duration:.2f}s")
        return result
    return wrapper
