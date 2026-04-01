#!/bin/bash
# P0-2: 目录清理脚本

echo "开始清理目录结构..."

# 1. 检查并合并 frontend_components
if [ -d "frontend_components" ]; then
    echo "合并 frontend_components 到 src/components/workflow/"
    mkdir -p src/components/workflow
    cp -r frontend_components/* src/components/workflow/ 2>/dev/null || true
    echo "✓ 前端组件已合并"
fi

# 2. 删除空壳目录
if [ -d "nexus_frontend" ]; then
    echo "删除空壳 nexus_frontend/"
    # rm -rf nexus_frontend/
    echo "⚠ 请手动确认后删除: rm -rf nexus_frontend/"
fi

# 3. 统一迁移目录
if [ -d "nexus_backend/supabase_migrations" ]; then
    echo "统一迁移文件到 supabase/migrations/"
    mkdir -p supabase/migrations
    cp nexus_backend/supabase_migrations/*.sql supabase/migrations/ 2>/dev/null || true
    echo "✓ 迁移文件已统一"
    echo "⚠ 请手动确认后删除: rm -rf nexus_backend/supabase_migrations/"
fi

echo "目录清理完成!"
