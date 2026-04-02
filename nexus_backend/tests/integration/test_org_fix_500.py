"""
回归测试：修复 500 AttributeError — OrganizationService.get_organization
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import Request
from app.routers.organization import get_organization_detail


@pytest.mark.asyncio
async def test_organization_detail_no_attribute_error():
    """get_organization_detail 不应抛出 AttributeError（回归 #500）"""
    mock_db = AsyncMock()
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "id": "org-id-test",
        "name": "Quality Assurance Org",
    }

    mock_request = MagicMock(spec=Request)
    mock_request.state.db = mock_db
    mock_request.state.org_id = "org-id-test"

    result = await get_organization_detail("org-id-test", mock_request)
    assert result["data"]["id"] == "org-id-test"
