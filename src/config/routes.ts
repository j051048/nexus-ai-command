import { lazyWithPreload } from '@/lib/lazyPreload';

export const routes = {
    SalesPipeline: lazyWithPreload(() => import('@/components/sales/SalesPipeline').then(m => ({ default: m.SalesPipeline }))),
    ApprovalCenter: lazyWithPreload(() => import('@/components/approval/ApprovalCenter').then(m => ({ default: m.ApprovalCenter }))),
    RewardsWallet: lazyWithPreload(() => import('@/components/rewards/RewardsWallet').then(m => ({ default: m.RewardsWallet }))),
    SalesTargetManager: lazyWithPreload(() => import('@/components/targets/SalesTargetManager').then(m => ({ default: m.SalesTargetManager }))),
    EmployeeManagement: lazyWithPreload(() => import('@/components/admin/EmployeeManagement').then(m => ({ default: m.EmployeeManagement }))),
    AISettingsPanel: lazyWithPreload(() => import('@/components/settings/AISettingsPanel').then(m => ({ default: m.AISettingsPanel }))),
    ProjectDetail: lazyWithPreload(() => import('@/components/projects/ProjectDetail').then(m => ({ default: m.ProjectDetail }))),
    DocumentsPage: lazyWithPreload(() => import('@/components/documents/DocumentsPage').then(m => ({ default: m.DocumentsPage }))),
    ExceptionsPage: lazyWithPreload(() => import('@/pages/ExceptionsPage')),
};
