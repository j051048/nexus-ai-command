from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request


@pytest.fixture
def mock_db():
    db = MagicMock()
    # Mock table interfaces
    db.table = MagicMock()
    return db


@pytest.fixture
def mock_request(mock_db):
    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.state.db = mock_db
    req.state.org_id = "test-org-123"
    return req


@pytest.mark.asyncio
async def test_list_customers_success(mock_request):
    mock_customers = [
        {"id": "c1", "name": "Customer 1", "stage": "lead"},
        {"id": "c2", "name": "Customer 2", "stage": "prospect"},
    ]

    with patch(
        "app.routers.crm.crm_service.list_customers", new_callable=AsyncMock
    ) as mock_list:
        mock_list.return_value = mock_customers

        from app.routers.crm import list_customers

        # Must pass Query-defaulted params explicitly to avoid Query object defaults
        response = await list_customers(
            req=mock_request,
            user_id="u123",
            search=None,
            stage=None,
            industry=None,
            offset=0,
            limit=50,
        )

        # api_list returns {"success": True, "data": [...], "meta": {"count": N, "total": N}}
        assert response["success"] is True
        assert len(response["data"]) == 2
        assert response["meta"]["total"] == 2
        mock_list.assert_called_once()


@pytest.mark.asyncio
async def test_create_customer_success(mock_request):
    from app.routers.crm import CreateCustomerRequest, create_customer

    body = CreateCustomerRequest(name="New Co", stage="lead", company="New Co Ltd")

    with patch(
        "app.routers.crm.crm_service.create_customer", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = {"id": "new-id", "name": "New Co"}

        response = await create_customer(body=body, req=mock_request, user_id="u123")

        assert response["success"] is True
        assert response["data"]["customer"]["id"] == "new-id"
        mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_get_customer_detail_not_found(mock_request):
    with patch(
        "app.routers.crm.crm_service.get_customer", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = None

        from app.routers.crm import get_customer

        # Domain not-found errors must retain their public 404 semantics.
        with pytest.raises(HTTPException) as exc:
            await get_customer(
                customer_id="non-existent", req=mock_request, user_id="u123"
            )

        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_list_contacts_success(mock_request):
    mock_contacts = [{"id": "con1", "name": "John Doe", "is_primary": True}]

    with patch(
        "app.routers.crm.crm_service.list_contacts", new_callable=AsyncMock
    ) as mock_contacts_list:
        mock_contacts_list.return_value = mock_contacts

        from app.routers.crm import list_contacts

        response = await list_contacts(
            customer_id="c1", req=mock_request, user_id="u123"
        )

        # api_list returns {"success": True, "data": [...], "meta": {"count": N, "total": N}}
        assert response["success"] is True
        assert response["meta"]["total"] == 1
        assert response["data"][0]["name"] == "John Doe"


@pytest.mark.asyncio
async def test_get_customer_stats_success(mock_request):
    mock_stats = {"total_customers": 10, "new_this_month": 2, "conversion_rate": 20.0}

    with patch(
        "app.routers.crm.crm_service.get_customer_stats", new_callable=AsyncMock
    ) as mock_get_stats:
        mock_get_stats.return_value = mock_stats

        from app.routers.crm import get_customer_stats

        response = await get_customer_stats(req=mock_request, user_id="u123")

        assert response["success"] is True
        assert response["data"]["stats"]["total_customers"] == 10


@pytest.mark.asyncio
async def test_get_stages(mock_request):
    from app.routers.crm import get_stages

    response = await get_stages()
    assert response["success"] is True
    assert "lead" in response["data"]["stages"]
