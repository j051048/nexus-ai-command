"""
竞品管理服务 (Competitor Service)

提供竞品公司、竞品产品、对比维度、关联文档的 CRUD 操作。
数据通过 Supabase PostgREST，按 organization_id 隔离。
"""

import logging
import uuid
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

THREAT_LEVELS = ("low", "medium", "high", "critical")


class CompetitorService:
    """竞品管理服务"""

    # ─── 竞品公司 CRUD ─────────────────────────────────────

    async def list_competitors(self, org_id: str, *, active_only: bool = True, db=None) -> list[dict]:
        query = db.table("competitors").select("*").eq("organization_id", org_id)
        if active_only:
            query = query.eq("is_active", True)
        res = await query.order("sort_order").order("created_at", desc=True).execute()
        return res.data or []

    async def get_competitor(self, competitor_id: str, *, db=None) -> dict | None:
        res = await db.table("competitors").select("*").eq("id", competitor_id).maybe_single().execute()
        return res.data

    async def find_by_name(self, name: str, org_id: str, *, db=None) -> dict | None:
        """按名称或品牌名模糊匹配竞品"""
        # 精确匹配
        res = (
            await db.table("competitors")
            .select("*")
            .eq("organization_id", org_id)
            .ilike("name", f"%{name}%")
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]
        # 品牌名匹配 (PostgreSQL array contains)
        res = (
            await db.table("competitors")
            .select("*")
            .eq("organization_id", org_id)
            .contains("brand_names", [name])
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    async def create_competitor(self, org_id: str, user_id: str, data: dict, *, db=None) -> dict:
        if not data.get("name"):
            raise ValueError("竞品名称不能为空")

        threat = data.get("threat_level", "medium")
        if threat not in THREAT_LEVELS:
            raise ValueError(f"无效的威胁等级: {threat}")

        competitor = {
            "id": str(uuid.uuid4()),
            "organization_id": org_id,
            "name": data["name"],
            "brand_names": data.get("brand_names", []),
            "industry": data.get("industry", ""),
            "tag": data.get("tag", ""),
            "logo_url": data.get("logo_url"),
            "website": data.get("website"),
            "description": data.get("description", ""),
            "strength_summary": data.get("strength_summary", ""),
            "weakness_summary": data.get("weakness_summary", ""),
            "threat_level": threat,
            "is_active": True,
            "sort_order": data.get("sort_order", 0),
            "metadata": data.get("metadata", {}),
            "created_by": user_id,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        res = await db.table("competitors").insert(competitor).execute()
        return res.data[0] if res.data else competitor

    async def update_competitor(self, competitor_id: str, data: dict, *, db=None) -> dict:
        update_data = {
            k: v
            for k, v in data.items()
            if k
            in {
                "name",
                "brand_names",
                "industry",
                "tag",
                "logo_url",
                "website",
                "description",
                "strength_summary",
                "weakness_summary",
                "threat_level",
                "is_active",
                "sort_order",
                "metadata",
            }
        }
        if not update_data:
            raise ValueError("没有可更新的字段")

        if "threat_level" in update_data and update_data["threat_level"] not in THREAT_LEVELS:
            raise ValueError(f"无效的威胁等级: {update_data['threat_level']}")

        update_data["updated_at"] = datetime.now(UTC).isoformat()

        res = await db.table("competitors").update(update_data).eq("id", competitor_id).execute()
        return res.data[0] if res.data else update_data

    async def delete_competitor(self, competitor_id: str, *, db=None) -> bool:
        await db.table("competitors").delete().eq("id", competitor_id).execute()
        return True

    # ─── 竞品产品 CRUD ─────────────────────────────────────

    async def list_products(self, competitor_id: str, *, db=None) -> list[dict]:
        res = (
            await db.table("competitor_products")
            .select("*")
            .eq("competitor_id", competitor_id)
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []

    async def create_product(self, competitor_id: str, org_id: str, data: dict, *, db=None) -> dict:
        if not data.get("name"):
            raise ValueError("产品名称不能为空")

        product = {
            "id": str(uuid.uuid4()),
            "competitor_id": competitor_id,
            "organization_id": org_id,
            "name": data["name"],
            "model": data.get("model", ""),
            "category": data.get("category", ""),
            "price_range": data.get("price_range", ""),
            "description": data.get("description", ""),
            "specs": data.get("specs", {}),
            "our_competing_product": data.get("our_competing_product", ""),
            "comparison_notes": data.get("comparison_notes", ""),
            "metadata": data.get("metadata", {}),
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        res = await db.table("competitor_products").insert(product).execute()
        return res.data[0] if res.data else product

    async def update_product(self, product_id: str, data: dict, *, db=None) -> dict:
        update_data = {
            k: v
            for k, v in data.items()
            if k
            in {
                "name",
                "model",
                "category",
                "price_range",
                "description",
                "specs",
                "our_competing_product",
                "comparison_notes",
                "metadata",
            }
        }
        update_data["updated_at"] = datetime.now(UTC).isoformat()
        res = await db.table("competitor_products").update(update_data).eq("id", product_id).execute()
        return res.data[0] if res.data else update_data

    async def delete_product(self, product_id: str, *, db=None) -> bool:
        await db.table("competitor_products").delete().eq("id", product_id).execute()
        return True

    # ─── 对比维度 CRUD ─────────────────────────────────────

    async def list_features(self, competitor_id: str, *, db=None) -> list[dict]:
        res = (
            await db.table("competitor_features")
            .select("*")
            .eq("competitor_id", competitor_id)
            .order("created_at")
            .execute()
        )
        return res.data or []

    async def upsert_feature(self, competitor_id: str, org_id: str, data: dict, *, db=None) -> dict:
        if not data.get("dimension"):
            raise ValueError("对比维度不能为空")

        feature = {
            "competitor_id": competitor_id,
            "organization_id": org_id,
            "dimension": data["dimension"],
            "competitor_score": data.get("competitor_score"),
            "our_score": data.get("our_score"),
            "competitor_detail": data.get("competitor_detail", ""),
            "our_advantage": data.get("our_advantage", ""),
            "counter_strategy": data.get("counter_strategy", ""),
            "metadata": data.get("metadata", {}),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        if data.get("id"):
            res = await db.table("competitor_features").update(feature).eq("id", data["id"]).execute()
        else:
            feature["id"] = str(uuid.uuid4())
            feature["created_at"] = datetime.now(UTC).isoformat()
            res = await db.table("competitor_features").insert(feature).execute()

        return res.data[0] if res.data else feature

    async def delete_feature(self, feature_id: str, *, db=None) -> bool:
        await db.table("competitor_features").delete().eq("id", feature_id).execute()
        return True

    # ─── 文档关联 ─────────────────────────────────────────

    async def list_documents(self, competitor_id: str, *, db=None) -> list[dict]:
        res = (
            await db.table("competitor_documents")
            .select("*, document:document_id(id, title, file_type, file_size, created_at)")
            .eq("competitor_id", competitor_id)
            .execute()
        )
        return res.data or []

    async def link_document(self, competitor_id: str, document_id: str, doc_type: str = "general", *, db=None) -> bool:
        await (
            db.table("competitor_documents")
            .upsert(
                {
                    "competitor_id": competitor_id,
                    "document_id": document_id,
                    "doc_type": doc_type,
                }
            )
            .execute()
        )
        return True

    async def unlink_document(self, competitor_id: str, document_id: str, *, db=None) -> bool:
        await (
            db.table("competitor_documents")
            .delete()
            .eq("competitor_id", competitor_id)
            .eq("document_id", document_id)
            .execute()
        )
        return True

    # ─── 打击卡聚合 ─────────────────────────────────────

    async def get_battlecard_data(self, competitor_id: str, *, db=None) -> dict:
        """聚合竞品结构化数据，用于打击卡生成"""
        competitor = await self.get_competitor(competitor_id, db=db)
        if not competitor:
            return {}

        products = await self.list_products(competitor_id, db=db)
        features = await self.list_features(competitor_id, db=db)
        docs = await self.list_documents(competitor_id, db=db)

        return {
            "competitor": competitor,
            "products": products,
            "features": features,
            "documents": docs,
        }


competitor_service = CompetitorService()
