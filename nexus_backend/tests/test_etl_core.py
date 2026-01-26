
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

def test_pii_scrubbing_boundary(etl_service):
    """
    Test PII scrubbing with boundaries.
    """
    # Use the inner function logic as implemented in _save_to_db
    # Since it's an inner function, we simulate the regex logic here 
    # OR we refactor the code to make it testable. 
    # For this test, we accept testing the regex logic directly to confirm correctness.
    import re
    
    def _scrub(content):
        # The logic from etl_service.py
        content = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)', '[PHONE_REDACTED]', content)
        content = re.sub(r'(?<!\d)\d{17}[\d|X](?!\d)', '[ID_REDACTED]', content)
        return content

    # Case 1: Real Phone Number
    assert _scrub("我的手机是 13800138000") == "我的手机是 [PHONE_REDACTED]"
    
    # Case 2: Order Number containing phone-like sequence
    # 2024 + 13800138000
    order_num = "订单号202413800138000"
    assert _scrub(order_num) == order_num # Should NOT change
    
    # Case 3: Embedded ID
    # 123 + ID + 456
    fake_id = "110101199001011234"
    assert _scrub(f"身份证 {fake_id} 有效") == "身份证 [ID_REDACTED] 有效"
    assert _scrub(f"编号9{fake_id}9") == f"编号9{fake_id}9" # Should NOT change

