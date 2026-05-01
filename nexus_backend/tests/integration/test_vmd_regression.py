"""
VMD (Virtual Marketing Department) Tool Regression Tests.
用于验证科学仪器行业内容生成工具的完整性。
"""

from unittest.mock import AsyncMock, patch

import pytest

from tests.e2e.test_tool_e2e_regression import _assert_tool_metadata, _load_tool

USER_ID = "user-vmd-001"
ORG_ID = "org-vmd-001"


@pytest.fixture
def vmd_tool_config():
    return {
        "org_id": ORG_ID,
        "token": "vmd-test-token",
        "model": "gpt-4o",
    }

@pytest.mark.asyncio
async def test_generate_product_manual_flow(vmd_tool_config):
    tool = _load_tool("generate_product_manual")
    _assert_tool_metadata(tool)

    # Mock Vector and LLM — llm_gateway.chat 替代旧的 AIService.call_llm
    with patch("app.services.vector_service.vector_service.search", new_callable=AsyncMock) as mock_search, \
         patch("app.tools.vmd_content_tools.llm_gateway.chat", new_callable=AsyncMock) as mock_llm:

        mock_search.return_value = "知识库中关于 ICP-MS 的参数：质量范围 2-260 amu..."
        mock_llm.return_value = "### 产品手册章节\n1. 概述\n2. 规格..."

        args = {"product_name": "ICP-MS 7800", "product_category": "质谱仪"}
        result = await tool.run(args, USER_ID, vmd_tool_config)
        summary = result["summary"] if isinstance(result, dict) else result

        assert "ICP-MS 7800" in summary
        assert "产品手册" in summary
        mock_search.assert_called_once()
        mock_llm.assert_called_once()


@pytest.mark.asyncio
async def test_generate_whitepaper_flow(vmd_tool_config):
    tool = _load_tool("generate_whitepaper")

    with patch("app.services.vector_service.vector_service.search", new_callable=AsyncMock) as mock_search, \
         patch("app.tools.vmd_content_tools.llm_gateway.chat", new_callable=AsyncMock) as mock_llm:

        mock_llm.return_value = "拉曼光谱在疫苗生产中的质量控制白皮书..."

        args = {"topic": "疫苗生产质控", "industry": "制药", "technology": "拉曼光谱"}
        result = await tool.run(args, USER_ID, vmd_tool_config)

        assert "白皮书" in result
        assert "疫苗生产" in result


@pytest.mark.asyncio
async def test_generate_social_post_variants(vmd_tool_config):
    tool = _load_tool("generate_social_post")

    with patch("app.tools.vmd_content_tools.llm_gateway.chat", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "【重磅】新品发布！欢迎关注..."

        # Test wechat platform
        args = {"topic": "新品发布", "platform": "wechat", "tone": "promotional"}
        result = await tool.run(args, USER_ID, vmd_tool_config)
        assert "微信公众号" in result

        # Test linkedin platform
        args = {"topic": "技术分享", "platform": "linkedin"}
        result = await tool.run(args, USER_ID, vmd_tool_config)
        assert "LinkedIn" in result
