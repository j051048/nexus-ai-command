"""Canonical parameter ontology for the five scientific-instrument lines."""

from __future__ import annotations

import re
from typing import Any

from app.services.scientific_instrument_domain import normalize_instrument_line

ONTOLOGY_VERSION = "scientific-instrument-parameters.v1"

COMMON_PARAMETERS = {
    "throughput": {
        "label": "样品通量",
        "unit": "samples/h",
        "aliases": ["通量", "样品通量", "throughput"],
    },
    "repeatability": {
        "label": "重复性",
        "unit": "%",
        "aliases": ["重复性", "rsd", "repeatability"],
    },
}

PARAMETERS: dict[str, dict[str, dict[str, Any]]] = {
    "spectroscopy": {
        "wavelength_range": {
            "label": "波长范围",
            "unit": "nm",
            "aliases": ["波长范围", "wavelength range", "光谱范围"],
        },
        "spectral_resolution": {
            "label": "光谱分辨率",
            "unit": "nm",
            "aliases": ["分辨率", "光谱分辨率", "resolution"],
        },
        "detection_limit": {
            "label": "检出限",
            "unit": "mg/L",
            "aliases": ["检出限", "检测限", "lod", "detection limit"],
        },
    },
    "chromatography": {
        "pressure_limit": {
            "label": "最高工作压力",
            "unit": "MPa",
            "aliases": ["最高压力", "耐压", "pressure limit", "maximum pressure"],
        },
        "flow_range": {
            "label": "流量范围",
            "unit": "mL/min",
            "aliases": ["流量范围", "flow range"],
        },
        "retention_time_rsd": {
            "label": "保留时间重复性",
            "unit": "%",
            "aliases": ["保留时间重复性", "保留时间rsd", "retention time rsd"],
        },
    },
    "mass_spectrometry": {
        "mass_range": {
            "label": "质量范围",
            "unit": "m/z",
            "aliases": ["质量范围", "质荷比范围", "mass range"],
        },
        "mass_resolution": {
            "label": "质量分辨率",
            "unit": "FWHM",
            "aliases": ["质量分辨率", "分辨率", "mass resolution"],
        },
        "mass_accuracy": {
            "label": "质量精度",
            "unit": "ppm",
            "aliases": ["质量精度", "质量准确度", "mass accuracy"],
        },
        "sensitivity": {
            "label": "灵敏度",
            "unit": "",
            "aliases": ["灵敏度", "sensitivity"],
        },
    },
    "energy_spectroscopy": {
        "energy_resolution": {
            "label": "能量分辨率",
            "unit": "eV",
            "aliases": ["能量分辨率", "energy resolution"],
        },
        "count_rate": {
            "label": "最大计数率",
            "unit": "cps",
            "aliases": ["计数率", "最大计数率", "count rate"],
        },
        "detector_area": {
            "label": "探测面积",
            "unit": "mm2",
            "aliases": ["探测面积", "探测器面积", "detector area"],
        },
    },
    "electronic_instrumentation": {
        "bandwidth": {"label": "带宽", "unit": "MHz", "aliases": ["带宽", "bandwidth"]},
        "sample_rate": {
            "label": "采样率",
            "unit": "GSa/s",
            "aliases": ["采样率", "sample rate", "sampling rate"],
        },
        "dynamic_range": {
            "label": "动态范围",
            "unit": "dB",
            "aliases": ["动态范围", "dynamic range"],
        },
        "measurement_accuracy": {
            "label": "测量精度",
            "unit": "%",
            "aliases": ["测量精度", "精度", "measurement accuracy"],
        },
    },
}

_NUMBER_WITH_UNIT = re.compile(
    r"^\s*([<>≤≥~约]?)\s*(-?\d+(?:\.\d+)?)\s*([a-zA-Zμµ%/²0-9.-]*)\s*$"
)


def _lookup(line_code: str | None) -> tuple[str | None, dict[str, dict[str, Any]]]:
    normalized = normalize_instrument_line(line_code)
    definitions = {**COMMON_PARAMETERS, **PARAMETERS.get(normalized or "", {})}
    return normalized, definitions


def normalize_product_specs(
    line_code: str | None, key_specs: dict[str, Any] | None
) -> dict[str, Any]:
    """Preserve source values while adding canonical keys and verification hints."""
    normalized_line, definitions = _lookup(line_code)
    alias_index = {
        alias.strip().lower(): (key, definition)
        for key, definition in definitions.items()
        for alias in [key, definition["label"], *definition.get("aliases", [])]
    }
    values: dict[str, Any] = {}
    unknown: dict[str, Any] = {}
    warnings: list[str] = []
    for source_key, raw_value in dict(key_specs or {}).items():
        match = alias_index.get(str(source_key).strip().lower())
        if not match:
            unknown[str(source_key)] = raw_value
            continue
        canonical_key, definition = match
        value_text = str(raw_value).strip()
        parsed = _NUMBER_WITH_UNIT.match(value_text)
        unit = parsed.group(3) if parsed else ""
        expected_unit = str(definition.get("unit") or "")
        if expected_unit and not unit:
            warnings.append(
                f"{definition['label']}缺少单位，建议核验为 {expected_unit}"
            )
        values[canonical_key] = {
            "label": definition["label"],
            "value": raw_value,
            "source_key": str(source_key),
            "observed_unit": unit or None,
            "expected_unit": expected_unit or None,
            "verification_status": (
                "needs_review" if expected_unit and not unit else "structured"
            ),
        }
    missing = [
        definition["label"]
        for key, definition in definitions.items()
        if key not in values and key not in COMMON_PARAMETERS
    ]
    return {
        "version": ONTOLOGY_VERSION,
        "instrument_line_code": normalized_line,
        "normalized_specs": values,
        "unmapped_specs": unknown,
        "missing_recommended_parameters": missing,
        "warnings": warnings,
    }


def build_parameter_prompt_context(
    line_code: str | None, key_specs: dict[str, Any] | None
) -> dict[str, Any]:
    snapshot = normalize_product_specs(line_code, key_specs)
    return {
        "ontology_version": snapshot["version"],
        "instrument_line_code": snapshot["instrument_line_code"],
        "verified_parameter_candidates": snapshot["normalized_specs"],
        "missing_parameters": snapshot["missing_recommended_parameters"],
        "writing_rule": "仅引用有来源的参数；缺单位、缺来源或冲突参数必须标记待核验。",
    }
