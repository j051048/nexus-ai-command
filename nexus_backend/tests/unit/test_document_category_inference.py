import pytest

from app.routers.documents import _infer_document_category


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("UV-2600-操作手册.pdf", "manual"),
        ("Thermo竞品对比.xlsx", "competitor"),
        ("制药行业应用案例.docx", "case"),
        ("某高校液相色谱招标文件.pdf", "tender"),
        ("实验室整体解决方案.pptx", "proposal"),
        ("ISO17025法规标准.pdf", "regulation"),
        ("GCMS产品参数彩页.pdf", "product"),
        ("公司介绍.pdf", "other"),
        (None, "other"),
    ],
)
def test_infer_document_category(filename, expected):
    assert _infer_document_category(filename) == expected
