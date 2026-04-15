import asyncio
import contextlib
import logging
import os
from datetime import UTC, datetime, timedelta
from functools import wraps

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


def _with_redis_lock(task_name: str, lock_ttl: int = 300):
    """Decorator: acquire a Redis lock before executing. Skip if already locked."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            redis_client = None
            lock_key = f"celery_lock:{task_name}"
            try:
                import redis as _redis

                redis_url = os.getenv("REDIS_URL")
                if redis_url:
                    redis_client = _redis.from_url(redis_url)
                    if not redis_client.set(lock_key, "1", nx=True, ex=lock_ttl):
                        logger.info(
                            "[%s] Another worker is executing, skipped", task_name
                        )
                        return "skipped: locked by another worker"
            except Exception as e:
                logger.debug(
                    "[%s] Redis lock unavailable, proceeding: %s", task_name, e
                )

            try:
                return func(*args, **kwargs)
            finally:
                if redis_client:
                    with contextlib.suppress(Exception):
                        redis_client.delete(lock_key)

        return wrapper

    return decorator


@celery_app.task
@_with_redis_lock("crawl_arxiv_leads", lock_ttl=600)
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
@_with_redis_lock("push_daily_briefing", lock_ttl=600)
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

        # P0 Security: 按组织遍历，使用 OrgFilteredClient 防止跨租户数据泄露
        orgs_res = (
            await supabase.table("organizations").select("id").execute()
        )
        org_ids = [o["id"] for o in (orgs_res.data or [])]

        tool = DailyBriefingTool()
        sent = 0
        for org_id in org_ids:
            try:
                org_client = supabase.get_org_filtered_client(org_id)
                # 查询该组织的管理层用户
                result = (
                    await org_client.table("users")
                    .select("id, role")
                    .in_("role", ["manager", "founder"])
                    .execute()
                )
                users = result.data or []

                for u in users:
                    try:
                        briefing = await tool.run({}, u["id"], config={"org_id": org_id})
                        await send_notification(
                            title="每日晨报",
                            content=briefing[:500],
                            target_user_id=u["id"],
                        )
                        sent += 1
                    except Exception as e:
                        logger.error(f"Briefing failed for user {u['id']}: {e}")
            except Exception as e:
                logger.error(f"Daily briefing failed for org {org_id}: {e}")

        return f"Sent daily briefing to {sent} users across {len(org_ids)} orgs"

    return _run_async(_run())


@celery_app.task
@_with_redis_lock("mine_sales_leads", lock_ttl=600)
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

        # P0 Security: 按组织遍历，防止跨租户数据泄露
        orgs_res = (
            await supabase.table("organizations").select("id").execute()
        )
        org_ids = [o["id"] for o in (orgs_res.data or [])]

        processed = 0
        for org_id in org_ids:
            try:
                org_client = supabase.get_org_filtered_client(org_id)
                result = (
                    await org_client.table("sales_leads")
                    .select("*")
                    .eq("stage", "lead")
                    .lt("updated_at", seven_days_ago)
                    .limit(20)
                    .execute()
                )

                stale_leads = result.data or []
                for lead in stale_leads:
                    try:
                        suggestion = await AIService.call_llm(
                            f"商机: {lead.get('company_name', '')}, 状态: {lead.get('status', '')}, 最后更新: {lead.get('updated_at', '')}",
                            "你是销售顾问。这个线索已经超过7天未跟进，请给出简短的跟进建议（1-2句话）。",
                        )
                        if lead.get("assigned_to"):
                            await send_notification(
                                title=f"线索跟进提醒: {lead.get('company_name', '')}",
                                content=suggestion[:300],
                                target_user_id=lead["assigned_to"],
                            )
                        processed += 1
                    except Exception as e:
                        logger.error(f"Lead mining failed for {lead.get('id', '?')}: {e}")
            except Exception as e:
                logger.error(f"Lead mining failed for org {org_id}: {e}")

        return f"Processed {processed} stale leads across {len(org_ids)} orgs"

    return _run_async(_run())


@celery_app.task
@_with_redis_lock("monitor_competitors", lock_ttl=600)
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

        # P0 Security: 按组织遍历，防止跨租户数据泄露
        orgs_res = (
            await supabase.table("organizations").select("id").execute()
        )
        org_ids = [o["id"] for o in (orgs_res.data or [])]
        total_notified = 0

        for org_id in org_ids:
            try:
                org_client = supabase.get_org_filtered_client(org_id)
                # 查询该组织的近期竞品分析
                result = (
                    await org_client.table("battlecard_analyses")
                    .select("id, competitor_name, user_id, created_at")
                    .order("created_at", desc=True)
                    .limit(10)
                    .execute()
                )
            except Exception:
                logger.info(f"battlecard_analyses table not available for org {org_id}")
                continue

            analyses = result.data or []
            if not analyses:
                continue

            # 汇总竞品名称
            competitors = list(
                set(
                    a.get("competitor_name", "")
                    for a in analyses
                    if a.get("competitor_name")
                )
            )
            if not competitors:
                continue

            try:
                analysis = await AIService.call_llm(
                    f"我们跟踪的竞品列表: {', '.join(competitors[:5])}",
                    "你是竞争情报分析师。根据竞品列表，生成简短的竞品动态提醒（3-5条要点），用中文。",
                )

                # 仅通知该组织的相关用户
                user_ids = list(set(a.get("user_id") for a in analyses if a.get("user_id")))
                for uid in user_ids[:10]:
                    await send_notification(
                        title="竞品动态周报",
                        content=analysis[:500],
                        target_user_id=uid,
                    )
                    total_notified += 1
            except Exception as e:
                logger.error(f"Competitor monitoring failed for org {org_id}: {e}")

        return f"Competitor analysis sent to {total_notified} users across {len(org_ids)} orgs"

    return _run_async(_run())


@celery_app.task
@_with_redis_lock("cleanup_stale_embeddings", lock_ttl=600)
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
                stale_docs = await vs.check_staleness(
                    org_id, staleness_days=30, db=supabase
                )
                total_stale += len(stale_docs)

                # Log stale documents for monitoring
                if stale_docs:
                    logger.info(
                        f"Org {org_id}: {len(stale_docs)} stale documents found"
                    )

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
                            await supabase.table("document_embeddings").delete().eq(
                                "id", chunk["id"]
                            ).execute()
                            total_expired += 1
                        except Exception as del_e:
                            if not (
                                hasattr(del_e, "code")
                                and str(getattr(del_e, "code", "")) == "204"
                            ):
                                logger.warning(
                                    f"Failed to delete expired embedding {chunk['id']}: {del_e}"
                                )
                            else:
                                total_expired += 1
                except Exception as e:
                    logger.debug(f"Expired embedding cleanup skipped for {org_id}: {e}")

            except Exception as e:
                logger.error(f"Knowledge base GC failed for org {org_id}: {e}")

        return f"GC complete: {total_stale} stale docs detected, {total_expired} expired embeddings cleaned"

    return _run_async(_run())


@celery_app.task
@_with_redis_lock("aggregate_ai_quality_metrics", lock_ttl=600)
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
@_with_redis_lock("monitor_tenants", lock_ttl=240)
def monitor_tenants():
    """
    租户信用监控 + 试用到期检查（原 main.py asyncio 循环）
    每5分钟运行一次
    """

    async def _run():
        from app.core.database import supabase
        from app.services.billing_service import billing_service
        from app.services.tenant_credit_service import tenant_credit_service

        if not supabase:
            return "skipped: no db"

        await tenant_credit_service.monitor_all_tenants(db=supabase)
        await billing_service.check_expired_trials(db=supabase)
        return "Tenant monitoring complete"

    return _run_async(_run())


@celery_app.task
@_with_redis_lock("check_approval_timeouts", lock_ttl=240)
def check_approval_timeouts():
    """
    审批超时升级检查（原 main.py asyncio 循环）
    每5分钟运行一次
    """

    async def _run():
        from app.services.approval_chain import approval_chain_service

        await approval_chain_service.check_timeout_escalation()
        return "Approval timeout check complete"

    return _run_async(_run())


@celery_app.task
@_with_redis_lock("sync_im_platforms", lock_ttl=600)
def sync_im_platforms():
    """
    IM平台通讯录+考勤同步（原 main.py asyncio 循环）
    每小时运行一次
    """

    async def _run():
        from app.core.database import supabase as sync_db
        from app.services.im_platform.attendance_sync_service import (
            attendance_sync_service,
        )
        from app.services.im_platform.contact_sync_service import contact_sync_service

        if not sync_db:
            return "skipped: no db"

        result = (
            await sync_db.table("im_platform_config")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        synced = 0
        for config in result.data or []:
            try:
                org_id = config.get("organization_id", "")
                platform = config.get("platform", "")
                if org_id and platform:
                    await contact_sync_service.sync_contacts(
                        org_id, platform, db=sync_db
                    )
                    await attendance_sync_service.sync_attendance(
                        org_id, platform, db=sync_db
                    )
                    synced += 1
            except Exception as e:
                logger.error(
                    f"IM sync error for org {config.get('organization_id')}: {e}"
                )

        return f"IM sync complete: {synced} orgs synced"

    return _run_async(_run())


@celery_app.task
@_with_redis_lock("check_contract_expiry", lock_ttl=600)
def check_contract_expiry():
    """
    3.5 合同到期预警
    查询30天内到期的合同，发送预警通知
    """

    async def _run():
        from app.core.database import supabase
        from app.services.notification_service import (
            NotificationPriority,
            send_notification,
        )

        if not supabase:
            return "skipped: no db"

        thirty_days_later = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")

        # P0 Security: 按组织遍历，防止跨租户数据泄露
        orgs_res = (
            await supabase.table("organizations").select("id").execute()
        )
        org_ids = [o["id"] for o in (orgs_res.data or [])]

        notified = 0
        for org_id in org_ids:
            try:
                org_client = supabase.get_org_filtered_client(org_id)
                result = (
                    await org_client.table("contracts")
                    .select("id, title, end_date, user_id, status")
                    .gte("end_date", today)
                    .lte("end_date", thirty_days_later)
                    .eq("status", "active")
                    .execute()
                )
            except Exception:
                logger.info(f"contracts table not available for org {org_id}")
                continue

            expiring = result.data or []
            for contract in expiring:
                try:
                    if contract.get("user_id"):
                        days_left = (
                            datetime.strptime(contract["end_date"], "%Y-%m-%d")
                            - datetime.now()
                        ).days
                        await send_notification(
                            title=f"合同到期预警: {contract.get('title', '未命名')}",
                            content=f"合同将在 {days_left} 天后到期 ({contract['end_date']})，请及时处理续签或结算。",
                            target_user_id=contract["user_id"],
                            priority=NotificationPriority.HIGH,
                        )
                        notified += 1
                except Exception as e:
                    logger.error(
                        f"Contract expiry notification failed for {contract.get('id', '?')}: {e}"
                    )

        return f"Notified {notified} expiring contracts across {len(org_ids)} orgs"

    return _run_async(_run())


# execute_user_scheduled_tasks: REMOVED — unified into ScheduledTaskRunner
# (FastAPI in-process async loop) to eliminate double-scheduling.
# See scheduled_task_runner.py for the single authoritative executor.


@celery_app.task
def decompose_vmd_task(task_id: str):
    """
    VMD Task Auto-Decomposition (#32)
    Takes a main task and uses LLM to decompose it into sub-tasks (WBS structure).

    Triggered asynchronously after task creation.
    """

    async def _run():
        from app.core.database import supabase
        from app.services.ai_service import AIService

        if not supabase:
            return "skipped: no db"

        # 1. Load the main task
        task_res = (
            await supabase.table("vmd_main_task")
            .select("*")
            .eq("id", task_id)
            .maybe_single()
            .execute()
        )
        if not task_res.data:
            logger.error(f"decompose_vmd_task: task {task_id} not found")
            return f"task {task_id} not found"

        task = task_res.data
        if task.get("status") not in ("pending", None):
            logger.info(
                f"decompose_vmd_task: task {task_id} status is {task.get('status')}, skipping"
            )
            return f"task {task_id} already processed"

        title = task.get("title", "")
        description = task.get("description", "")
        scene_code = task.get("scene_code", "")

        # 2. Use LLM to decompose the task description into sub-tasks
        decompose_prompt = (
            f"你是一个项目分解专家。请将以下任务分解为可执行的子任务列表。\n\n"
            f"任务标题: {title}\n"
            f"任务描述: {description}\n"
            f"场景编码: {scene_code}\n\n"
            f"请返回JSON格式的子任务列表，每个子任务包含:\n"
            f"- title: 子任务标题\n"
            f"- agent_role: 负责的Agent角色 (如: content_creator, data_analyst, market_researcher, reviewer)\n"
            f"- description: 子任务描述\n"
            f"- sort_order: 执行顺序 (从1开始)\n\n"
            f"只返回JSON数组，不要其他内容。示例:\n"
            f'[{{"title": "市场调研", "agent_role": "market_researcher", "description": "...", "sort_order": 1}}]'
        )

        try:
            import json

            llm_response = await AIService.call_llm(
                decompose_prompt,
                "你是一个严格按JSON格式输出的项目分解助手。只输出JSON数组，不添加任何其他文字。",
            )

            # Parse LLM response - try to extract JSON array
            response_text = llm_response.strip()
            # Handle markdown code blocks
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(
                    lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
                )
                response_text = response_text.strip()

            sub_tasks_data = json.loads(response_text)
            if not isinstance(sub_tasks_data, list):
                sub_tasks_data = [sub_tasks_data]

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(
                f"decompose_vmd_task: LLM response parse failed: {e}, creating default sub-task"
            )
            sub_tasks_data = [
                {
                    "title": f"执行: {title}",
                    "agent_role": "content_creator",
                    "description": description,
                    "sort_order": 1,
                }
            ]

        # 3. Create vmd_sub_task records (批量插入替代逐条 INSERT)
        tenant_id = task.get("tenant_id", "default")
        records = []
        for idx, st in enumerate(sub_tasks_data):
            records.append(
                {
                    "main_task_id": task_id,
                    "tenant_id": tenant_id,
                    "title": st.get("title", "未命名子任务"),
                    "agent_role": st.get("agent_role", "content_creator"),
                    "description": st.get("description", ""),
                    "sort_order": st.get("sort_order", idx + 1),
                    "status": "pending",
                }
            )
        try:
            await supabase.table("vmd_sub_task").insert(records).execute()
            created_count = len(records)
        except Exception as e:
            logger.error(
                f"decompose_vmd_task: batch insert failed: {e}, falling back to individual inserts"
            )
            created_count = 0
            for sub_record in records:
                try:
                    await supabase.table("vmd_sub_task").insert(sub_record).execute()
                    created_count += 1
                except Exception as e2:
                    logger.error(f"decompose_vmd_task: failed to create sub-task: {e2}")

        # 4. Update main task status and WBS structure
        wbs_structure = {
            "version": "1.0",
            "decomposed_at": datetime.now(UTC).isoformat(),
            "total_sub_tasks": created_count,
            "sub_tasks": [
                {"title": st.get("title", ""), "agent_role": st.get("agent_role", "")}
                for st in sub_tasks_data[:created_count]
            ],
        }

        await (
            supabase.table("vmd_main_task")
            .update(
                {
                    "status": "executing",
                    "wbs_structure": wbs_structure,
                }
            )
            .eq("id", task_id)
            .execute()
        )

        return f"Decomposed task {task_id} into {created_count} sub-tasks"

    return _run_async(_run())


# ---------------------------------------------------------------------------
# P0-2: Smart Recommendation Push
# ---------------------------------------------------------------------------


@celery_app.task
@_with_redis_lock("push_smart_recommendations", lock_ttl=600)
def push_smart_recommendations():
    """Push smart recommendations to online users via WebSocket every 2 hours."""

    async def _run():
        from app.core.database import supabase

        if not supabase:
            return "skipped: no db"

        from app.services.smart_recommendation_service import (
            smart_recommendation_service,
        )
        from app.services.websocket_manager import ws_manager

        connected_users = ws_manager.get_connected_user_ids()
        if not connected_users:
            return "skipped: no online users"

        pushed = 0
        for user_id in connected_users:
            try:
                user_result = (
                    await supabase.table("users")
                    .select("organization_id, role")
                    .eq("id", user_id)
                    .maybe_single()
                    .execute()
                )

                if not user_result.data:
                    continue

                context = {
                    "org_id": user_result.data.get("organization_id"),
                    "role": user_result.data.get("role", "employee"),
                }

                recs = await smart_recommendation_service.get_recommendations(
                    user_id=user_id,
                    context=context,
                    limit=3,
                    db=supabase,
                )

                # Only push HIGH+ priority recommendations (priority value >= 3)
                important_recs = [r for r in recs if r.priority.value >= 3]
                if not important_recs:
                    continue

                await ws_manager.send_to_user(
                    user_id,
                    {
                        "type": "recommendation",
                        "data": [
                            {
                                "id": r.id,
                                "type": r.type.value,
                                "title": r.title,
                                "description": r.description,
                                "priority": r.priority.name.lower(),
                                "action_url": r.action_url,
                                "action_label": r.action_label,
                            }
                            for r in important_recs
                        ],
                    },
                )
                pushed += 1
            except Exception as e:
                logger.error(f"Recommendation push failed for {user_id}: {e}")

        return f"pushed to {pushed}/{len(connected_users)} users"

    return _run_async(_run())


# ---------------------------------------------------------------------------


@celery_app.task
@_with_redis_lock("purge_superseded_memories", lock_ttl=600)
def purge_superseded_memories():
    """
    P2-2: 清理已被取代的旧版本记忆。
    每天凌晨3:45运行，删除 superseded_by IS NOT NULL 且超过 30 天的旧记录。
    这些记录已被新版本取代，保留它们只会膨胀表。
    """

    async def _run():
        from app.core.database import supabase

        if not supabase:
            return "skipped: no db"

        cutoff = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        try:
            result = (
                await supabase.table("conversation_memories")
                .delete()
                .not_.is_("superseded_by", "null")
                .lt("updated_at", cutoff)
                .execute()
            )
            deleted = len(result.data) if result.data else 0
            logger.info(
                f"[MemoryPurge] Deleted {deleted} superseded memories older than 30 days"
            )
            return f"Purged {deleted} superseded old-version memories"
        except Exception as e:
            # superseded_by column may not exist yet
            logger.error(f"[MemoryPurge] Failed (column may not exist): {e}")
            return f"skipped: {e}"

    return _run_async(_run())


@celery_app.task
@_with_redis_lock("cleanup_stale_memories", lock_ttl=600)
def cleanup_stale_memories():
    """
    P0-2: 记忆衰减清理
    每天凌晨4点运行，清理30天以上未访问且衰减分数低于阈值的记忆。
    保护 explicit_memory 和 policy 类型不被自动删除。
    """

    async def _run():
        from app.core.database import supabase
        from app.services.conversation_memory_service import conversation_memory_service

        if not supabase:
            return "skipped: no db"

        result = await conversation_memory_service.cleanup_decayed_memories(
            min_age_days=30,
            score_threshold=0.1,
            batch_size=200,
            db=supabase,
        )
        return f"Memory decay cleanup: scanned={result['scanned']}, deleted={result['deleted']}"

    return _run_async(_run())


@celery_app.task
@_with_redis_lock("consolidate_memories", lock_ttl=600)
def consolidate_memories():
    """
    记忆整合 (Sleep Cycle): 每天凌晨3:30运行。
    对每个有未整合记忆的活跃用户，用 LLM 发现跨记忆的模式、
    生成洞察、建立记忆间关联。在 decay cleanup (4:00) 之前运行。
    """

    async def _run():
        from app.core.database import supabase
        from app.services.conversation_memory_service import conversation_memory_service

        if not supabase:
            return "skipped: no db"

        # Get distinct users with unconsolidated memories
        try:
            result = (
                await supabase.table("conversation_memories")
                .select("user_id")
                .eq("is_consolidated", False)
                .limit(500)
                .execute()
            )
        except Exception as e:
            logger.warning(f"Consolidation user query failed: {e}")
            return f"error: {e}"

        user_ids = list({r["user_id"] for r in (result.data or [])})
        total_insights = 0
        processed_users = 0

        for uid in user_ids[:50]:  # Cap at 50 users per batch
            try:
                r = await conversation_memory_service.consolidate_user_memories(
                    user_id=uid, batch_size=30, db=supabase
                )
                total_insights += r.get("insights_created", 0)
                if r.get("processed", 0) > 0:
                    processed_users += 1
            except Exception as e:
                logger.warning(f"Consolidation failed for user {uid}: {e}")

        return (
            f"Consolidated {total_insights} insights "
            f"for {processed_users}/{len(user_ids[:50])} users"
        )

    return _run_async(_run())


@celery_app.task
@_with_redis_lock("reevaluate_memory_importance", lock_ttl=600)
def reevaluate_memory_importance():
    """
    记忆重要性重评估: 每周日4:30运行。
    根据访问模式动态调整记忆的 importance 评分。
    纯数学计算，零 LLM 成本。
    """

    async def _run():
        from app.core.database import supabase
        from app.services.conversation_memory_service import conversation_memory_service

        if not supabase:
            return "skipped: no db"

        result = await conversation_memory_service.reevaluate_importance(
            batch_size=200, db=supabase
        )
        return f"Importance reeval: boosted={result['boosted']}, decayed={result['decayed']}"

    return _run_async(_run())


@celery_app.task
@_with_redis_lock("decay_kg_strength", lock_ttl=600)
def decay_kg_strength():
    """
    知识图谱 strength 时间衰减: 每周三凌晨4:15运行。
    对长期未被提及的三元组降低 strength，低于阈值的归档（soft-expire）。
    保护高 occurrences 的核心三元组不被误删。
    纯数学计算，零 LLM 成本。
    """

    async def _run():
        from app.core.database import supabase
        from app.services.conversation_memory.cleanup import decay_kg_strength as _decay

        if not supabase:
            return "skipped: no db"

        result = await _decay(
            decay_rate=0.95,
            archive_threshold=0.15,
            protect_occurrences=5,
            batch_size=500,
            db=supabase,
        )
        return (
            f"KG decay: scanned={result['scanned']}, "
            f"decayed={result['decayed']}, archived={result['archived']}"
        )

    return _run_async(_run())


# ---------------------------------------------------------------------------
# P1-2: Action Outcome Tracking — Record AI actions for effectiveness measurement
# ---------------------------------------------------------------------------


@celery_app.task
@_with_redis_lock("measure_action_outcomes", lock_ttl=600)
def measure_action_outcomes():
    """
    P1-2: 操作效果追踪
    每天检查过去24-72小时的AI操作是否产生了预期效果。
    例如：AI发送跟进提醒后，客户是否在48小时内被更新。
    """

    async def _run():
        from app.core.database import supabase

        if not supabase:
            return "skipped: no db"

        now = datetime.now(UTC)
        check_window_start = (now - timedelta(hours=72)).isoformat()
        check_window_end = (now - timedelta(hours=24)).isoformat()

        try:
            result = (
                await supabase.table("ai_action_outcomes")
                .select("id, action_type, target_id, action_at, expected_outcome")
                .is_("success", "null")
                .gte("action_at", check_window_start)
                .lte("action_at", check_window_end)
                .limit(50)
                .execute()
            )
        except Exception as e:
            logger.error(f"ai_action_outcomes query failed: {e}")
            return "skipped: table not available"

        actions = result.data or []
        if not actions:
            return "no actions to measure"

        measured = 0
        for action in actions:
            try:
                success = None
                actual_outcome = ""

                if action["action_type"] == "followup_reminder":
                    # Check if the customer was updated since the reminder
                    cust_res = (
                        await supabase.table("customers")
                        .select("updated_at")
                        .eq("id", action["target_id"])
                        .maybe_single()
                        .execute()
                    )
                    if cust_res.data:
                        updated_at = cust_res.data.get("updated_at", "")
                        if updated_at > action["action_at"]:
                            success = True
                            actual_outcome = "客户记录在提醒后已更新"
                        else:
                            success = False
                            actual_outcome = "客户记录在提醒后仍未更新"

                elif action["action_type"] == "approval_reminder":
                    # Check if the approval was processed
                    apr_res = (
                        await supabase.table("approval_requests")
                        .select("status")
                        .eq("id", action["target_id"])
                        .maybe_single()
                        .execute()
                    )
                    if apr_res.data:
                        status = apr_res.data.get("status", "pending")
                        if status != "pending":
                            success = True
                            actual_outcome = f"审批已处理，状态: {status}"
                        else:
                            success = False
                            actual_outcome = "审批仍在待处理中"

                elif action["action_type"] == "contract_expiry_reminder":
                    # Check if contract was renewed or handled
                    cont_res = (
                        await supabase.table("contracts")
                        .select("status, updated_at")
                        .eq("id", action["target_id"])
                        .maybe_single()
                        .execute()
                    )
                    if cont_res.data:
                        if cont_res.data.get("updated_at", "") > action["action_at"]:
                            success = True
                            actual_outcome = (
                                f"合同已处理，状态: {cont_res.data.get('status')}"
                            )
                        else:
                            success = False
                            actual_outcome = "合同到期提醒后仍未处理"

                if success is not None:
                    await (
                        supabase.table("ai_action_outcomes")
                        .update(
                            {
                                "success": success,
                                "actual_outcome": actual_outcome,
                                "measured_at": now.isoformat(),
                            }
                        )
                        .eq("id", action["id"])
                        .execute()
                    )
                    measured += 1

            except Exception as e:
                logger.error(
                    f"Action outcome measurement failed for {action['id']}: {e}"
                )

        return f"Measured {measured}/{len(actions)} action outcomes"

    return _run_async(_run())


# ---------------------------------------------------------------------------
# P1-4: Lead Scoring — Recalculate lead scores periodically
# ---------------------------------------------------------------------------


@celery_app.task
@_with_redis_lock("score_all_leads", lock_ttl=600)
def score_all_leads_task():
    """每小时重算所有组织的线索评分。"""

    async def _run():
        from app.core.database import supabase
        from app.services.lead_scoring_service import score_all_leads

        if not supabase:
            return "skipped: no db"

        orgs_res = await supabase.table("organizations").select("id").execute()
        org_ids = [o["id"] for o in (orgs_res.data or [])]

        total_scored = 0
        for org_id in org_ids:
            try:
                result = await score_all_leads(supabase, org_id)
                total_scored += result.get("scored", 0)
            except Exception as e:
                logger.error(f"Lead scoring failed for org {org_id}: {e}")

        return f"Scored {total_scored} leads across {len(org_ids)} orgs"

    return _run_async(_run())


# ── AI ROI Daily Aggregation ─────────────────────────────────────────────────


# Tool name → ROI category mapping
_TOOL_CATEGORY_MAP = {
    "approve_request": "approval", "reject_request": "approval",
    "get_pending_approvals": "approval", "smart_approve": "approval",
    "submit_approval_on_behalf": "approval", "list_approval_flows": "approval",
    "create_approval_flow": "approval", "approve_expense": "approval",
    "get_employee_approval_history": "approval",
    "get_customers": "crm", "get_customer_detail": "crm",
    "create_customer": "crm", "update_customer": "crm",
    "add_follow_up": "crm", "get_follow_ups": "crm",
    "update_customer_stage": "crm", "get_sales_pipeline": "crm",
    "get_contracts": "crm", "create_contract": "crm",
    "get_expiring_contracts": "crm", "analyze_contract": "crm",
    "generate_customer_profile": "crm",
    "get_performance_report": "report", "smart_report": "report",
    "get_company_stats": "report", "get_business_dashboard": "report",
    "get_team_insight": "report", "anomaly_detection": "report",
    "analyze_data_attribution": "report", "strategy_simulation": "report",
    "generate_weekly_report": "report",
    "clock_in_out": "attendance", "get_attendance_record": "attendance",
    "attendance_statistics": "attendance", "query_attendance": "attendance",
    "query_team_attendance": "attendance", "create_shift_schedule": "attendance",
    "list_shift_schedules": "attendance",
    "create_expense_claim": "finance", "query_expense_status": "finance",
    "query_budget": "finance", "query_salary": "finance",
    "recognize_invoice": "finance", "submit_expense": "finance",
    "list_expenses": "finance", "check_budget": "finance",
    "create_leave_request": "leave", "query_leave_status": "leave",
    "request_leave": "leave",
    "create_scheduled_task": "schedule", "list_scheduled_tasks": "schedule",
    "delete_scheduled_task": "schedule", "get_daily_briefing": "schedule",
    "book_meeting": "schedule", "create_task": "schedule",
    "update_task": "schedule", "list_tasks": "schedule",
    "query_knowledge_base": "knowledge", "batch_analyze_documents": "knowledge",
    "load_knowledge": "knowledge",
}


@celery_app.task
@_with_redis_lock("aggregate_ai_roi_daily", lock_ttl=600)
def aggregate_ai_roi_daily():
    """每日聚合 AI ROI 指标 → ai_roi_daily 表。"""

    async def _run():
        from datetime import date, timedelta

        from app.core.database import supabase

        if not supabase:
            return "skipped: no db"

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        logger.info("[ROI] Aggregating AI ROI for %s", yesterday)

        # ── 1. Get all tenant_ids from llm_call_log ──
        try:
            tenant_res = (
                await supabase.table("llm_call_log")
                .select("org_id")
                .gte("created_at", yesterday + "T00:00:00")
                .lt("created_at", yesterday + "T23:59:59.999")
                .execute()
            )
            org_ids = list({
                r["org_id"] for r in (tenant_res.data or [])
                if r.get("org_id")
            })
        except Exception:
            # Fallback: try tenant_usage_records
            try:
                tenant_res = (
                    await supabase.table("tenant_usage_records")
                    .select("tenant_id")
                    .gte("recorded_at", yesterday)
                    .execute()
                )
                org_ids = list({
                    r["tenant_id"] for r in (tenant_res.data or [])
                    if r.get("tenant_id")
                })
            except Exception:
                org_ids = ["default"]

        if not org_ids:
            return "no tenants with activity"

        # ── 2. Load baselines ──
        baselines = {}
        try:
            bl_res = (
                await supabase.table("ai_roi_baselines")
                .select("action_category, baseline_minutes, hourly_labor_cost")
                .execute()
            )
            for row in (bl_res.data or []):
                baselines[row["action_category"]] = {
                    "minutes": float(row["baseline_minutes"]),
                    "hourly_cost": float(row["hourly_labor_cost"]),
                }
        except Exception as e:
            logger.warning("[ROI] Failed to load baselines: %s", e)

        total_upserted = 0

        for org_id in org_ids:
            try:
                metrics = await _aggregate_one_tenant(
                    supabase, org_id, yesterday, baselines
                )
                if metrics:
                    await supabase.table("ai_roi_daily").upsert(
                        metrics, on_conflict="tenant_id,metric_date"
                    ).execute()
                    total_upserted += 1
            except Exception as e:
                logger.error("[ROI] Failed for tenant %s: %s", org_id, e)

        return f"Aggregated ROI for {total_upserted}/{len(org_ids)} tenants on {yesterday}"

    return _run_async(_run())


async def _aggregate_one_tenant(
    supabase, org_id: str, date_str: str, baselines: dict
) -> dict | None:
    """Aggregate ROI metrics for one tenant on one date."""
    metrics = {
        "tenant_id": org_id,
        "metric_date": date_str,
        "ai_cost_usd": 0,
        "total_tokens": 0,
        "total_llm_calls": 0,
        "tool_calls_total": 0,
        "tool_calls_success": 0,
        "cat_approval": 0, "cat_crm": 0, "cat_report": 0,
        "cat_attendance": 0, "cat_finance": 0, "cat_leave": 0,
        "cat_schedule": 0, "cat_knowledge": 0, "cat_other": 0,
        "estimated_minutes_saved": 0,
        "estimated_labor_cost_saved": 0,
        "roi_percent": 0,
        "avg_response_time_ms": 0,
        "positive_feedback": 0,
        "negative_feedback": 0,
    }

    day_start = date_str + "T00:00:00"
    day_end = date_str + "T23:59:59.999"

    # ── LLM cost from llm_call_log ──
    try:
        llm_res = (
            await supabase.table("llm_call_log")
            .select("cost_usd, total_tokens, duration_ms")
            .eq("org_id", org_id)
            .gte("created_at", day_start)
            .lt("created_at", day_end)
            .execute()
        )
        rows = llm_res.data or []
        metrics["total_llm_calls"] = len(rows)
        total_cost = 0.0
        total_tokens = 0
        total_ms = 0
        for r in rows:
            total_cost += float(r.get("cost_usd") or 0)
            total_tokens += int(r.get("total_tokens") or 0)
            total_ms += int(r.get("duration_ms") or 0)
        metrics["ai_cost_usd"] = round(total_cost, 4)
        metrics["total_tokens"] = total_tokens
        if rows:
            metrics["avg_response_time_ms"] = int(total_ms / len(rows))
    except Exception as e:
        logger.debug("[ROI] llm_call_log query failed for %s: %s", org_id, e)

    # ── Tool execution from tool_execution_audit ──
    try:
        tool_res = (
            await supabase.table("tool_execution_audit")
            .select("tool_name, success")
            .eq("org_id", org_id)
            .gte("created_at", day_start)
            .lt("created_at", day_end)
            .execute()
        )
        tool_rows = tool_res.data or []
        metrics["tool_calls_total"] = len(tool_rows)
        success_count = 0
        for r in tool_rows:
            if r.get("success"):
                success_count += 1
            cat = _TOOL_CATEGORY_MAP.get(r.get("tool_name", ""), "other")
            col = f"cat_{cat}"
            if col in metrics:
                metrics[col] += 1
            else:
                metrics["cat_other"] += 1
        metrics["tool_calls_success"] = success_count
    except Exception as e:
        logger.debug("[ROI] tool_execution_audit query failed for %s: %s", org_id, e)

    # ── Feedback from ai_feedback ──
    try:
        fb_res = (
            await supabase.table("ai_feedback")
            .select("rating")
            .eq("org_id", org_id)
            .gte("created_at", day_start)
            .lt("created_at", day_end)
            .execute()
        )
        for r in (fb_res.data or []):
            rating = r.get("rating", 0)
            if rating and rating >= 4:
                metrics["positive_feedback"] += 1
            elif rating and rating <= 2:
                metrics["negative_feedback"] += 1
    except Exception as e:
        logger.debug("[ROI] ai_feedback query failed for %s: %s", org_id, e)

    # ── Calculate savings based on baselines ──
    total_minutes_saved = 0.0
    total_labor_saved = 0.0
    cat_fields = [
        "cat_approval", "cat_crm", "cat_report", "cat_attendance",
        "cat_finance", "cat_leave", "cat_schedule", "cat_knowledge", "cat_other",
    ]
    for col in cat_fields:
        cat_name = col.replace("cat_", "")
        count = metrics[col]
        if count > 0:
            bl = baselines.get(cat_name, {"minutes": 8, "hourly_cost": 45})
            minutes = count * bl["minutes"]
            cost = minutes / 60 * bl["hourly_cost"]
            total_minutes_saved += minutes
            total_labor_saved += cost

    metrics["estimated_minutes_saved"] = round(total_minutes_saved, 1)
    metrics["estimated_labor_cost_saved"] = round(total_labor_saved, 2)

    ai_cost = float(metrics["ai_cost_usd"])
    if ai_cost > 0:
        metrics["roi_percent"] = round(
            (total_labor_saved - ai_cost) / ai_cost * 100, 2
        )
    elif total_labor_saved > 0:
        metrics["roi_percent"] = 9999.0  # effectively infinite ROI

    return metrics
