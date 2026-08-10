from app.services.artifact_delivery_scan import (
    scan_delivery_safety,
    verify_docx_render,
)
from app.services.artifact_format_lint import lint_markdown_format


def test_lint_detects_table_column_mismatch():
    text = "| A | B |\n| --- | --- |\n| 1 | 2 | 3 |\n"
    result = lint_markdown_format(text)
    assert any(item["code"] == "table_column_mismatch" for item in result["findings"])
    assert result["score"] < 100


def test_lint_detects_heading_level_jump():
    text = "## 一级\n#### 直接三级\n"
    result = lint_markdown_format(text)
    assert any(item["code"] == "heading_level_jump" for item in result["findings"])


def test_lint_detects_mixed_list_markers():
    text = "- 项目一\n* 项目二\n"
    result = lint_markdown_format(text)
    assert any(item["code"] == "list_marker_mixed" for item in result["findings"])


def test_lint_detects_unbalanced_code_fence():
    text = "```python\nprint(1)\n"
    result = lint_markdown_format(text)
    assert any(item["code"] == "unbalanced_code_fence" for item in result["findings"])


def test_lint_clean_document_scores_high():
    text = "## 标题\n\n正文内容。\n\n- 列表项\n"
    result = lint_markdown_format(text)
    assert result["score"] == 100.0


def test_scan_detects_pii_and_internal_markers():
    text = "联系人电话 13812345678，身份证 110101199001011234，见内部资料。"
    result = scan_delivery_safety(text)
    codes = {item["code"] for item in result["findings"]}
    assert "pii_phone" in codes
    assert "pii_id_card" in codes
    assert "internal_marker" in codes


def test_scan_detects_promise_language():
    text = "我方保证 30 个工作日内完成交付。"
    result = scan_delivery_safety(text)
    assert any(item["code"] == "unverified_promise" for item in result["findings"])


def test_scan_clean_text_scores_high():
    result = scan_delivery_safety("本方案基于企业授权资料编制。")
    assert result["score"] == 100.0
    assert result["findings"] == []


def test_verify_docx_render_rejects_empty_bytes():
    result = verify_docx_render(b"")
    assert result["ok"] is False
