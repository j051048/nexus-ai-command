import pytest

from app.services.artifact_section_revision import replace_section, section_span


def test_targeted_revision_preserves_unselected_bytes():
    original = "# 正式标题\n\n## 背景\n已批准背景。[E1]\n\n## 预算\n旧预算\n\n## 售后\n原售后条款。\n"
    revised = replace_section(original, "预算", "新的预算表\n\n| 项目 | 金额 |\n| --- | --- |\n| 安装 | 待报价 |")
    start, end = section_span(original, "预算")
    assert revised[:start] == original[:start]
    assert revised.endswith(original[end:])
    assert "旧预算" not in revised


@pytest.mark.parametrize("markdown,heading", [("## 预算\nA\n## 预算\nB", "预算"), ("# 标题\n正文", "预算")])
def test_missing_or_ambiguous_section_fails_closed(markdown, heading):
    with pytest.raises(ValueError):
        section_span(markdown, heading)


def test_fenced_headings_are_not_revision_targets():
    with pytest.raises(ValueError):
        section_span("~~~\n## 预算\n~~~\n## 售后\n内容", "预算")


def test_model_cannot_inject_other_top_level_sections():
    with pytest.raises(ValueError):
        replace_section("## 预算\n原文\n## 售后\n条款", "预算", "修改\n## 售后\n意外篡改")
