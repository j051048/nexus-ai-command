import asyncio
import logging
from datetime import datetime, timedelta

from app.core.celery_app import celery_app
from app.services.crawler_service import crawler_service

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async code in sync Celery tasks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task
def crawl_arxiv_leads():
    """
    Scheduled task to run the Crawler Service.
    Daily 2:00 AM job.
    """
    papers = crawler_service.crawl_arxiv(query="Raman Spectroscopy", max_results=3)
    for paper in papers:
        crawler_service.analyze_and_push_lead(paper)
    return f"Crawled and processed {len(papers)} papers."


@celery_app.task
def push_daily_briefing():
    """
    3.1 每日晨报推送
    每天早8点推送给所有 manager/founder 角色用户
    """

    async def _run():
        from app.core.database import supabase
        from app.services.notification_service import send_notification
        from app.tools.boss_tools import DailyBriefingTool

        if not supabase:
            logger.warning("DB not available, skipping daily briefing")
            return "skipped: no db"

        # 查询所有管理层用户 (founder = boss, manager = 管理者)
        result = await supabase.table("users").select("id, role").in_("role", ["manager", "founder"]).execute()
        users = result.data or []

        tool = DailyBriefingTool()
        sent = 0
        for u in users:
            try:
                briefing = await tool.run({}, u["id"], config={})
                await send_notification(
                    title="每日晨报",
                    content=briefing[:500],
                    target_user_id=u["id"],
                )
                sent += 1
            except Exception as e:
                logger.error(f"Briefing failed for user {u['id']}: {e}")

        return f"Sent daily briefing to {sent}/{len(users)} users"

    return _run_async(_run())


@celery_app.task
def mine_sales_leads():
    """
    3.3 商机线索挖掘
    扫描7天+未跟进的线索，生成AI跟进建议并通知负责人
    """

    async def _run():
        from app.core.database import supabase
        from app.services.ai_service import AIService
        from app.services.notification_service import send_notification

        if not supabase:
            return "skipped: no db"

        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()

        result = (
            await supabase.table("sales_leads")
            .select("id, company_name, status, assigned_to, updated_at")
            .eq("status", "lead")
            .lt("updated_at", seven_days_ago)
            .limit(20)
            .execute()
        )

        stale_leads = result.data or []
        if not stale_leads:
            return "No stale leads found"

        processed = 0
        for lead in stale_leads:
            try:
                suggestion = await AIService.call_llm(
                    f"商机: {lead['company_name']}, 状态: {lead['status']}, " f"最后更新: {lead['updated_at']}",
                    "你是销售顾问。这个线索已经超过7天未跟进，请给出简短的跟进建议（1-2句话）。",
                )
                if lead.get("assigned_to"):
                    await send_notification(
                        title=f"线索跟进提醒: {lead['company_name']}",
                        content=suggestion[:300],
                        target_user_id=lead["assigned_to"],
                    )
                processed += 1
            except Exception as e:
                logger.error(f"Lead mining failed for {lead['id']}: {e}")

        return f"Processed {processed} stale leads"

    return _run_async(_run())


@celery_app.task
def monitor_competitors():
    """
    3.4 竞品监控
    查询竞品分析记录，生成AI竞品动态分析
    """

    async def _run():
        from app.core.database import supabase
        from app.services.ai_service import AIService
        from app.services.notification_service import send_notification

        if not supabase:
            return "skipped: no db"

        # 查询近期竞品分析
        try:
            result = (
                await supabase.table("battlecard_analyses")
                .select("id, competitor_name, user_id, created_at")
                .order("created_at", desc=True)
                .limit(10)
                .execute()
            )
        except Exception:
            logger.info("battlecard_analyses table not available")
            return "skipped: table not available"

        analyses = result.data or []
        if not analyses:
            return "No competitor data"

        # 汇总竞品名称
        competitors = list(set(a.get("competitor_name", "") for a in analyses if a.get("competitor_name")))
        if not competitors:
            return "No competitors found"

        try:
            analysis = await AIService.call_llm(
                f"我们跟踪的竞品列表: {', '.join(competitors[:5])}",
                "你是竞争情报分析师。根据竞品列表，生成简短的竞品动态提醒（3-5条要点），用中文。",
            )

            # 通知所有相关用户
            user_ids = list(set(a.get("user_id") for a in analyses if a.get("user_id")))
            for uid in user_ids[:10]:
                await send_notification(
                    title="竞品动态周报",
                    content=analysis[:500],
                    target_user_id=uid,
                )

            return f"Competitor analysis sent to {len(user_ids)} users"
        except Exception as e:
            logger.error(f"Competitor monitoring failed: {e}")
            return f"failed: {e}"

    return _run_async(_run())


@celery_app.task
def cleanup_stale_embeddings():
    """
    知识库GC: 检测过期文档embedding并清理
    - 检测 staleness_days 天未更新的过期 embedding
    - 清理已标记 expires_at 过期的 embedding
    - 通知文档所有者更新知识库
    """

    async def _run():
        from app.core.database import supabase
        from app.services.vector_service import VectorService

        if not supabase:
            return "skipped: no db"

        vs = VectorService()

        # 1. Get all active org_ids
        try:
            orgs_res = await supabase.table("organizations").select("id").execute()
            org_ids = [o["id"] for o in (orgs_res.data or [])]
        except Exception:
            org_ids = ["default"]

        total_stale = 0
        total_expired = 0

        for org_id in org_ids:
            try:
                # Check for stale embeddings (default 30 days)
                stale_docs = await vs.check_staleness(org_id, staleness_days=30, db=supabase)
                total_stale += len(stale_docs)

                # Log stale documents for monitoring
                if stale_docs:
                    logger.info(f"Org {org_id}: {len(stale_docs)} stale documents found")

                # Clean up expired embeddings (where expires_at < now)
                try:
                    expired_res = (
                        await supabase.table("document_embeddings")
                        .select("id, document_id")
                        .eq("organization_id", org_id)
                        .lt("expires_at", datetime.now().isoformat())
                        .not_.is_("expires_at", "null")
                        .limit(500)
                        .execute()
                    )
                    expired = expired_res.data or []

                    for chunk in expired:
                        try:
                            await supabase.table("document_embeddings").delete().eq("id", chunk["id"]).execute()
                            total_expired += 1
                        except Exception as del_e:
                            if not (hasattr(del_e, "code") and str(getattr(del_e, "code", "")) == "204"):
                                logger.warning(f"Failed to delete expired embedding {chunk['id']}: {del_e}")
                            else:
                                total_expired += 1
                except Exception as e:
                    logger.debug(f"Expired embedding cleanup skipped for {org_id}: {e}")

            except Exception as e:
                logger.error(f"Knowledge base GC failed for org {org_id}: {e}")

        return f"GC complete: {total_stale} stale docs detected, {total_expired} expired embeddings cleaned"

    return _run_async(_run())


@celery_app.task
def aggregate_ai_quality_metrics():
    """每日聚合AI质量指标"""

    async def _run():
        from app.core.database import supabase
        from app.services.ai_quality_service import ai_quality_service

        if not supabase:
            return "skipped: no db"

        # Aggregate for all orgs
        try:
            orgs_res = await supabase.table("organizations").select("id").execute()
            org_ids = [o["id"] for o in (orgs_res.data or [])]
        except Exception:
            org_ids = []

        # Also aggregate global (no tenant filter)
        await ai_quality_service.aggregate_daily_metrics(tenant_id=None)

        for org_id in org_ids:
            try:
                await ai_quality_service.aggregate_daily_metrics(tenant_id=org_id)
            except Exception as e:
                logger.error(f"Quality aggregation failed for {org_id}: {e}")

        return f"AI quality metrics aggregated for {len(org_ids)} orgs"

    return _run_async(_run())


@celery_app.task
def check_contract_expiry():
    """
    3.5 合同到期预警
    查询30天内到期的合同，发送预警通知
    """

    async def _run():
        from app.core.database import supabase
        from app.services.notification_service import NotificationPriority, send_notification

        if not supabase:
            return "skipped: no db"

        thirty_days_later = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")

        try:
            result = (
                await supabase.table("contracts")
                .select("id, title, end_date, user_id, status")
                .gte("end_date", today)
                .lte("end_date", thirty_days_later)
                .eq("status", "active")
                .execute()
            )
        except Exception:
            logger.info("contracts table not available")
            return "skipped: table not available"

        expiring = result.data or []
        if not expiring:
            return "No expiring contracts"

        notified = 0
        for contract in expiring:
            try:
                if contract.get("user_id"):
                    days_left = (datetime.strptime(contract["end_date"], "%Y-%m-%d") - datetime.now()).days
                    await send_notification(
                        title=f"合同到期预警: {contract.get('title', '未命名')}",
                        content=f"合同将在 {days_left} 天后到期 ({contract['end_date']})，请及时处理续签或结算。",
                        target_user_id=contract["user_id"],
                        priority=NotificationPriority.HIGH,
                    )
                    notified += 1
            except Exception as e:
                logger.error(f"Contract expiry notification failed for {contract['id']}: {e}")

        return f"Notified {notified} expiring contracts"

    return _run_async(_run())
