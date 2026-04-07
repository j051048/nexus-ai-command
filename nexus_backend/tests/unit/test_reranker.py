"""API Reranker 单元测试

覆盖 VectorService._rerank_with_api() 的各种场景:
- 正常成功（Cohere 格式响应）
- API 失败 → 异常抛出（调用方 catch 后降级）
- 文档数 <= 1 直接返回
- 文档数 <= 3 截断返回
- 空文档列表安全处理
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def vector_service():
    """创建 VectorService 实例"""
    from app.services.vector_service import VectorService

    return VectorService()


@pytest.fixture
def sample_documents():
    """5 个样本文档用于 reranking 测试"""
    return [
        {"id": 1, "content": "销售流程包括线索获取、初步沟通、需求分析", "score": 0.8},
        {"id": 2, "content": "差旅报销标准：单日住宿不超过800元", "score": 0.7},
        {"id": 3, "content": "绩效考核分为季度和年度两种", "score": 0.6},
        {"id": 4, "content": "公司年终奖发放标准按照S/A/B/C等级", "score": 0.5},
        {"id": 5, "content": "入职培训为期两周，包含产品培训和销售技巧", "score": 0.4},
    ]


class TestRerankWithApi:
    """测试 _rerank_with_api 方法"""

    @pytest.mark.asyncio
    async def test_successful_rerank(self, vector_service, sample_documents):
        """正常 Cohere 格式响应应正确 rerank"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"index": 2, "relevance_score": 0.95},
                {"index": 0, "relevance_score": 0.85},
                {"index": 4, "relevance_score": 0.70},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_http_client):
            result = await vector_service._rerank_with_api("绩效", sample_documents, top_n=3)

        assert len(result) == 3
        # 第一个应该是 index=2（绩效考核），因为它有最高的 relevance_score
        assert result[0]["id"] == 3  # documents[2]
        assert result[0]["rerank_score"] == 0.95
        assert result[1]["id"] == 1  # documents[0]
        assert result[2]["id"] == 5  # documents[4]

    @pytest.mark.asyncio
    async def test_api_failure_raises_exception(self, vector_service, sample_documents):
        """API 调用失败应抛出异常（由调用方处理降级）"""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("Server Error", request=MagicMock(), response=mock_response)
        )

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_http_client), pytest.raises(httpx.HTTPStatusError):
            await vector_service._rerank_with_api("测试", sample_documents, top_n=3)

    @pytest.mark.asyncio
    async def test_empty_documents(self, vector_service):
        """空文档列表应直接返回空列表"""
        result = await vector_service._rerank_with_api("测试", [], top_n=3)
        assert result == []

    @pytest.mark.asyncio
    async def test_single_document(self, vector_service):
        """单个文档应直接返回，不调用 API"""
        docs = [{"id": 1, "content": "唯一文档", "score": 0.9}]
        result = await vector_service._rerank_with_api("测试", docs, top_n=3)
        assert result == docs

    @pytest.mark.asyncio
    async def test_three_or_fewer_documents(self, vector_service):
        """3 个或更少的文档应直接截断返回，不调用 API"""
        docs = [
            {"id": 1, "content": "文档1", "score": 0.9},
            {"id": 2, "content": "文档2", "score": 0.8},
            {"id": 3, "content": "文档3", "score": 0.7},
        ]
        result = await vector_service._rerank_with_api("测试", docs, top_n=2)
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2

    @pytest.mark.asyncio
    async def test_backfill_unseen_documents(self, vector_service, sample_documents):
        """API 返回不足 top_n 个结果时应从原始文档回填"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"index": 0, "relevance_score": 0.9},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_http_client):
            result = await vector_service._rerank_with_api("测试", sample_documents, top_n=3)

        assert len(result) == 3
        # 第一个是 API 返回的
        assert result[0]["id"] == 1
        assert result[0]["rerank_score"] == 0.9
        # 后面是回填的（无 rerank_score）
        assert "rerank_score" not in result[1]

    @pytest.mark.asyncio
    async def test_duplicate_index_handling(self, vector_service, sample_documents):
        """API 返回重复 index 时应去重"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"index": 0, "relevance_score": 0.9},
                {"index": 0, "relevance_score": 0.8},  # 重复
                {"index": 1, "relevance_score": 0.7},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_http_client):
            result = await vector_service._rerank_with_api("测试", sample_documents, top_n=3)

        # 去重后只有 index 0 和 1，第三个回填
        ids = [r["id"] for r in result]
        assert ids[0] == 1  # index 0
        assert ids[1] == 2  # index 1
        assert len(result) == 3
