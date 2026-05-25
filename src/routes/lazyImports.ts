import { lazyWithRetry } from "@/lib/lazyPreload";

// Core pages
export const DashboardLayout = lazyWithRetry(() => import("@/pages/Index"));
export const NotFound = lazyWithRetry(() => import("@/pages/NotFound"));
export const EmployeeDashboard = lazyWithRetry(() => import("@/components/dashboard/EmployeeDashboard").then(m => ({ default: m.EmployeeDashboard })));
export const BossDashboard = lazyWithRetry(() => import("@/components/dashboard/BossDashboard").then(m => ({ default: m.BossDashboard })));

// Projects & Sales
export const ProjectManagement = lazyWithRetry(() => import("@/pages/ProjectManagement").then(m => ({ default: m.ProjectManagement })));
export const ProjectDetail = lazyWithRetry(() => import("@/components/projects/ProjectDetail").then(m => ({ default: m.ProjectDetail })));
export const SalesPipeline = lazyWithRetry(() => import("@/components/sales/SalesPipeline").then(m => ({ default: m.SalesPipeline })));
export const ApprovalCenter = lazyWithRetry(() => import("@/components/approval/ApprovalCenter").then(m => ({ default: m.ApprovalCenter })));
export const ExceptionsPage = lazyWithRetry(() => import("@/pages/ExceptionsPage"));
export const RewardsWallet = lazyWithRetry(() => import("@/components/rewards/RewardsWallet").then(m => ({ default: m.RewardsWallet })));
export const SalesTargetManager = lazyWithRetry(() => import("@/components/targets/SalesTargetManager").then(m => ({ default: m.SalesTargetManager })));
export const TargetDashboard = lazyWithRetry(() => import("@/pages/TargetDashboard"));
export const TenderAnalysisPage = lazyWithRetry(() => import("@/pages/TenderAnalysisPage").then(m => ({ default: m.TenderAnalysisPage })));
export const BattlecardLibrary = lazyWithRetry(() => import("@/pages/BattlecardLibrary").then(m => ({ default: m.BattlecardLibrary })));

// Documents & Knowledge
export const DocumentsPage = lazyWithRetry(() => import("@/components/documents/DocumentsPage").then(m => ({ default: m.DocumentsPage })));
export const KnowledgeGraphPage = lazyWithRetry(() => import("@/pages/knowledge/KnowledgeGraphPage"));
export const DataImportPage = lazyWithRetry(() => import("@/pages/DataImportPage"));

// Business Management
export const CRMPage = lazyWithRetry(() => import("@/pages/CRMPage"));
export const ContractManagement = lazyWithRetry(() => import("@/pages/ContractManagement"));
export const TrainingCenter = lazyWithRetry(() => import("@/pages/TrainingCenter"));
export const WorkOrderPage = lazyWithRetry(() => import("@/pages/WorkOrderPage"));
export const AssetManagement = lazyWithRetry(() => import("@/pages/AssetManagement"));
export const CertificateManagement = lazyWithRetry(() => import("@/pages/CertificateManagement"));
export const InventoryPage = lazyWithRetry(() => import("@/pages/InventoryPage"));

// Inbox (unified todo center)
export const InboxPage = lazyWithRetry(() => import("@/pages/InboxPage"));
export const IndustryKnowledgePage = lazyWithRetry(() => import("@/pages/IndustryKnowledgePage"));
export const AIOperatingSystemPage = lazyWithRetry(() => import("@/pages/AIOperatingSystemPage"));
export const WorkspaceHubPage = lazyWithRetry(() => import("@/pages/ProductSpaceHubPage").then(m => ({ default: m.WorkspaceHubPage })));
export const DataHubPage = lazyWithRetry(() => import("@/pages/ProductSpaceHubPage").then(m => ({ default: m.DataHubPage })));
export const AICenterPage = lazyWithRetry(() => import("@/pages/ProductSpaceHubPage").then(m => ({ default: m.AICenterPage })));

// OA & Enterprise
export const OACenter = lazyWithRetry(() => import("@/pages/OACenter"));
export const HRCenter = lazyWithRetry(() => import("@/pages/HRCenter"));
export const FinanceCenter = lazyWithRetry(() => import("@/pages/FinanceCenter"));
export const ProfileCenter = lazyWithRetry(() => import("@/pages/ProfileCenter"));

// Workflow
export const WorkflowList = lazyWithRetry(() => import("@/pages/WorkflowList"));
export const WorkflowDesigner = lazyWithRetry(() => import("@/pages/WorkflowDesigner"));
export const WorkflowTemplates = lazyWithRetry(() => import("@/pages/WorkflowTemplates"));
export const FormDesigner = lazyWithRetry(() => import("@/pages/FormDesigner"));

// Dashboard & Reports
export const CustomDashboard = lazyWithRetry(() => import("@/pages/CustomDashboard"));
export const AuditPanel = lazyWithRetry(() => import("@/pages/AuditPanel"));
export const NotificationCenter = lazyWithRetry(() => import("@/pages/NotificationCenter"));
export const ReportsPage = lazyWithRetry(() => import("@/pages/ReportsPage"));
export const ReportBuilderPage = lazyWithRetry(() => import("@/pages/ReportBuilderPage"));
export const PaymentPage = lazyWithRetry(() => import("@/pages/PaymentPage"));

// Billing (Stripe)
export const BillingDashboard = lazyWithRetry(() => import("@/pages/billing/BillingDashboard"));
export const CheckoutSuccessPage = lazyWithRetry(() => import("@/pages/billing/CheckoutSuccessPage"));
export const CheckoutCancelPage = lazyWithRetry(() => import("@/pages/billing/CheckoutCancelPage"));

// Admin
export const AISettingsPanel = lazyWithRetry(() => import("@/components/settings/AISettingsPanel").then(m => ({ default: m.AISettingsPanel })));

export const SuperAdminDashboard = lazyWithRetry(() => import("@/pages/SuperAdminDashboard"));
export const APIKeysPage = lazyWithRetry(() => import("@/pages/APIKeysPage"));
export const AdminPanel = lazyWithRetry(() => import("@/pages/AdminPanel"));
export const CompanySettingsPage = lazyWithRetry(() => import("@/pages/CompanySettingsPage"));
export const OrgChartPage = lazyWithRetry(() => import("@/pages/OrgChartPage"));
export const PluginMarketplace = lazyWithRetry(() => import("@/pages/PluginMarketplace"));
export const LLMModelManagement = lazyWithRetry(() => import("@/pages/LLMModelManagement"));
export const LLMCostDashboard = lazyWithRetry(() => import("@/pages/LLMCostDashboard"));
export const SoulDocumentPage = lazyWithRetry(() => import("@/pages/SoulDocumentPage"));
export const AgentRunsPage = lazyWithRetry(() => import("@/pages/AgentRunsPage"));
export const ToolGovernancePage = lazyWithRetry(() => import("@/pages/ToolGovernancePage"));
export const SLODashboard = lazyWithRetry(() => import("@/pages/SLODashboard"));
export const DeploymentReadinessPage = lazyWithRetry(() => import("@/pages/DeploymentReadinessPage"));
export const PermissionMatrixPage = lazyWithRetry(() => import("@/pages/PermissionMatrixPage"));

// VMD
export const VMDCenter = lazyWithRetry(() => import("@/pages/VMDCenter"));
export const VMDTaskCenter = lazyWithRetry(() => import("@/pages/VMDTaskCenter"));
export const VMDAgentConfig = lazyWithRetry(() => import("@/pages/VMDAgentConfig"));
export const VMDClueManagement = lazyWithRetry(() => import("@/pages/VMDClueManagement"));
export const VMDDashboard = lazyWithRetry(() => import("@/pages/VMDDashboard"));
export const VMDCompliancePage = lazyWithRetry(() => import("@/pages/VMDCompliancePage"));
export const AgentDebugPanel = lazyWithRetry(() => import("@/pages/AgentDebugPanel"));
export const ScheduledTasks = lazyWithRetry(() => import("@/pages/ScheduledTasks"));
export const IntentRulesPage = lazyWithRetry(() => import("@/pages/admin/IntentRulesPage"));

// Dev
export const AnimationShowcase = lazyWithRetry(() => import("@/pages/AnimationShowcase"));

// ROI
export const AiRoiDashboard = lazyWithRetry(() => import("@/pages/AiRoiDashboard"));
export const CustomerSuccessPage = lazyWithRetry(() => import("@/pages/CustomerSuccessPage"));
