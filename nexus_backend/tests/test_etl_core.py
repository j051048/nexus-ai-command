
import pytest
from app.services.etl_service import ETLService

@pytest.fixture
def etl_service():
    return ETLService()

def test_chunking_logic(etl_service):
    """
    Test CJK overlap chunking logic.
    Input: "ABCD" with size=2, overlap=1
    Expected: ["AB", "BC", "CD"]
    """
    text = "ABCD"
    chunks = list(etl_service._simple_chunk(text, size=2, overlap=1))
    assert chunks == ["AB", "BC", "CD"]
    
def test_chunking_logic_chinese(etl_service):
    """
    Test with Chinese characters
    """
    text = "我爱北京天安门"
    # Size 4, Overlap 2 -> "我爱北京", "北京天安", "天安门"
    # "我爱北京" (0-4)
    # Next start = 4 - 2 = 2 ("北京")
    # "北京天安" (2-6)
    # Next start = 6 - 2 = 4 ("天安")
    # "天安门" (4-7)
    chunks = list(etl_service._simple_chunk(text, size=4, overlap=2))
    assert chunks == ["我爱北京", "北京天安", "天安门"]

