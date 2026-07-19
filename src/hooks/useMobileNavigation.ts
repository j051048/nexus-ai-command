/**
 * 移动端导航逻辑 Hook
 * 封装 Tab 切换、子页面检测、返回、标题映射等逻辑
 */

import { useCallback, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/components/auth/AuthContext';

type TabId = 'home' | 'customers' | 'ai' | 'data' | 'profile';

interface TabConfig {
  defaultPath: string | ((role: string) => string);
  matchPaths: string[];
}

const TAB_CONFIG: Record<Exclude<TabId, 'ai'>, TabConfig> = {
  home: {
    defaultPath: '/dashboard',
    matchPaths: ['/dashboard'],
  },
  customers: {
    defaultPath: '/crm',
    matchPaths: ['/crm', '/sales', '/contracts', '/growth/solutions', '/growth/tenders', '/tender-analysis', '/battlecards'],
  },
  data: {
    defaultPath: '/data',
    matchPaths: [
      '/data', '/reports', '/report-builder', '/target-dashboard',
      '/boss-dashboard', '/custom-dashboard', '/customer-success',
    ],
  },
  profile: {
    defaultPath: '/profile',
    matchPaths: [
      '/profile', '/settings', '/rewards', '/payments', '/workbench',
      '/approval', '/projects', '/exceptions', '/workflows', '/oa',
      '/hr', '/finance', '/employees', '/roles', '/departments',
      '/targets', '/knowledge', '/documents', '/import', '/form-designer',
      '/workflow-templates', '/notification-center', '/api-keys',
      '/audit', '/training', '/admin', '/ai-center',
      '/vmd', '/vmd/tasks', '/vmd/agents', '/vmd/clues',
      '/vmd/compliance', '/vmd/dashboard', '/llm/models', '/plugins',
      '/agent-debug', '/agent-runs', '/tools/governance',
    ],
  },
};

/** 路径 → 中文标题映射 */
const PAGE_TITLES: Record<string, string> = {
  '/dashboard': '收件箱',
  '/workbench': '工作台',
  '/data': '数据',
  '/ai-center': '助手',
  '/boss-dashboard': '总控中心',
  '/approval': '工作台',
  '/sales': '销售管道',
  '/crm': 'CRM 客户',
  '/projects': '项目管理',
  '/contracts': '合同管理',
  '/exceptions': '异常待办',
  '/workflows': '工作流',
  '/oa': 'OA 办公',
  '/hr': '人事中心',
  '/finance': '财务中心',
  '/growth/solutions': '方案作战',
  '/growth/tenders': '投标作战',
  '/tender-analysis': '投标作战',
  '/battlecards': '竞品库',
  '/reports': '数据报表',
  '/employees': '员工管理',
  '/roles': '角色管理',
  '/departments': '部门管理',
  '/targets': '目标管理',
  '/target-dashboard': '目标看板',
  '/knowledge': '知识资产',
  '/knowledge/industry': '行业知识资产',
  '/knowledge/graph': '关系洞察',
  '/documents': '文档中心',
  '/import': '数据导入',
  '/form-designer': '表单设计',
  '/workflow-templates': '工作流模板',
  '/notification-center': '消息中心',
  '/profile': '我的',
  '/settings': '系统设置',
  '/rewards': '激励钱包',
  '/payments': '订阅支付',
  '/api-keys': 'API 密钥',
  '/audit': '审计日志',
  '/plugins': '插件市场',
  '/training': '培训中心',
  '/custom-dashboard': '自定义看板',
  '/admin': '超管面板',
  '/vmd': '虚拟市场部',
  '/vmd/tasks': 'VMD 任务中心',
  '/vmd/agents': 'Agent 配置',
  '/vmd/clues': '线索管理',
  '/vmd/compliance': '合规校验',
  '/vmd/dashboard': 'VMD 数据看板',
  '/llm/models': 'LLM 模型管理',
  '/agent-runs': 'Agent Run 管理台',
  '/tools/governance': 'Tool 治理',
  '/agent-debug': 'Agent 调试',
};

/** Tab 首页路径集合 — 这些路径算 Tab 首页，不显示返回按钮 */
const TAB_HOME_PATHS = new Set([
  '/dashboard',
  '/crm',
  '/data',
  '/profile',
]);

export function useMobileNavigation() {
  const location = useLocation();
  const navigate = useNavigate();
  const { role } = useAuth();

  /** 当前路径匹配到哪个 Tab */
  const activeTab = useMemo<TabId>(() => {
    const path = location.pathname;
    for (const [tabId, config] of Object.entries(TAB_CONFIG)) {
      if (config.matchPaths.some(p => path === p || path.startsWith(p + '/'))) {
        return tabId as TabId;
      }
    }
    return 'home';
  }, [location.pathname]);

  /** 是否在 Tab 首页之外的子页面（需要显示返回按钮） */
  const isSubPage = useMemo(() => {
    return !TAB_HOME_PATHS.has(location.pathname);
  }, [location.pathname]);

  /** 是否正好在某个 Tab 的首页路径上 */
  const isTabHomePage = useMemo(() => {
    return TAB_HOME_PATHS.has(location.pathname);
  }, [location.pathname]);

  /** 获取页面标题 */
  const getPageTitle = useCallback((path: string): string => {
    // 精确匹配
    if (PAGE_TITLES[path]) return PAGE_TITLES[path];
    // 前缀匹配（如 /projects/123）
    const basePath = '/' + path.split('/').filter(Boolean)[0];
    return PAGE_TITLES[basePath] || 'Nexus OS';
  }, []);

  /** 切换 Tab */
  const navigateToTab = useCallback((tabId: string) => {
    if (tabId === 'ai') return; // AI tab 由外层处理
    const config = TAB_CONFIG[tabId as Exclude<TabId, 'ai'>];
    if (!config) return;
    const path = typeof config.defaultPath === 'function'
      ? config.defaultPath(role || 'employee')
      : config.defaultPath;
    navigate(path);
  }, [navigate, role]);

  /** 返回上一页 */
  const goBack = useCallback(() => {
    // 尝试浏览器 history back
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      // 回退到当前 Tab 的首页
      const config = TAB_CONFIG[activeTab as Exclude<TabId, 'ai'>];
      if (config) {
        const path = typeof config.defaultPath === 'function'
          ? config.defaultPath(role || 'employee')
          : config.defaultPath;
        navigate(path);
      } else {
        navigate('/dashboard');
      }
    }
  }, [navigate, activeTab, role]);

  return {
    activeTab,
    isSubPage,
    isTabHomePage,
    getPageTitle,
    navigateToTab,
    goBack,
  };
}
