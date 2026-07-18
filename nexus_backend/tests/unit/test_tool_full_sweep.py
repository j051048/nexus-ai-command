"""
Full Sweep Regression Test - 全量工具稳健性扫描
批量验证 100+ 个已注册工具的元数据、Schema 规范及基本执行链路。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools import _TOOL_MODULES
from tests.e2e.test_tool_e2e_regression import _load_tool

# 排除一些由于环境特殊、初始化极重或需要真实硬件连接的工具（如有）
EXCLUDED_TOOLS = []

ALL_REGISTERED_TOOLS = [t for t in _TOOL_MODULES if t not in EXCLUDED_TOOLS]


@pytest.mark.parametrize("tool_name", ALL_REGISTERED_TOOLS)
def test_tool_specification_standards(tool_name):
    """
    P0 规范性测试：所有工具必须满足 Nexus Harness 的元数据标准。
    """
    tool = _load_tool(tool_name)

    assert (
        tool.name == tool_name
    ), f"工具内部名称 ({tool.name}) 与注册名 ({tool_name}) 不一致"
    assert tool.description, f"工具 {tool_name} 缺少描述 (LLM 无法识别)"
    assert len(tool.description) > 10, f"工具 {tool_name} 描述过短"

    # 验证 JSON Schema 结构
    assert isinstance(tool.parameters, dict)
    assert tool.parameters.get("type") == "object"
    if "properties" in tool.parameters:
        assert isinstance(tool.parameters["properties"], dict)


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ALL_REGISTERED_TOOLS)
async def test_tool_run_crashes_protected(tool_name):
    """
    P1 稳定性扫描：所有工具在数据库异常或空数据时，不应抛出未捕获异常导致进程崩溃。
    应通过 safe_tool_error 返回人类可读错误。
    """
    tool = _load_tool(tool_name)

    mock_config = {"org_id": "test-org", "token": "test-token"}
    user_id = "test-user"

    # 模拟一个最简参数（通常工具至少一个必填，或者全可选）
    # 这一步主要是检测导入依赖是否正确，以及基础逻辑是否健壮
    dummy_args = {}

    # 我们 patch 掉底层客户端和 AI 服务
    with patch("app.tools._shared.supabase", new_callable=MagicMock), patch(
        "app.services.ai_service.AIService.call_llm", new_callable=AsyncMock
    ) as mock_llm:

        mock_llm.return_value = "Mock LLM Response for Test"

        try:
            # 我们不验证结果是否“正确”（业务逻辑由专项测试负责），只验证“不崩溃”
            await tool.run(dummy_args, user_id, mock_config)
        except (ValueError, KeyError, TypeError):
            # 允许业务异常（如参数缺失导致的校验失败）
            pass
        except Exception as e:
            # 不允许底层代码崩溃（如 AttributeError, NameError 等）
            pytest.fail(
                f"工具 {tool_name} 在基础调用中抛出非业务异常: {type(e).__name__}: {e}"
            )
