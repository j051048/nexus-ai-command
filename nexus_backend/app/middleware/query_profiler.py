"""慢查询分析"""
import time
from functools import wraps

def profile_query(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        duration = time.time() - start
        if duration > 1.0:
            print(f"慢查询: {func.__name__} took {duration:.2f}s")
        return result
    return wrapper
