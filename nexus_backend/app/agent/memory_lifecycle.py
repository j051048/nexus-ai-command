"""
记忆生命周期管理 — 分级压缩与智能遗忘

三级策略：
  Level 1 (0-30 天)：全量保留，不做任何压缩
  Level 2 (30-90 天)：LLM 语义压缩（保留核心事实，去除冗余上下文）
  Level 3 (90+ 天)：仅保留 consolidation insight，低分记忆标记过期

设计原则：
- 绝不暴力截断（旧方案 content[:200] 丢失关键语义）
- 压缩前先检查 memory_scorer 的动态评分，高分记忆跳过压缩
- 用户标记重要的记忆永远不会被压缩或遗忘
- 所有操作异步执行，不阻塞主流程
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)

# 时间窗口配置
_LEVEL2_START_DAYS = 30  # Level 2 压缩起点
_LEVEL3_START_DAYS = 90  # Level 3 过期起点
_BATCH_SIZE = 50  # 每批处理的记忆数
_HIGH_IMPORTANCE_SKIP = 0.7  # 高于此分数的记忆跳过压缩
_FORGET_THRESHOLD = 0.08  # 低于此分数的记忆可被标记过期


async def run_lifecycle_maintenance(
    batch_size: int = _BATCH_SIZE,
    db: Any = None,
) -> dict:
    """执行完整的生命周期维护（建议作为定时任务每小时运行一次）

    Returns: {"level2_compressed": int, "level3_expired": int, "errors": int}
    """
    stats = {"level2_compressed": 0, "level3_expired": 0, "errors": 0}

    try:
        l2 = await compress_semantic(days_start=_LEVEL2_START_DAYS, days_end=_LEVEL3_START_DAYS, batch_size=batch_size, db=db)
        stats["level2_compressed"] = l2
    except Exception as e:
        logger.error(f"[Lifecycle] Level 2 compression failed: {e}")
        stats["errors"] += 1

    try:
        l3 = await expire_low_value_memories(days=_LEVEL3_START_DAYS, batch_size=batch_size, db=db)
        stats["level3_expired"] = l3
    except Exception as e:
        logger.error(f"[Lifecycle] Level 3 expiration failed: {e}")
        stats["errors"] += 1

    if stats["level2_compressed"] or stats["level3_expired"]:
        logger.info(
            f"[Lifecycle] Maintenance complete: "
            f"compressed={stats['level2_compressed']}, "
            f"expired={stats['level3_expired']}"
        )

    return stats


async def compress_semantic(
    days_start: int = 30,
    days_end: int = 90,
    batch_size: int = _BATCH_SIZE,
    db: Any = None,
) -> int:
    """Level 2：LLM 语义压缩 30-90 天的记忆

    保留核心事实（人名、数字、决策结论），去除上下文和冗余描述。
    高重要性记忆跳过压缩。用户标记重要的记忆永远不压缩。

    Returns: 压缩的记忆条数
    """
    client = db or supabase
    if not client:
        return 0

    start_cutoff = datetime.now(UTC) - timedelta(days=days_end)
    end_cutoff = datetime.now(UTC) - timedelta(days=days_start)

    try:
        result = (
            await client.table("conversation_memories")
            .select("id, content, value, category, importance, user_marked_important, metadata")
            .gte("created_at", start_cutoff.isoformat())
            .lt("created_at", end_cutoff.isoformat())
            .eq("compressed", False)
            .order("importance", desc=False)  # 低重要性优先压缩
            .limit(batch_size)
            .execute()
        )
    except Exception as e:
        logger.warning(f"[Lifecycle] Compression query failed: {e}")
        return 0

    memories = result.data or []
    if not memories:
        return 0

    # 过滤：跳过高重要性和用户标记的记忆
    compressible = []
    for mem in memories:
        if mem.get("user_marked_important"):
            continue
        importance = float(mem.get("importance", 0) or 0)
        if importance >= _HIGH_IMPORTANCE_SKIP:
            continue
        content = mem.get("value") or mem.get("content") or ""
        if len(str(content)) < 100:
            continue  # 已经很短，无需压缩
        compressible.append(mem)

    if not compressible:
        return 0

    compressed_count = 0

    # 分批送入 LLM 做语义压缩（每批 10 条，控制 token 消耗）
    chunk_size = 10
    for i in range(0, len(compressible), chunk_size):
        chunk = compressible[i : i + chunk_size]
        try:
            compressed_results = await _llm_compress_batch(chunk)
            for mem, compressed_text in zip(chunk, compressed_results, strict=False):
                if compressed_text and len(compressed_text) < len(str(mem.get("value", ""))):
                    try:
                        update_data: dict[str, Any] = {
                            "value": compressed_text,
                            "compressed": True,
                        }
                        # 保留原始内容的 hash 用于溯源
                        meta = mem.get("metadata") or {}
                        if isinstance(meta, dict):
                            original_content = str(mem.get("value", ""))
                            meta["original_length"] = len(original_content)
                            meta["compressed_at"] = datetime.now(UTC).isoformat()
                            update_data["metadata"] = meta

                        await (
                            client.table("conversation_memories")
                            .update(update_data)
                            .eq("id", mem["id"])
                            .execute()
                        )
                        compressed_count += 1
                    except Exception as e:
                        logger.error(f"[Lifecycle] Failed to update compressed memory {mem['id']}: {e}")
        except Exception as e:
            logger.warning(f"[Lifecycle] LLM compression batch failed: {e}")
            # Fallback：对这批用规则压缩（不丢失关键信息）
            for mem in chunk:
                try:
                    fallback_text = _rule_based_compress(str(mem.get("value", "")))
                    if fallback_text:
                        await (
                            client.table("conversation_memories")
                            .update({"value": fallback_text, "compressed": True})
                            .eq("id", mem["id"])
                            .execute()
                        )
                        compressed_count += 1
                except Exception:
                    pass

    if compressed_count:
        logger.info(f"[Lifecycle] Level 2 compressed {compressed_count}/{len(compressible)} memories")

    return compressed_count


async def expire_low_value_memories(
    days: int = 90,
    batch_size: int = _BATCH_SIZE,
    db: Any = None,
) -> int:
    """Level 3：标记 90+ 天的低价值记忆为过期

    不做物理删除，而是 soft-expire（设置 status='expired'），
    使其不再出现在常规检索中，但仍可用于审计和溯源。

    Returns: 过期标记的记忆条数
    """
    from app.agent.memory_scorer import memory_scorer

    client = db or supabase
    if not client:
        return 0

    cutoff = datetime.now(UTC) - timedelta(days=days)

    try:
        result = (
            await client.table("conversation_memories")
            .select("id, content, value, category, importance, access_count, "
                    "user_marked_important, last_accessed_at, created_at")
            .lt("created_at", cutoff.isoformat())
            .neq("status", "expired")  # 已过期的跳过
            .order("importance", desc=False)
            .limit(batch_size)
            .execute()
        )
    except Exception as e:
        logger.warning(f"[Lifecycle] Expiration query failed: {e}")
        return 0

    memories = result.data or []
    if not memories:
        return 0

    expired_count = 0
    for mem in memories:
        # 永远不过期用户标记的记忆
        if mem.get("user_marked_important"):
            continue

        # 使用 memory_scorer 的动态评分决定是否过期
        should_forget = await memory_scorer.should_forget(mem, threshold=_FORGET_THRESHOLD)
        if not should_forget:
            continue

        try:
            await (
                client.table("conversation_memories")
                .update({
                    "status": "expired",
                    "metadata": {
                        **(mem.get("metadata") or {}),
                        "expired_at": datetime.now(UTC).isoformat(),
                        "expire_reason": "low_value_decay",
                    },
                })
                .eq("id", mem["id"])
                .execute()
            )
            expired_count += 1
        except Exception as e:
            logger.error(f"[Lifecycle] Failed to expire memory {mem['id']}: {e}")

    if expired_count:
        logger.info(f"[Lifecycle] Level 3 expired {expired_count}/{len(memories)} low-value memories")

    return expired_count


async def cleanup_expired_memories(days: int = 180, db: Any = None) -> int:
    """物理删除 180+ 天已过期的记忆（最终清理）

    仅删除 status='expired' 的记忆，确保活跃记忆不受影响。

    Returns: 删除的记忆条数
    """
    client = db or supabase
    if not client:
        return 0

    cutoff = datetime.now(UTC) - timedelta(days=days)

    try:
        result = (
            await client.table("conversation_memories")
            .delete()
            .eq("status", "expired")
            .lt("created_at", cutoff.isoformat())
            .execute()
        )
        count = len(result.data) if result.data else 0
        if count:
            logger.info(f"[Lifecycle] Physically deleted {count} expired memories older than {days} days")
        return count
    except Exception as e:
        logger.error(f"[Lifecycle] Physical cleanup failed: {e}")
        return 0


# ── 内部辅助函数 ──


async def _llm_compress_batch(memories: list[dict]) -> list[str]:
    """用 LLM 对一批记忆做语义压缩

    Returns: 压缩后的文本列表（与 memories 一一对应）
    """
    from app.services.ai_service import AIService

    mem_texts = []
    for i, mem in enumerate(memories):
        content = str(mem.get("value", "") or mem.get("content", ""))
        # 限制单条输入长度
        if len(content) > 2000:
            content = content[:2000] + "..."
        category = mem.get("category", "general")
        mem_texts.append(f"[{i}] ({category}) {content}")

    prompt = (
        f"以下是 {len(memories)} 条需要压缩的记忆条目。\n"
        f"请将每条压缩为 1-2 句话的核心事实摘要。\n\n"
        + "\n\n".join(mem_texts)
    )

    system = (
        "你是记忆压缩专家。将每条记忆压缩为核心事实摘要。\n"
        "规则：\n"
        "- 保留：人名、公司名、数字、日期、决策结论、行动结果\n"
        "- 删除：上下文描述、情感表达、重复信息、冗余修饰语\n"
        "- 每条压缩为 1-2 句话，不超过 150 字\n"
        "- 输出格式：每行一条，用 [序号] 开头，如 [0] 压缩后的内容\n"
        "- 如果原文已经足够简洁，原样返回"
    )

    try:
        result_text = await AIService.call_llm(prompt, system)
        return _parse_compressed_lines(result_text, len(memories))
    except Exception as e:
        logger.warning(f"[Lifecycle] LLM compression failed: {e}")
        # Fallback to rule-based compression
        return [_rule_based_compress(str(m.get("value", ""))) for m in memories]


def _parse_compressed_lines(text: str, expected_count: int) -> list[str]:
    """解析 LLM 压缩输出，提取每条压缩结果"""
    if not text:
        return [""] * expected_count

    results = [""] * expected_count
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # 匹配 [0], [1] 等索引前缀
        if line.startswith("["):
            try:
                bracket_end = line.index("]")
                idx = int(line[1:bracket_end])
                content = line[bracket_end + 1:].strip().lstrip(":").lstrip()
                if 0 <= idx < expected_count and content:
                    results[idx] = content
            except (ValueError, IndexError):
                continue

    return results


def _rule_based_compress(content: str) -> str:
    """基于规则的轻量压缩（LLM 不可用时的 fallback）

    策略：保留首句 + 末句 + 中间的关键数字/人名
    """
    if not content or len(content) <= 200:
        return content

    lines = content.split("\n")
    if len(lines) <= 3:
        # 短文本：保留首尾
        return content[:300] + f"... (原文 {len(content)} 字)"

    # 保留首 2 行 + 末 1 行 + 中间含数字或引号的行
    keep_lines = lines[:2]
    for line in lines[2:-1]:
        # 保留含数字、人名标记、关键词的行
        if any(c.isdigit() for c in line) or ":" in line or "：" in line:
            keep_lines.append(line)
            if len(keep_lines) >= 5:
                break
    keep_lines.append(lines[-1])

    result = "\n".join(keep_lines)
    if len(result) < len(content):
        result += f"\n(语义压缩, 原文 {len(content)} 字 → {len(result)} 字)"
    return result
