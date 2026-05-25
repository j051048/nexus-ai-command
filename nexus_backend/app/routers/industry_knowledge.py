"""Scientific instrument industry knowledge assets.

The endpoint keeps the initial asset catalog server-side so teams can evolve
industry playbooks without coupling every consumer to frontend-only constants.
When the managed table is present it becomes the source of truth; otherwise the
built-in catalog provides a deterministic launch baseline.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_org_id, get_current_user_id
from app.core.dependencies import get_request_db
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/industry-knowledge", tags=["Industry Knowledge"])

AssetType = Literal["competitor", "tender", "customer_chain", "sales_play"]


class IndustryKnowledgeAsset(BaseModel):
    id: str
    title: str
    type: AssetType
    scenario: str
    description: str
    tags: list[str] = Field(default_factory=list)
    framework: list[str] = Field(default_factory=list)
    ai_prompt: str
    owner: str = "sales-enablement"
    status: Literal["active", "draft", "archived"] = "active"
    evidence_count: int = 0
    version: int = 1
    updated_at: str | None = None


BUILTIN_ASSETS: list[IndustryKnowledgeAsset] = [
    IndustryKnowledgeAsset(
        id="thermo-fisher-lcms-battlecard",
        title="Thermo Fisher LC/MS 竞品对比框架",
        type="competitor",
        scenario="液质联用采购、质谱平台更新、科研平台招标",
        description="围绕灵敏度、稳定性、软件生态、耗材成本、服务网络和论文背书构建可复用战卡。",
        tags=["LC/MS", "Thermo Fisher", "竞品参数", "售前论证"],
        framework=[
            "核心指标：检测限、线性范围、质量准确度、扫描速度",
            "业务指标：样本通量、维护停机、耗材与维保成本",
            "证据材料：论文引用、标杆客户、应用方案、售后响应",
            "反击话术：把单点参数优势转译为全生命周期收益",
        ],
        ai_prompt="请基于 Thermo Fisher LC/MS 竞品对比框架，为我的产品生成一份销售战卡，包含参数对比、客户关切、反击话术和证据材料清单。",
        evidence_count=4,
    ),
    IndustryKnowledgeAsset(
        id="agilent-chromatography-battlecard",
        title="Agilent 色谱系统对标框架",
        type="competitor",
        scenario="高校实验室、第三方检测、药企 QC 色谱采购",
        description="把硬件稳定性、软件工作流、方法迁移、耗材锁定和售后能力拆成可评分维度。",
        tags=["HPLC", "GC", "Agilent", "方法迁移"],
        framework=[
            "系统能力：泵稳定性、进样精度、柱温控制、检测器灵敏度",
            "迁移成本：现有方法兼容、人员学习成本、历史数据连续性",
            "采购风险：耗材绑定、维保周期、备件交付、停机损失",
            "成交策略：先证明方法迁移，再谈总体拥有成本",
        ],
        ai_prompt="请按 Agilent 色谱系统对标框架，帮我准备一份给药企 QC 客户的竞品对比和方法迁移沟通提纲。",
        evidence_count=3,
    ),
    IndustryKnowledgeAsset(
        id="shimadzu-technical-comparison",
        title="Shimadzu 色谱质谱技术对标框架",
        type="competitor",
        scenario="预算敏感型高校、区域检测中心、国产替代论证",
        description="用于把参数、价格、服务、培训和国产替代政策组合成可解释的采购建议。",
        tags=["Shimadzu", "GC-MS", "国产替代", "预算论证"],
        framework=[
            "参数对照：灵敏度、分辨率、稳定性、自动化程度",
            "采购论证：预算约束、国产替代政策、平台共享效率",
            "实施风险：安装周期、培训计划、方法包成熟度",
            "赢单抓手：把预算优势与可交付服务承诺绑定",
        ],
        ai_prompt="请使用 Shimadzu 色谱质谱技术对标框架，生成一份预算敏感客户的采购论证材料和异议处理话术。",
        evidence_count=3,
    ),
    IndustryKnowledgeAsset(
        id="tender-score-breakdown",
        title="招投标评分拆解模板",
        type="tender",
        scenario="公开招标、竞争性磋商、技术方案打分前评估",
        description="把招标文件拆成硬性门槛、技术分、商务分、服务分和风险条款，提前预测失分点。",
        tags=["招标文件", "评分标准", "技术偏离表", "风险条款"],
        framework=[
            "资格门槛：资质、授权、业绩、交付周期",
            "技术分：关键参数、偏离条款、检测报告、应用案例",
            "商务分：报价策略、付款条件、质保承诺、备件价格",
            "风险项：排他参数、模糊验收、服务半径、违约责任",
        ],
        ai_prompt="请按招投标评分拆解模板分析这份招标文件，输出预计得分、硬性风险、可补证据和投标策略。",
        evidence_count=5,
    ),
    IndustryKnowledgeAsset(
        id="research-institute-buying-chain",
        title="高校/科研院所采购决策链",
        type="customer_chain",
        scenario="课题组设备采购、公共平台采购、学院统筹采购",
        description="识别 PI、实验老师、平台负责人、采购办、财务和使用学生的不同诉求。",
        tags=["高校客户", "科研院所", "决策链", "采购办"],
        framework=[
            "PI：研究方向、论文产出、平台影响力、预算来源",
            "实验老师：易用性、稳定性、培训、售后响应",
            "采购办：合规、价格、资质、验收文件",
            "学生/用户：方法模板、上手速度、排队效率",
        ],
        ai_prompt="请根据高校/科研院所采购决策链，为这个客户生成角色地图、关键问题清单和下一步跟进节奏。",
        evidence_count=4,
    ),
    IndustryKnowledgeAsset(
        id="funding-lead-follow-up",
        title="基金/课题线索跟进节奏",
        type="sales_play",
        scenario="国自然、科技部项目、重点实验室建设、论文方向线索",
        description="把基金立项、论文关键词和平台建设计划转成客户触达、资料准备和商机推进节奏。",
        tags=["基金线索", "论文线索", "重点实验室", "销售节奏"],
        framework=[
            "线索识别：项目名称、关键词、负责人、预算周期",
            "触达时机：立项后 30 天、预算确认、方案论证前",
            "资料准备：应用案例、技术路线、设备配置建议",
            "推进节奏：首访、技术交流、样机演示、方案固化",
        ],
        ai_prompt="请按基金/课题线索跟进节奏，把这条科研项目线索转成客户触达话术、资料清单和 30 天推进计划。",
        evidence_count=2,
    ),
]


def _from_row(row: dict[str, Any]) -> IndustryKnowledgeAsset:
    metadata = row.get("metadata") or {}
    return IndustryKnowledgeAsset(
        id=str(row.get("asset_id") or row.get("id")),
        title=str(row.get("title") or "未命名行业资产"),
        type=row.get("asset_type") or row.get("type") or "sales_play",
        scenario=str(row.get("scenario") or ""),
        description=str(row.get("description") or ""),
        tags=list(row.get("tags") or []),
        framework=list(row.get("framework") or []),
        ai_prompt=str(row.get("ai_prompt") or row.get("prompt") or ""),
        owner=str(row.get("owner") or metadata.get("owner") or "sales-enablement"),
        status=row.get("status") or "active",
        evidence_count=int(
            row.get("evidence_count") or metadata.get("evidence_count") or 0
        ),
        version=int(row.get("version") or 1),
        updated_at=row.get("updated_at"),
    )


@router.get("/assets")
async def list_industry_knowledge_assets(
    request: Request,
    asset_type: AssetType | None = Query(None),
    status: str = Query("active"),
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    """List productized scientific-instrument knowledge assets."""
    try:
        client = get_request_db(request)
        query = (
            client.table("industry_knowledge_assets")
            .select("*")
            .eq("organization_id", org_id)
            .eq("status", status)
            .order("updated_at", desc=True)
        )
        if asset_type:
            query = query.eq("asset_type", asset_type)
        res = await query.execute()
        assets = [_from_row(row) for row in (res.data or [])]
        source = "database"
    except Exception as exc:
        logger.info(
            "Industry knowledge table unavailable for user=%s org=%s: %s",
            user_id,
            org_id,
            exc,
        )
        assets = BUILTIN_ASSETS
        source = "builtin"
        if asset_type:
            assets = [asset for asset in assets if asset.type == asset_type]

    summary = {
        "total": len(assets),
        "by_type": {
            type_name: sum(1 for asset in assets if asset.type == type_name)
            for type_name in ["competitor", "tender", "customer_chain", "sales_play"]
        },
        "evidence_count": sum(asset.evidence_count for asset in assets),
    }
    return api_success(
        data={
            "items": [asset.model_dump() for asset in assets],
            "summary": summary,
            "source": source,
        }
    )


@router.get("/assets/{asset_id}")
async def get_industry_knowledge_asset(
    asset_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    """Return one industry knowledge asset by stable id."""
    try:
        client = get_request_db(request)
        res = (
            await client.table("industry_knowledge_assets")
            .select("*")
            .eq("organization_id", org_id)
            .eq("asset_id", asset_id)
            .limit(1)
            .execute()
        )
        if res.data:
            return api_success(
                data={
                    "asset": _from_row(res.data[0]).model_dump(),
                    "source": "database",
                }
            )
    except Exception as exc:
        logger.info("Industry knowledge detail fallback: user=%s err=%s", user_id, exc)

    asset = next((item for item in BUILTIN_ASSETS if item.id == asset_id), None)
    if not asset:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "行业知识资产不存在")
    return api_success(data={"asset": asset.model_dump(), "source": "builtin"})
