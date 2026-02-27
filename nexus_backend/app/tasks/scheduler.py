import asyncio
import logging
from datetime import UTC, datetime, timedelta

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
def sync_im_platforms():
    """
    IM平台通讯录+考勤同步（原 main.py asyncio 循环）
    每小时运行一次
    """

    async def _run():
        from app.core.database import supabase as sync_db
        from app.services.im_platform.attendance_sync_service import attendance_sync_service
        from app.services.im_platform.contact_sync_service import contact_sync_service

        if not sync_db:
            return "skipped: no db"

        result = await sync_db.table("im_platform_config").select("*").eq("is_active", True).execute()
        synced = 0
        for config in result.data or []:
            try:
                org_id = config.get("organization_id", "")
                platform = config.get("platform", "")
                if org_id and platform:
                    await contact_sync_service.sync_contacts(org_id, platform, db=sync_db)
                    await attendance_sync_service.sync_attendance(org_id, platform, db=sync_db)
                    synced += 1
            except Exception as e:
                logger.error(f"IM sync error for org {config.get('organization_id')}: {e}")

        return f"IM sync complete: {synced} orgs synced"

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


@celery_app.task
def execute_user_scheduled_tasks():
    """
    用户自定义定时任务执行器
    每分钟检查是否有到期的用户定时任务，执行并推送结果通知
    """

    async def _run():
        from app.agent.proactive_runner import run_proactive_agent
        from app.core.database import supabase
        from app.services.notification_service import send_notification

        if not supabase:
            return "skipped: no db"

        now = datetime.now(UTC)
        result = (
            await supabase.table("user_scheduled_tasks")
            .select("*")
            .eq("is_active", True)
            .lte("next_execution_at", now.isoformat())
            .order("next_execution_at")
            .limit(20)
            .execute()
        )

        tasks = result.data or []
        if not tasks:
            return "No user tasks due"

        executed = 0
        for task in tasks:
            try:
                # Run AI agent with the user's prompt
                agent_result = await run_proactive_agent(
                    prompt=task["prompt"],
                    user_id=task["user_id"],
                    org_id=task.get("organization_id"),
                    agent_name=f"scheduled_{task['id'][:8]}",
                    timeout=60.0,
                )

                response = agent_result.get("response", "任务执行完成，但未生成结果。")

                # Send notification to user
                if task.get("notify_method") == "notification":
                    await send_notification(
                        title=f"定时任务: {task['name']}",
                        content=response[:500],
                        target_user_id=task["user_id"],
                    )

                # Compute next execution time
                from app.tools.scheduled_task_tools import _compute_next_execution

                next_exec = None
                if task["schedule_type"] != "once":
                    next_exec = _compute_next_execution(
                        task["schedule_type"],
                        task.get("hour"),
                        task.get("minute", 0),
                        task.get("day_of_week"),
                        task.get("interval_minutes"),
                        None,
                    )

                # Update task record
                update_data = {
                    "last_executed_at": now.isoformat(),
                    "execution_count": (task.get("execution_count", 0) or 0) + 1,
                    "last_result": response[:1000],
                }

                if task["schedule_type"] == "once":
                    update_data["is_active"] = False
                elif next_exec:
                    update_data["next_execution_at"] = next_exec

                await (
                    supabase.table("user_scheduled_tasks")
                    .update(update_data)
                    .eq("id", task["id"])
                    .execute()
                )

                executed += 1
                logger.info(f"Executed user scheduled task: {task['name']} for user {task['user_id']}")

            except Exception as e:
                logger.error(f"User scheduled task failed {task['id']}: {e}")
                # Record failure but keep task active
                try:
                    await (
                        supabase.table("user_scheduled_tasks")
                        .update({"last_result": f"执行失败: {str(e)[:200]}"})
                        .eq("id", task["id"])
                        .execute()
                    )
                except Exception:
                    pass

        return f"Executed {executed}/{len(tasks)} user scheduled tasks"

    return _run_async(_run())


# ---------------------------------------------------------------------------
# P0-2: Memory Decay Cleanup
# ---------------------------------------------------------------------------

@celery_app.task
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


# ---------------------------------------------------------------------------
# P1-2: Action Outcome Tracking — Record AI actions for effectiveness measurement
# ---------------------------------------------------------------------------

@celery_app.task
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
            logger.debug(f"ai_action_outcomes query failed: {e}")
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
                            actual_outcome = f"合同已处理，状态: {cont_res.data.get('status')}"
                        else:
                            success = False
                            actual_outcome = "合同到期提醒后仍未处理"

                if success is not None:
                    await (
                        supabase.table("ai_action_outcomes")
                        .update({
                            "success": success,
                            "actual_outcome": actual_outcome,
                            "measured_at": now.isoformat(),
                        })
                        .eq("id", action["id"])
                        .execute()
                    )
                    measured += 1

            except Exception as e:
                logger.error(f"Action outcome measurement failed for {action['id']}: {e}")

        return f"Measured {measured}/{len(actions)} action outcomes"

    return _run_async(_run())
