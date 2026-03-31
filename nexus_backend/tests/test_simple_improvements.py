"""
简化改进方案的单元测试
"""
import pytest
import asyncio
from app.core.tool_wrapper import execute_tool_safely, safe_tool
from app.core.context_manager import SimpleContextManager
from app.core.progress import send_progress, ProgressHelper


# ============ 测试错误处理 ============

async def normal_tool(value: int):
    """正常工具"""
    return value * 2


async def slow_tool(delay: int):
    """慢速工具"""
    await asyncio.sleep(delay)
    return "done"


async def failing_tool():
    """失败工具"""
    raise ValueError("Something went wrong")


@pytest.mark.asyncio
async def test_execute_tool_success():
    """测试正常执行"""
    result = await execute_tool_safely(
        normal_tool,
        {'value': 5},
        timeout=10
    )

    assert result['success'] is True
    assert result['data'] == 10


@pytest.mark.asyncio
async def test_execute_tool_timeout():
    """测试超时"""
    result = await execute_tool_safely(
        slow_tool,
        {'delay': 5},
        timeout=1  # 1秒超时
    )

    assert result['success'] is False
    assert '超时' in result['error']


@pytest.mark.asyncio
async def test_execute_tool_exception():
    """测试异常处理"""
    result = await execute_tool_safely(
        failing_tool,
        {},
        timeout=10
    )

    assert result['success'] is False
    assert '执行失败' in result['error']


@pytest.mark.asyncio
async def test_safe_tool_decorator():
    """测试装饰器"""
    @safe_tool(timeout=10)
    async def decorated_tool(x: int):
        return x + 1

    result = await decorated_tool(x=5)
    assert result['success'] is True
    assert result['data'] == 6


# ============ 测试进度反馈 ============

@pytest.mark.asyncio
async def test_progress_helper():
    """测试进度辅助类"""
    messages = []

    async def mock_callback(msg):
        messages.append(msg)

    helper = ProgressHelper(callback=mock_callback)
    await helper.send("Step 1")
    await helper.send("Step 2")

    assert len(messages) == 2
    assert messages[0]['message'] == "Step 1"
    assert messages[1]['message'] == "Step 2"


# ============ 测试上下文压缩 ============
# 注意：这个测试需要真实的数据库连接，可以跳过或使用 mock

@pytest.mark.skip(reason="需要数据库连接")
@pytest.mark.asyncio
async def test_context_trim():
    """测试上下文修剪"""
    manager = SimpleContextManager()

    # 这里需要实际的 conversation_id
    conversation_id = "test-conversation-id"

    trimmed = await manager.trim_if_needed(conversation_id)
    # 根据实际消息数量判断
    assert isinstance(trimmed, bool)
