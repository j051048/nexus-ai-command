"""插件市场 API 路由"""

import logging

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.plugin_executor import EXECUTOR_REGISTRY, execute_plugin
from app.services.plugin_marketplace_service import plugin_marketplace_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/plugins", tags=["Plugins"])


@router.get("")
async def list_plugins(
    req: Request,
    category: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """获取插件市场列表"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        plugins = await plugin_marketplace_service.list_plugins(org_id=org_id, category=category, db=db)
        return api_success(data={"plugins": plugins})
    except Exception as e:
        logger.error(f"Failed to list plugins: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/installed")
async def get_installed_plugins(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取已安装的插件"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        plugins = await plugin_marketplace_service.get_installed_plugins(org_id=org_id, db=db)
        return api_success(data={"plugins": plugins})
    except Exception as e:
        logger.error(f"Failed to get installed plugins: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/{plugin_id}/install")
async def install_plugin(
    plugin_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """安装插件"""
    try:
        body = await req.json()
        config = body.get("config", {})
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        result = await plugin_marketplace_service.install_plugin(
            org_id=org_id, plugin_id=plugin_id, config=config, db=db
        )
        return api_success(data={"plugin": result}, message="插件安装成功")
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except Exception as e:
        logger.error(f"Failed to install plugin: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/{plugin_id}/uninstall")
async def uninstall_plugin(
    plugin_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """卸载插件"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        success = await plugin_marketplace_service.uninstall_plugin(org_id=org_id, plugin_id=plugin_id, db=db)
        return api_success(data={"uninstalled": success}, message="插件已卸载")
    except Exception as e:
        logger.error(f"Failed to uninstall plugin: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/{plugin_id}/config")
async def update_plugin_config(
    plugin_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新插件配置"""
    try:
        body = await req.json()
        config = body.get("config", {})
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        result = await plugin_marketplace_service.update_plugin_config(
            org_id=org_id, plugin_id=plugin_id, config=config, db=db
        )
        return api_success(data={"plugin": result}, message="配置已更新")
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except Exception as e:
        logger.error(f"Failed to update plugin config: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ── P3: Plugin Execution API ──


@router.post("/{plugin_id}/execute")
async def execute_plugin_action(
    plugin_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Execute a plugin action.

    Body: {"action": "send_message", "params": {"content": "Hello"}}
    """
    try:
        body = await req.json()
        action = body.get("action", "")
        params = body.get("params", {})

        if not action:
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "Missing 'action' field")

        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)

        # Inject user context into params
        params["user_id"] = user_id
        params["org_id"] = org_id

        result = await execute_plugin(
            plugin_id=plugin_id,
            action=action,
            params=params,
            org_id=org_id,
            db=db,
        )

        if result.get("success"):
            return api_success(data=result, message="插件执行成功")
        else:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, result.get("error", "执行失败"))

    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Plugin execution failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/{plugin_id}/actions")
async def get_plugin_actions(
    plugin_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get available actions for a plugin."""
    executor = EXECUTOR_REGISTRY.get(plugin_id)
    if not executor:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, f"No executor for plugin: {plugin_id}")

    return api_success(
        data={
            "plugin_id": plugin_id,
            "actions": executor.supported_actions(),
        }
    )
