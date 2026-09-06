import pytest

from app.services.artifact_docx_renderer import render_artifact_docx, render_artifact_pdf, render_artifact_xlsx
from app.services.artifact_export_validation import validate_export
from app.services.artifact_delivery_scan import verify_docx_render
from app.services.artifact_text_metrics import body_character_count


@pytest.mark.parametrize("family", ["光谱", "色谱", "质谱", "能谱", "电子仪器"])
@pytest.mark.parametrize("output_format,renderer", [
    ("docx", render_artifact_docx), ("pdf", render_artifact_pdf), ("xlsx", render_artifact_xlsx),
])
def test_five_families_export_canonical_paragraphs_and_tables(family, output_format, renderer):
    title = f"{family}客户检测能力建设方案"
    markdown = f"# {title}\n\n## 客户需求\n样品分析结果需要能够追溯。\n\n## 推荐配置\n| 模块名称 | 配置理由 |\n| --- | --- |\n| 检测主机 | 匹配企业检测场景 |\n"
    artifact = {"title": title, "content_markdown": markdown, "version_number": 2}
    content = renderer(artifact, {}, {}) if output_format != "xlsx" else renderer(artifact, {})
    result = validate_export(content, output_format, title=title, expected_markdown=markdown)
    assert result["ok"], result
    if output_format == "docx":
        assert verify_docx_render(content)["ok"]
    corrupt = validate_export(content, output_format, expected_markdown="关键配置章节被错误遗漏的测试内容")
    assert not corrupt["ok"]


@pytest.mark.parametrize("output_format", ["docx", "pdf", "xlsx"])
def test_invalid_export_is_not_a_successful_download(output_format):
    assert not validate_export(b"not a document", output_format)["ok"]


def test_body_count_excludes_title_sources_and_repeated_reference_ids():
    assert body_character_count("# 封面\n## 正文\n客户方案ABC123。[EVID:doc:chunk]\n## 资料来源\n" + "来源" * 3000) == 10
