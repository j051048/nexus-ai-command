
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Mock settings just in case
with patch("app.core.config.settings.OPENAI_API_KEY", "sk-mock"):
    from app.services.etl_service import ETLService

@pytest.mark.asyncio
async def test_vision_api_payload():
    """
    Test that image files trigger the Vision API payload construction.
    ID: TC13
    """
    # 1. Setup
    service = ETLService()
    
    # Mock file upload
    mock_file = MagicMock()
    mock_file.filename = "invoice.jpg"
    mock_file.read = AsyncMock(return_value=b"fake_image_content")
    
    # Mock _call_ai_raw to avoid real HTTP request but capture payload
    service._call_ai_raw = AsyncMock(return_value='{"key": "value"}')
    # Mock extract_metadata_via_ai to pass the metadata step
    service.extract_metadata_via_ai = AsyncMock(return_value=(True, {"doc_type": "invoice"}))
    # Mock _save_to_db
    service._save_to_db = MagicMock(return_value="doc_123")
    # Mock _generate_embeddings
    service._generate_embeddings = AsyncMock()

    # 2. Execute
    result = await service.process_file(mock_file, api_key="sk-test", base_url="http://mock")

    # 3. Verify
    # Verify _call_ai_raw was called (meaning it tried to extract text from image)
    assert service._call_ai_raw.called
    call_args = service._call_ai_raw.call_args
    payload = call_args[0][0]
    
    # Check payload structure for Vision
    assert payload["model"] == "gpt-4o-mini"
    assert payload["messages"][0]["content"][1]["type"] == "image_url"
    assert "data:image/jpeg;base64," in payload["messages"][0]["content"][1]["image_url"]["url"]
    
    # Verify overall success
    assert result["status"] == "success"
