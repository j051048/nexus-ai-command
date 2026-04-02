import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock
from fastapi import Request

# Setup path
sys.path.append(os.path.join(os.getcwd(), "nexus_backend"))

from app.services.organization_service import organization_service
from app.routers.organization import get_organization_stats

async def test_org_stats_attribute():
    """Verify that OrganizationService has get_org_stats and the router can call it."""
    print("Checking OrganizationService for get_org_stats attribute...")
    if not hasattr(organization_service, "get_org_stats"):
        print("❌ Error: OrganizationService is missing 'get_org_stats'!")
        return False
    print("✅ Success: get_org_stats exists on service.")

    # Mock DB
    mock_db = AsyncMock()
    # Chain: db.table().select().eq().execute()
    mock_execute = AsyncMock()
    mock_execute.count = 5
    mock_execute.data = [{"role": "admin"}, {"role": "user"}]
    
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_execute
    
    # Mock Request
    mock_request = MagicMock(spec=Request)
    mock_request.state.db = mock_db
    mock_request.state.org_id = "test-org-uuid"

    print("Checking Router call to get_organization_stats...")
    try:
        response = await get_organization_stats(mock_request, user_id="test-user")
        print(f"✅ Success: Router returned {response.body}")
        return True
    except AttributeError as e:
        print(f"❌ AttributeError in Router: {e}")
        return False
    except Exception as e:
        print(f"⚠️ Other Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_org_stats_attribute())
    if not result:
        sys.exit(1)
