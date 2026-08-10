"""Canonical domain catalog for scientific-instrument growth workflows."""

from __future__ import annotations

from typing import Any

INSTRUMENT_DOMAIN_VERSION = "scientific-instrument.v1"

INSTRUMENT_LINES: tuple[dict[str, Any], ...] = (
    {
        "code": "spectroscopy",
        "name": "光谱",
        "short_name": "光谱",
        "summary": "围绕物质光学响应进行定性、定量与结构分析的仪器体系。",
        "families": ["原子吸收", "ICP-OES", "紫外可见", "红外", "拉曼", "荧光光谱"],
        "applications": ["元素分析", "分子结构", "材料鉴定", "环境检测", "制药质控"],
        "decision_roles": ["实验室主任", "技术负责人", "仪器平台主管", "采购", "财务"],
        "evidence_requirements": [
            "检测限与重复性",
            "标准样品实测",
            "应用方法",
            "同类客户案例",
        ],
        "tender_focus": [
            "波长范围",
            "分辨率",
            "检测限",
            "光学系统",
            "方法库与服务能力",
        ],
    },
    {
        "code": "chromatography",
        "name": "色谱",
        "short_name": "色谱",
        "summary": "围绕复杂混合物分离、定量和纯度分析的仪器与耗材体系。",
        "families": ["气相色谱", "液相色谱", "离子色谱", "凝胶色谱", "制备色谱"],
        "applications": [
            "成分分离",
            "杂质分析",
            "食品安全",
            "药物分析",
            "化工过程控制",
        ],
        "decision_roles": [
            "分析平台主管",
            "方法开发人员",
            "质量负责人",
            "采购",
            "实验室主任",
        ],
        "evidence_requirements": [
            "分离度与重复性",
            "方法转移验证",
            "柱与耗材成本",
            "样品通量",
        ],
        "tender_focus": [
            "流量与压力范围",
            "检测器配置",
            "自动进样",
            "软件合规",
            "耗材兼容性",
        ],
    },
    {
        "code": "mass_spectrometry",
        "name": "质谱",
        "short_name": "质谱",
        "summary": "围绕离子质荷比开展高灵敏定性、定量和结构解析的高端仪器体系。",
        "families": ["GC-MS", "LC-MS", "ICP-MS", "MALDI-TOF", "高分辨质谱"],
        "applications": [
            "痕量检测",
            "未知物鉴定",
            "蛋白质组",
            "代谢组",
            "元素与同位素分析",
        ],
        "decision_roles": [
            "平台主管",
            "学科带头人",
            "核心技术用户",
            "采购",
            "信息化负责人",
        ],
        "evidence_requirements": [
            "灵敏度与质量精度",
            "真实基质实测",
            "数据库覆盖",
            "运行稳定性",
        ],
        "tender_focus": [
            "质量范围",
            "分辨率",
            "扫描速度",
            "灵敏度",
            "离子源与软件生态",
        ],
    },
    {
        "code": "energy_spectroscopy",
        "name": "能谱",
        "short_name": "能谱",
        "summary": "围绕射线或电子能量分布开展元素组成与表面化学分析的仪器体系。",
        "families": ["EDS/EDX", "XRF", "XPS", "AES", "电子能量损失谱"],
        "applications": [
            "元素组成",
            "表面分析",
            "失效分析",
            "矿物与合金分析",
            "半导体材料",
        ],
        "decision_roles": [
            "材料平台主管",
            "电镜平台主管",
            "失效分析负责人",
            "采购",
            "设备处",
        ],
        "evidence_requirements": [
            "能量分辨率",
            "轻元素能力",
            "标准样品验证",
            "联机兼容性",
        ],
        "tender_focus": [
            "能量分辨率",
            "探测面积",
            "计数率",
            "轻元素检测",
            "主机接口与标定",
        ],
    },
    {
        "code": "electronic_instrumentation",
        "name": "电子与高科技科学仪器",
        "short_name": "电子仪器",
        "summary": "面向电子、通信、半导体与先进制造的测量、测试和自动化仪器体系。",
        "families": [
            "示波器",
            "频谱分析仪",
            "网络分析仪",
            "信号源",
            "半导体测试",
            "自动化测试系统",
        ],
        "applications": [
            "研发验证",
            "射频微波",
            "功率电子",
            "半导体测试",
            "产线质量控制",
        ],
        "decision_roles": [
            "研发负责人",
            "测试平台主管",
            "生产工程负责人",
            "采购",
            "信息安全负责人",
        ],
        "evidence_requirements": [
            "带宽与精度",
            "自动化接口",
            "不确定度与校准",
            "现场测试报告",
        ],
        "tender_focus": [
            "带宽与采样率",
            "动态范围",
            "同步能力",
            "SCPI/LXI 接口",
            "校准与二次开发",
        ],
    },
)

_LINE_BY_CODE = {item["code"]: item for item in INSTRUMENT_LINES}


def normalize_instrument_line(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower().replace("-", "_")
    aliases = {
        "光谱": "spectroscopy",
        "色谱": "chromatography",
        "质谱": "mass_spectrometry",
        "能谱": "energy_spectroscopy",
        "电子仪器": "electronic_instrumentation",
        "电子与高科技科学仪器": "electronic_instrumentation",
        "electronics": "electronic_instrumentation",
        "electronic_instruments": "electronic_instrumentation",
        "electronic-instrumentation": "electronic_instrumentation",
    }
    code = aliases.get(value.strip(), normalized)
    return code if code in _LINE_BY_CODE else None


def get_instrument_line(value: str | None) -> dict[str, Any] | None:
    code = normalize_instrument_line(value)
    return _LINE_BY_CODE.get(code) if code else None


def build_instrument_context(
    line_code: str | None,
    *,
    application_field: str | None = None,
    product_models: list[str] | None = None,
) -> dict[str, Any]:
    line = get_instrument_line(line_code)
    if not line:
        return {
            "domain_version": INSTRUMENT_DOMAIN_VERSION,
            "instrument_line_code": None,
            "application_field": application_field,
            "product_models": product_models or [],
            "classification_status": "unclassified",
        }
    return {
        "domain_version": INSTRUMENT_DOMAIN_VERSION,
        "instrument_line_code": line["code"],
        "instrument_line_name": line["name"],
        "application_field": application_field,
        "product_models": product_models or [],
        "families": line["families"],
        "decision_roles": line["decision_roles"],
        "evidence_requirements": line["evidence_requirements"],
        "tender_focus": line["tender_focus"],
        "classification_status": "classified",
    }


def instrument_domain_catalog() -> dict[str, Any]:
    return {
        "domain_version": INSTRUMENT_DOMAIN_VERSION,
        "instrument_lines": [dict(item) for item in INSTRUMENT_LINES],
    }
