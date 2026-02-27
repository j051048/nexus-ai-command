"""
#25: APM Trace ID 全链路传播

使用 Python contextvars 在请求生命周期内传播 trace_id，
使得所有服务层（DB、LLM、Agent）都能获取当前请求的 trace_id。
"""

import uuid
from contextvars import ContextVar

# 全局 ContextVar，在 RequestIDMiddleware 中设置
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_trace_id() -> str:
    """获取当前请求的 trace_id，如果不存在则返回空字符串。"""
    return trace_id_var.get()


def get_request_id() -> str:
    """获取当前请求的 request_id，如果不存在则返回空字符串。"""
    return request_id_var.get()


def set_trace_id(trace_id: str) -> None:
    """设置当前请求的 trace_id。"""
    trace_id_var.set(trace_id)


def set_request_id(request_id: str) -> None:
    """设置当前请求的 request_id。"""
    request_id_var.set(request_id)


def ensure_trace_id() -> str:
    """获取当前 trace_id，如果不存在则生成新的。"""
    tid = trace_id_var.get()
    if not tid:
        tid = str(uuid.uuid4())
        trace_id_var.set(tid)
    return tid
