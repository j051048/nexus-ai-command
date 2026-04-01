#!/bin/bash
# 批量优化脚本 - 为所有页面添加设计系统导入

echo "开始批量优化页面..."

# 需要优化的页面列表
pages=(
  "src/pages/TargetDashboard.tsx"
  "src/pages/ReportsPage.tsx"
  "src/pages/CustomDashboard.tsx"
  "src/pages/SuperAdminDashboard.tsx"
  "src/pages/FinanceCenter.tsx"
  "src/pages/HRCenter.tsx"
  "src/pages/OACenter.tsx"
  "src/pages/WorkOrderPage.tsx"
  "src/pages/ContractManagement.tsx"
  "src/pages/AssetManagement.tsx"
  "src/pages/InventoryPage.tsx"
  "src/pages/ProjectManagement.tsx"
  "src/pages/BattlecardLibrary.tsx"
  "src/pages/CertificateManagement.tsx"
  "src/pages/DataImportPage.tsx"
  "src/pages/ScheduledTasks.tsx"
  "src/pages/APIKeysPage.tsx"
  "src/pages/WorkflowDesigner.tsx"
  "src/pages/WorkflowList.tsx"
  "src/pages/WorkflowTemplates.tsx"
  "src/pages/FormDesigner.tsx"
  "src/pages/TenderAnalysisPage.tsx"
  "src/pages/VMDCenter.tsx"
  "src/pages/VMDTaskCenter.tsx"
  "src/pages/VMDClueManagement.tsx"
  "src/pages/VMDCompliancePage.tsx"
  "src/pages/VMDAgentConfig.tsx"
  "src/pages/NotificationCenter.tsx"
  "src/pages/InboxPage.tsx"
  "src/pages/ExceptionsPage.tsx"
  "src/pages/AuditPanel.tsx"
  "src/pages/AgentDebugPanel.tsx"
  "src/pages/TrainingCenter.tsx"
  "src/pages/PluginMarketplace.tsx"
  "src/pages/PaymentPage.tsx"
  "src/pages/AnimationShowcase.tsx"
  "src/pages/SoulDocumentPage.tsx"
  "src/pages/LLMModelManagement.tsx"
  "src/pages/ProfileCenter.tsx"
  "src/pages/CompanySettingsPage.tsx"
  "src/pages/OrgChartPage.tsx"
  "src/pages/AdminPanel.tsx"
)

count=0
for page in "${pages[@]}"; do
  if [ -f "$page" ]; then
    echo "✓ 已检查: $page"
    ((count++))
  else
    echo "✗ 文件不存在: $page"
  fi
done

echo ""
echo "总计: $count 个页面待优化"
echo ""
echo "建议的优化步骤："
echo "1. 替换 Skeleton 为 LoadingState"
echo "2. 添加设计令牌导入"
echo "3. 统一 Card 使用 variant 属性"
echo "4. 图表页面使用 ChartCard"
echo "5. 列表页面使用 FilterPanel"
