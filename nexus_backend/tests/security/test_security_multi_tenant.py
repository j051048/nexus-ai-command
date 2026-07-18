"""
Multi-Tenant Security Matrix - 隔离审计与权限泄露测试
对标大厂 SaaS 标准：确保租户 A 的 token 无论如何无法访问或写入租户 B 的数据。
"""

import asyncio
import json
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.security
@pytest.mark.asyncio
async def test_cross_tenant_access_rejection():
    """
    测试：租户 A 的 ID 被注入到 租户 B 的请求中。
    预期：RLS 或 Middleware 应当拒绝。
    """
    from app.services.conversation_memory.storage import save_memory

    # 模拟租户 A 尝试显式向租户 B 的 org_id 写入数据
    user_id_a = "user-a-01"
    org_id_b = "org-b-999"

    # 数据库 client 会自动感知 auth.uid()
    # 我们模拟 supabase 返回 Permission Denied (403)
    mock_client = MagicMock()

    # 模拟 select 链（同步链式调用 + 异步 execute）
    mock_execute_select = AsyncMock(return_value=MagicMock(data=None))
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.is_.return_value.maybe_single.return_value.execute = (
        mock_execute_select
    )

    # 原子记忆 RPC 是当前唯一写入边界，模拟数据库在该边界拒绝跨租户写入。
    mock_execute_insert = AsyncMock(
        side_effect=Exception("PGRST301: Row Level Security policy violation")
    )
    mock_client.rpc.return_value.execute = mock_execute_insert
    mock_client.table.return_value.insert.return_value.execute = mock_execute_insert

    with (
        patch("app.services.conversation_memory.storage.supabase", mock_client),
        patch(
            "app.services.conversation_memory.storage.generate_embedding",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        try:
            await save_memory(
                user_id_a, "malicious_key", "secret_content", org_id=org_id_b
            )
            pytest.fail("跨租户写入未被阻断！")
        except Exception as e:
            assert "Row Level Security" in str(e)
    mock_client.rpc.assert_called_once()


@pytest.mark.security
def test_sensitive_field_leaking_in_api_response():
    """验证 PII 脱敏管线生效，且模拟 API 响应不泄露原始敏感数据。"""
    from app.services.conversation_memory.pii_filter import sanitize_pii

    # 原始 PII 样本
    raw_phone = "13812345678"
    raw_id_card = "110101199003077777"
    raw_email = "zhangsan@company.com"
    raw_bank_card = "6222021234567890123"

    # 1) 验证 sanitize_pii 确实脱敏了每种 PII
    for raw in [raw_phone, raw_id_card, raw_email, raw_bank_card]:
        sanitized = sanitize_pii(raw)
        assert sanitized != raw, f"PII 未被脱敏: {raw}"

    # 2) 模拟一个包含 PII 的 API 响应 payload，确认原始值不残留
    fake_api_response = {
        "data": {
            "id": "org-001",
            "name": "测试公司",
            "contact_phone": sanitize_pii(raw_phone),
            "admin_email": sanitize_pii(raw_email),
            "notes": sanitize_pii(
                f"负责人身份证 {raw_id_card}，银行卡 {raw_bank_card}"
            ),
        }
    }
    response_text = json.dumps(fake_api_response, ensure_ascii=False)

    # 用正则检测响应中是否残留未脱敏的 PII
    pii_patterns = [
        (r"1[3-9]\d{9}", "手机号"),
        (
            r"[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]",
            "身份证",
        ),
        (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "邮箱"),
        (r"[4-6]\d{15,18}", "银行卡"),
    ]
    for pattern, label in pii_patterns:
        matches = re.findall(pattern, response_text)
        assert not matches, f"API 响应中泄露了未脱敏的{label}: {matches}"


@pytest.mark.security
@pytest.mark.asyncio
async def test_tool_tenant_context_purity():
    """
    测试：工具并发执行时，各自收到正确的租户 context，不会串味。
    项目使用显式 config 传参（非 ThreadLocal），本测试验证这一点。
    """
    from app.tools.organization_tools import ListDepartmentsTool

    tool = ListDepartmentsTool()

    config_a = {"org_id": "org-aaa", "token": "tok-a"}
    config_b = {"org_id": "org-bbb", "token": "tok-b"}

    captured_org_ids = []

    async def fake_list_departments(org_id, parent_id=None, db=None):
        # 记录每次调用收到的 org_id
        captured_org_ids.append(org_id)
        # 模拟轻微延迟以增加并发交叉的可能性
        await asyncio.sleep(0.01)
        return [{"id": f"dept-{org_id}", "name": f"Dept of {org_id}", "manager": None}]

    with patch(
        "app.tools.organization_tools.organization_service.list_departments",
        side_effect=fake_list_departments,
    ):
        # 并发调用同一个工具实例，传入不同 config
        result_a, result_b = await asyncio.gather(
            tool.run({}, "user-1", config=config_a),
            tool.run({}, "user-2", config=config_b),
        )

    # 验证每次调用收到了各自正确的 org_id
    assert "org-aaa" in captured_org_ids
    assert "org-bbb" in captured_org_ids
    # 验证返回内容包含各自 org 的数据
    assert "org-aaa" in result_a
    assert "org-bbb" in result_b
