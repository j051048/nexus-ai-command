"""Curated scientific-instrument scenario packs used before model prompting."""

from __future__ import annotations

from typing import Any

_LINES = {
    "spectroscopy": (
        "光谱",
        ["检出限与线性范围", "光源与检测器配置", "样品前处理", "方法学验证"],
    ),
    "chromatography": (
        "色谱",
        ["分离度与重复性", "进样通量", "柱与耗材", "数据完整性"],
    ),
    "mass_spectrometry": (
        "质谱",
        ["灵敏度与质量范围", "离子源兼容", "定量方法", "环境与气路"],
    ),
    "energy_spectroscopy": (
        "能谱",
        ["能量分辨率", "探测效率", "样品仓与安全", "谱图分析"],
    ),
    "electronic_instrumentation": (
        "电子仪器",
        ["带宽与精度", "通道与接口", "自动化协议", "校准与可追溯性"],
    ),
}

_INDUSTRIES = {
    "制药": ["GMP/数据完整性", "方法转移", "审计追踪", "验证文件"],
    "高校科研": ["课题方向", "开放共享", "预算来源", "培训与论文产出"],
    "第三方检测": ["日均样本量", "资质范围", "周转时间", "LIMS 对接"],
    "半导体": ["洁净环境", "自动化集成", "量测重复性", "产线节拍"],
    "新能源": ["材料体系", "原位测试", "安全边界", "多尺度表征"],
    "环境与食品": ["标准方法", "前处理通量", "检出限", "质控样与报告"],
}


def list_scenario_packs() -> list[dict[str, Any]]:
    packs: list[dict[str, Any]] = []
    for line_code, (line_name, line_facts) in _LINES.items():
        for industry, industry_facts in _INDUSTRIES.items():
            packs.append(
                {
                    "code": f"{line_code}:{industry}",
                    "name": f"{industry}{line_name}方案",
                    "instrument_line_code": line_code,
                    "industry": industry,
                    "required_facts": line_facts + industry_facts,
                    "section_outline": [
                        "客户目标",
                        "需求与证据",
                        "技术路线",
                        "配置与报价",
                        "实施验收",
                        "服务保障",
                    ],
                }
            )
    return packs


def get_scenario_pack(code: str | None) -> dict[str, Any] | None:
    if not code:
        return None
    return next((item for item in list_scenario_packs() if item["code"] == code), None)
