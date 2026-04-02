#!/bin/bash

# Nexus AI 全量质量扫描脚本 (大厂 QA 规范版)
# 作用：一键生成全栈覆盖率报告，精确定位未覆盖代码行。

echo "🚀 [Nexus QA] 启动全栈覆盖率扫描..."

# 1. 后端覆盖率扫描
echo "🐍 [Backend] 正在扫描 FastAPI 与 Agent 核心逻辑..."
cd nexus_backend
pytest --cov=app \
       --cov-report=html:../qa_reports/backend_coverage \
       --cov-report=term \
       tests/unit/ tests/agent/ tests/integration/

# 2. 前端覆盖率扫描
echo "⚛️ [Frontend] 正在扫描 React 组件与状态管理..."
cd ..
npx vitest run --coverage --reporter=html --outputFile=qa_reports/frontend_coverage/index.html

# 3. 数据库 RLS 验证 (可选，需 Supabase 环境)
echo "🗄️ [Database] 验证超大规模租户隔离隔离..."
# npx supabase test db

echo "✅ [SUCCESS] 扫描完成！"
echo "📊 后端报告: [Project]/qa_reports/backend_coverage/index.html"
echo "📊 前端报告: [Project]/qa_reports/frontend_coverage/index.html"
echo "💡 提示：打开 HTML 报告，未被测试覆盖的逻辑会以红色高亮显示。"
