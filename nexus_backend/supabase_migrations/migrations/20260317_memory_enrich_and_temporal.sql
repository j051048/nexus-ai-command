-- ============================================================================
-- Migration: Memory Enrichment & Temporal Tracking
-- Date: 2026-03-17
-- Purpose:
--   1. enriched_value: 上下文补全后的记忆文本（用于 embedding 生成）
--   2. valid_from: 事实的真实世界生效时间（非录入时间）
-- ============================================================================

-- enriched_value: 滑动窗口预处理后的自包含记忆文本
ALTER TABLE public.conversation_memories
    ADD COLUMN IF NOT EXISTS enriched_value TEXT;

-- valid_from: 记忆描述的事实何时生效（如"上个月搬家"对应的实际日期）
ALTER TABLE public.conversation_memories
    ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ;
