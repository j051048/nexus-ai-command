"""
集中化 Mock 工厂 — 提取后端测试中的重复 mock 创建模式。

Usage:
    from tests.mock_helpers import make_mock_llm, make_mock_openai_client, make_mock_supabase_with_data
"""

from unittest.mock import AsyncMock, MagicMock

from tests.conftest import MockSupabaseClient


def make_mock_llm(response_content: str = "OK", tool_calls: list | None = None) -> AsyncMock:
    """创建 mock LLM (ChatOpenAI) 的 ainvoke 响应。

    Args:
        response_content: 模拟 LLM 返回的文本内容
        tool_calls: 可选的 tool_call 列表，模拟 Agent 工具调用

    Returns:
        AsyncMock 的 LLM 实例，支持 ainvoke / agenerate 调用
    """
    mock_message = MagicMock()
    mock_message.content = response_content
    mock_message.tool_calls = tool_calls or []
    mock_message.additional_kwargs = {}

    mock_response = MagicMock()
    mock_response.content = response_content
    mock_response.tool_calls = tool_calls or []

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_message)
    mock_llm.agenerate = AsyncMock(
        return_value=MagicMock(generations=[[MagicMock(message=mock_message)]])
    )
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)

    return mock_llm


def make_mock_openai_client(embed_vector: list[float] | None = None) -> MagicMock:
    """创建 mock AsyncOpenAI 客户端。

    Args:
        embed_vector: 模拟的 embedding 向量，默认为 1536 维零向量

    Returns:
        MagicMock 的 AsyncOpenAI 实例
    """
    if embed_vector is None:
        embed_vector = [0.0] * 1536

    mock_embedding_data = MagicMock()
    mock_embedding_data.embedding = embed_vector

    mock_embedding_response = MagicMock()
    mock_embedding_response.data = [mock_embedding_data]

    mock_chat_message = MagicMock()
    mock_chat_message.content = "mock response"

    mock_chat_choice = MagicMock()
    mock_chat_choice.message = mock_chat_message

    mock_chat_response = MagicMock()
    mock_chat_response.choices = [mock_chat_choice]

    client = MagicMock()
    client.embeddings = MagicMock()
    client.embeddings.create = AsyncMock(return_value=mock_embedding_response)
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=mock_chat_response)

    return client


def make_mock_supabase_with_data(table_data: dict[str, list] | None = None) -> MockSupabaseClient:
    """创建预填充数据的 MockSupabaseClient。

    Args:
        table_data: {表名: [行数据列表]} 映射

    Returns:
        配置好的 MockSupabaseClient 实例

    Example:
        db = make_mock_supabase_with_data({
            "users": [{"id": "u1", "name": "Test"}],
            "documents": [{"id": "d1", "name": "Doc"}],
        })
    """
    client = MockSupabaseClient()
    if table_data:
        for table_name, data in table_data.items():
            client.set_table_data(table_name, data)
    return client
