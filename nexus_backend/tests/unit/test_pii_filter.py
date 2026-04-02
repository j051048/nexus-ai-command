"""Tests for PII filter — memory sanitization before persist."""

from app.services.conversation_memory.pii_filter import sanitize_pii


class TestSanitizePII:
    # ── Mobile ──
    def test_china_mobile(self):
        assert sanitize_pii("我的手机号是13812345678") == "我的手机号是138****5678"

    def test_china_mobile_in_sentence(self):
        assert sanitize_pii("联系方式：15900001234，谢谢") == "联系方式：159****1234，谢谢"

    # ── ID Card ──
    def test_china_id_card_18(self):
        # 110101 1990 01 01 123 4 → region + masked birth+seq + check
        result = sanitize_pii("身份证号110101199001011234")
        assert "110101" in result
        assert result.endswith("4")
        assert "19900101" not in result

    def test_china_id_card_with_x(self):
        result = sanitize_pii("证件号11010119900101123X")
        assert "110101" in result
        assert result.endswith("X")

    # ── Bank Card ──
    def test_bank_card_16(self):
        result = sanitize_pii("卡号6222021234561234")
        assert "6222" in result
        assert result.endswith("1234")
        assert "02123456" not in result

    def test_bank_card_19(self):
        result = sanitize_pii("银行卡6217001234567891234")
        assert "6217" in result
        assert result.endswith("1234")

    # ── Email ──
    def test_email(self):
        assert sanitize_pii("邮箱是zhangsan@example.com") == "邮箱是z***@example.com"

    def test_email_short_local(self):
        assert sanitize_pii("a@b.com") == "a***@b.com"

    # ── Passport ──
    def test_passport(self):
        result = sanitize_pii("护照号G12345678")
        assert result.startswith("护照号G")
        assert "12345678" not in result

    # ── Edge cases ──
    def test_no_pii(self):
        text = "今天天气不错，开了3个会"
        assert sanitize_pii(text) == text

    def test_empty_and_none(self):
        assert sanitize_pii("") == ""
        assert sanitize_pii(None) is None

    def test_mixed_pii(self):
        text = "用户张三，手机13812345678，邮箱zhangsan@corp.com"
        result = sanitize_pii(text)
        assert "138****5678" in result
        assert "z***@corp.com" in result
        assert "13812345678" not in result
        assert "zhangsan@" not in result

    def test_no_false_positive_short_numbers(self):
        """Short numbers like order IDs should NOT be masked."""
        text = "订单号12345，金额500元"
        assert sanitize_pii(text) == text
