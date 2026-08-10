"""Versioned delivery packs for the five commercial instrument lines."""

from __future__ import annotations

from typing import Any

from app.services.scientific_instrument_domain import normalize_instrument_line

DOMAIN_PACK_VERSION = "scientific-delivery-packs.v1"

DOMAIN_PACKS: dict[str, dict[str, tuple[str, ...]]] = {
    "spectroscopy": {
        "decision_dimensions": (
            "样品类型、基体与目标元素/官能团",
            "波长范围、光谱分辨率、检出限与重复性",
            "光源、光路、检测器、附件和方法库",
            "标准物质实测、方法验证与实验室环境条件",
        ),
        "acceptance_checks": (
            "用标准物质核验波长准确度、重复性和检出能力",
            "记录光源预热、基线稳定性、环境和样品前处理条件",
        ),
        "standards_focus": ("行业检测方法标准", "计量校准规范", "数据完整性要求"),
        "forbidden_claims": ("未实测即承诺检出限", "跨技术路线直接比较单一参数"),
    },
    "chromatography": {
        "decision_dimensions": (
            "目标组分、基质、前处理、色谱柱和流动相",
            "压力、流量范围、梯度性能、保留时间与峰面积重复性",
            "检测器、自动进样、柱温箱、软件和耗材全周期成本",
            "现有方法迁移、系统适用性与样品通量",
        ),
        "acceptance_checks": (
            "用客户方法核验分离度、保留时间和峰面积重复性",
            "记录压力脉动、梯度准确度、残留和方法迁移偏差",
        ),
        "standards_focus": ("药典/行业分析方法", "系统适用性", "审计追踪与电子记录"),
        "forbidden_claims": ("忽略色谱柱和基质差异承诺分离效果", "隐去耗材成本"),
    },
    "mass_spectrometry": {
        "decision_dimensions": (
            "目标化合物、离子化模式、基质效应与定量范围",
            "质量范围、分辨率、质量精度、灵敏度与扫描速度",
            "离子源、前端分离、数据库、定量软件和数据处理链",
            "真实基质实测、稳定性、维护频率和运行成本",
        ),
        "acceptance_checks": (
            "用客户真实基质核验定量下限、线性、精密度和回收率",
            "记录质量轴校准、离子源条件、批间漂移和交叉污染",
        ),
        "standards_focus": ("生物分析/残留检测方法", "定量方法验证", "数据可追溯性"),
        "forbidden_claims": ("以纯溶液灵敏度替代真实基质能力", "虚构数据库覆盖率"),
    },
    "energy_spectroscopy": {
        "decision_dimensions": (
            "材料体系、元素范围、轻元素需求与空间/表面分辨需求",
            "能量分辨率、计数率、探测面积和几何条件",
            "主机兼容、真空/环境条件、标准样品和定量模型",
            "联机控制、谱库、标定、漂移修正和安全条件",
        ),
        "acceptance_checks": (
            "用标准样品核验峰位、分辨率、计数率和重复性",
            "记录束流/管压、几何、真空、死时间和定量校正条件",
        ),
        "standards_focus": ("材料/矿物分析方法", "辐射安全", "能量与计数标定"),
        "forbidden_claims": (
            "脱离测试几何比较检出能力",
            "未说明基体效应即承诺定量精度",
        ),
    },
    "electronic_instrumentation": {
        "decision_dimensions": (
            "被测对象、信号频段、通道、动态范围和自动化场景",
            "带宽、采样率、噪声、测量精度、相位与时基性能",
            "探头/夹具、校准、不确定度、SCPI/LXI/OPC-UA 集成",
            "研发验证、产线节拍、数据接口和二次开发边界",
        ),
        "acceptance_checks": (
            "用可溯源标准源核验幅度、频率、时基和通道一致性",
            "验证远程命令、异常恢复、数据导出和自动化节拍",
        ),
        "standards_focus": ("计量校准规范", "EMC/电气安全", "自动化接口与数据安全"),
        "forbidden_claims": ("仅凭带宽宣称整体性能领先", "未验证接口即承诺无缝集成"),
    },
}


def get_domain_pack(line_code: str | None) -> dict[str, Any] | None:
    normalized = normalize_instrument_line(line_code)
    pack = DOMAIN_PACKS.get(normalized or "")
    if not pack:
        return None
    return {
        "version": DOMAIN_PACK_VERSION,
        "instrument_line": normalized,
        **{key: list(value) for key, value in pack.items()},
    }


def build_domain_pack_prompt(line_code: str | None) -> str:
    pack = get_domain_pack(line_code)
    if not pack:
        return ""
    dimensions = "\n".join(f"- {item}" for item in pack["decision_dimensions"])
    acceptance = "\n".join(f"- {item}" for item in pack["acceptance_checks"])
    standards = "、".join(pack["standards_focus"])
    forbidden = "、".join(pack["forbidden_claims"])
    return (
        f"\n## Instrument domain pack ({pack['instrument_line']}@{pack['version']})\n"
        f"Decision dimensions:\n{dimensions}\n"
        f"Acceptance evidence:\n{acceptance}\n"
        f"Standards focus: {standards}.\n"
        f"Forbidden shortcuts: {forbidden}."
    )
