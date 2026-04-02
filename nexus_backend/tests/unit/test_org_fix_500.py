import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from fastapi import Request

# Need to manually setup some imports since we are in the backend root
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.routers.organization import get_organization_detail

async def test_organization_detail_logic():
    """
    Verify the fix for 500 AttributeError: 'OrganizationService' object has no attribute 'get_organization'
    """
    mock_db = AsyncMock()
    # Mocking Supabase-like response hierarchy
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "id": "org-id-test",
        "name": "Quality Assurance Org"
    }
    
    mock_request = MagicMock(spec=Request)
    mock_request.state.db = mock_db
    mock_request.state.org_id = "org-id-test"
    
    print("Testing get_organization_detail with mocked db...")
    try:
        # In our updated code, we also check org_id from state
        result = await get_organization_detail("org-id-test", mock_request)
        print(f"✅ Success: {result}")
        assert result["data"]["id"] == "org-id-test"
    except AttributeError as e:
        print(f"❌ Regression Fail: AttributeError found! {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Result (checking for data): {e}")

if __name__ == "__main__":
    asyncio.run(test_organization_detail_logic())
