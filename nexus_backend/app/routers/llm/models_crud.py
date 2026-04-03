"""LLM 模型 CRUD 子路由"""

import logging

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import api_success

logger = logging.getLogger(__name__)
router = APIRouter(tags=["LLM Models CRUD"])


@router.get("/models")
async def list_models(req: Request, user_id: str = Depends(get_current_user_id)):
    """获取当前租户的 LLM 模型配置列表"""
    try:
        db = getattr(req.state, "db", None)
        org_id = getattr(req.state, "org_id", None)

        if not db or not org_id:
            return api_success(data=[])

        result = (
            await db.table("llm_model_config")
            .select(
                "id,model_code,model_name,provider_type,adapter_code,"
                "api_base_url,model_id,model_type,timeout_ms,max_tokens,"
                "context_window,supports_tools,supports_streaming,"
                "input_price_per_1m,output_price_per_1m,status,is_default,sort_order"
            )
            .eq("tenant_id", str(org_id))
            .eq("is_deleted", False)
            .order("sort_order")
            .execute()
        )
        return api_success(data=result.data or [])
    except Exception as e:
        logger.error(f"Failed to list LLM models: {e}")
        return api_success(data=[])
