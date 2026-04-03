"""
声明式模型配置加载器

从 YAML 文件加载模型配置，支持：
- 多层级配置（default/tier/scene）
- 环境变量覆盖
- 热重载
"""

import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_config_cache: dict[str, Any] | None = None
_config_mtime: float = 0


def _get_config_path() -> Path:
    """获取配置文件路径"""
    return Path(__file__).parent.parent.parent / "config" / "models.yaml"


def _load_yaml_config() -> dict[str, Any]:
    """加载 YAML 配置文件（带缓存和热重载）"""
    global _config_cache, _config_mtime

    config_path = _get_config_path()
    if not config_path.exists():
        logger.warning(f"Model config not found: {config_path}")
        return {}

    # 检查文件修改时间
    current_mtime = config_path.stat().st_mtime
    if _config_cache and current_mtime == _config_mtime:
        return _config_cache

    # 重新加载
    with open(config_path, encoding="utf-8") as f:
        _config_cache = yaml.safe_load(f) or {}
        _config_mtime = current_mtime
        logger.info(f"Loaded model config from {config_path}")

    return _config_cache


def get_model_config(
    tier: str | None = None,
    scene_code: str | None = None,
) -> dict[str, Any]:
    """
    获取模型配置

    优先级：scene > tier > default
    支持环境变量覆盖：MODEL_{TIER}_PROVIDER, MODEL_{TIER}_MODEL 等
    """
    config = _load_yaml_config()

    # 1. 从 default 开始
    result = config.get("default", {}).copy()

    # 2. 应用 tier 配置
    if tier and tier in config:
        result.update(config[tier])

    # 3. 应用 scene 配置（最高优先级）
    if scene_code and "scenes" in config and scene_code in config["scenes"]:
        result.update(config["scenes"][scene_code])

    # 4. 环境变量覆盖
    env_prefix = f"MODEL_{tier.upper()}_" if tier else "MODEL_"
    if env_model := os.getenv(f"{env_prefix}MODEL"):
        result["model"] = env_model
    if env_provider := os.getenv(f"{env_prefix}PROVIDER"):
        result["provider"] = env_provider
    if env_temp := os.getenv(f"{env_prefix}TEMPERATURE"):
        result["temperature"] = float(env_temp)

    return result


def get_embedding_config() -> dict[str, Any]:
    """获取 Embedding 模型配置"""
    config = _load_yaml_config()
    return config.get("embedding", {
        "provider": "openai",
        "model": "text-embedding-3-large",
        "dimensions": 1536,
    })
