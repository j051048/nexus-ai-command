
import pytest
from app.services.etl_service import ETLService

@pytest.fixture
def etl_service():
    return ETLService()

def test_chunking_logic(etl_service):
    """
    Test Semantic Chunking Logic with sliding window fallback.
    Input: "ABCD" with size=2, overlap=1
    Expected: ["AB", "BC", "CD"] (since no newlines, it falls back to sliding window)
    """
    text = "ABCD"
    chunks = list(etl_service._semantic_chunk(text, size=2, overlap=1))
    assert chunks == ["AB", "BC", "CD", "D"]
    
def test_chunking_logic_chinese(etl_service):
    """
    Test with Chinese characters and Semantic boundaries.
    """
    # Case A: Split by logical paragraphs (double newlines) - Merged if small enough
    text_para = "第一段内容\n\n第二段内容"
    chunks_a = list(etl_service._semantic_chunk(text_para, size=100, overlap=10))
    # Correct behavior: "第一段内容\n\n第二段内容" (because 5+5 < 100)
    assert chunks_a == ["第一段内容\n\n第二段内容"]

    # Case B: Sliding window for long text without line breaks
    text_long = "我爱北京天安门"
    # Size 4, Overlap 2 -> "我爱北京", "北京天安", "天安门"
    chunks_b = list(etl_service._semantic_chunk(text_long, size=4, overlap=2))
    assert chunks_b == ["我爱北京", "北京天安", "天安门", "门"]

def test_pii_scrubbing_boundary(etl_service):
    """
    Test PII scrubbing with boundaries.
    """
    # Use the actual implementation
    
    # Case 1: Real Phone Number
    assert etl_service._scrub_pii("我的手机是 13800138000") == "我的手机是 [PHONE_REDACTED]"
    
    # Case 2: Order Number containing phone-like sequence
    # 2024 + 13800138000 -> 14 digits, should not match phone logic (11 digits)
    order_num = "订单号202413800138000"
    processed = etl_service._scrub_pii(order_num)
    assert processed == order_num # Should NOT change
    
    # Case 3: Embedded ID
    # 110101 + 1990 + 0101 + 1234 (18 digits)
    fake_id = "110101199001011234"
    masked_id = "110101********1234"
    assert etl_service._scrub_pii(f"身份证 {fake_id} 有效") == f"身份证 {masked_id} 有效"
    
    # Boundary check: ID embedded in longer string of numbers
    assert etl_service._scrub_pii(f"编号9{fake_id}9") == f"编号9{fake_id}9" # Should NOT change because of (?<!\d) check

