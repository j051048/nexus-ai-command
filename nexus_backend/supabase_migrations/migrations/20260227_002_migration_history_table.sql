-- #18: 迁移历史记录表
-- 用于自动迁移运行器 (migration_runner.py) 记录已应用的迁移

CREATE TABLE IF NOT EXISTS public.migration_history (
    id SERIAL PRIMARY KEY,
    migration_name TEXT NOT NULL UNIQUE,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum TEXT
);

-- 创建索引加速查找
CREATE INDEX IF NOT EXISTS idx_migration_history_name ON public.migration_history (migration_name);

COMMENT ON TABLE public.migration_history IS '数据库迁移历史记录，由 migration_runner.py 自动管理';
