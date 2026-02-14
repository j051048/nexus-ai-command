/**
 * P2 UX Enhancement: Internationalization (i18n) Framework
 * 国际化框架 - 支持多语言
 */



// ==================== 类型定义 ====================

export type Locale = 'zh-CN' | 'en-US' | 'ja-JP';

export interface LocaleConfig {
  code: Locale;
  name: string;
  nativeName: string;
  flag: string;
  dateFormat: string;
  numberFormat: Intl.NumberFormatOptions;
}

export type TranslationKey = string;
export type TranslationValues = Record<string, string | number>;
export type Translations = Record<string, string | Record<string, string>>;

// ==================== 语言配置 ====================

export const localeConfigs: Record<Locale, LocaleConfig> = {
  'zh-CN': {
    code: 'zh-CN',
    name: 'Chinese (Simplified)',
    nativeName: '简体中文',
    flag: '🇨🇳',
    dateFormat: 'YYYY年MM月DD日',
    numberFormat: { style: 'decimal', minimumFractionDigits: 0 },
  },
  'en-US': {
    code: 'en-US',
    name: 'English (US)',
    nativeName: 'English',
    flag: '🇺🇸',
    dateFormat: 'MM/DD/YYYY',
    numberFormat: { style: 'decimal', minimumFractionDigits: 0 },
  },
  'ja-JP': {
    code: 'ja-JP',
    name: 'Japanese',
    nativeName: '日本語',
    flag: '🇯🇵',
    dateFormat: 'YYYY/MM/DD',
    numberFormat: { style: 'decimal', minimumFractionDigits: 0 },
  },
};

// ==================== 翻译资源 ====================

const translations: Record<Locale, Translations> = {
  'zh-CN': {
    // 通用
    'common.loading': '加载中...',
    'common.error': '出错了',
    'common.retry': '重试',
    'common.cancel': '取消',
    'common.confirm': '确认',
    'common.save': '保存',
    'common.delete': '删除',
    'common.edit': '编辑',
    'common.add': '添加',
    'common.search': '搜索',
    'common.filter': '筛选',
    'common.export': '导出',
    'common.import': '导入',
    'common.refresh': '刷新',
    'common.back': '返回',
    'common.next': '下一步',
    'common.previous': '上一步',
    'common.submit': '提交',
    'common.reset': '重置',
    'common.close': '关闭',
    'common.yes': '是',
    'common.no': '否',
    'common.all': '全部',
    'common.none': '无',
    'common.more': '更多',
    'common.less': '收起',

    // 导航
    'nav.dashboard': '工作台',
    'nav.projects': '项目管理',
    'nav.sales': '销售管理',
    'nav.approval': '智能审批',
    'nav.rewards': '激励钱包',
    'nav.knowledge': '知识库',
    'nav.settings': '设置',
    'nav.profile': '个人中心',
    'nav.logout': '退出登录',

    // 仪表盘
    'dashboard.welcome': '欢迎回来，{name}',
    'dashboard.todayTasks': '今日待办',
    'dashboard.pendingApprovals': '待审批',
    'dashboard.salesTarget': '销售目标',
    'dashboard.teamPerformance': '团队绩效',
    'dashboard.recentActivities': '最近活动',

    // AI 助手
    'ai.title': 'AI 指挥中心',
    'ai.placeholder': '输入指令或提问...',
    'ai.thinking': 'AI 正在思考...',
    'ai.selectAgent': '选择 AI 助手',
    'ai.salesAgent': '销售指挥官',
    'ai.performanceAgent': '绩效教练',
    'ai.assistantAgent': '企业小助手',
    'ai.knowledgeAgent': '知识助手',

    // AI Chat
    'ai.sendMessage': '发送消息',
    'ai.newChat': '新对话',
    'ai.chatHistory': '历史记录',
    'ai.clearChat': '清空对话',
    'ai.copyMessage': '复制消息',
    'ai.regenerate': '重新生成',
    'ai.stopGeneration': '停止生成',
    'ai.uploadFile': '上传文件',
    'ai.uploadSuccess': '文件上传成功',
    'ai.uploadFailed': '文件上传失败',
    'ai.loginRequired': '请先登录',
    'ai.quotaExceeded': '配额已用尽',
    'ai.networkError': '网络连接失败，请重试',
    'ai.safetyBlock': '内容安全拦截',
    'ai.thinkingProcess': '思考过程',
    'ai.toolExecution': '工具执行中',
    'ai.searchingKnowledge': '正在检索知识库',

    // Approval
    'approval.pending': '待审批',
    'approval.approved': '已通过',
    'approval.rejected': '已驳回',
    'approval.expired': '已过期',
    'approval.approve': '通过',
    'approval.reject': '驳回',
    'approval.comment': '审批意见',

    // 通知
    'notification.title': '通知中心',
    'notification.markAllRead': '全部已读',
    'notification.noNotifications': '暂无通知',
    'notification.settings': '通知设置',

    // 设置
    'settings.theme': '主题设置',
    'settings.language': '语言设置',
    'settings.notifications': '通知设置',
    'settings.security': '安全设置',
    'settings.about': '关于',

    // 时间
    'time.justNow': '刚刚',
    'time.minutesAgo': '{count} 分钟前',
    'time.hoursAgo': '{count} 小时前',
    'time.daysAgo': '{count} 天前',
    'time.today': '今天',
    'time.yesterday': '昨天',

    // 错误
    'error.network': '网络连接失败，请检查网络后重试',
    'error.unauthorized': '登录已过期，请重新登录',
    'error.forbidden': '您没有权限执行此操作',
    'error.notFound': '请求的资源不存在',
    'error.serverError': '服务器错误，请稍后重试',
    'error.unknown': '发生未知错误',
  },

  'en-US': {
    // Common
    'common.loading': 'Loading...',
    'common.error': 'Error',
    'common.retry': 'Retry',
    'common.cancel': 'Cancel',
    'common.confirm': 'Confirm',
    'common.save': 'Save',
    'common.delete': 'Delete',
    'common.edit': 'Edit',
    'common.add': 'Add',
    'common.search': 'Search',
    'common.filter': 'Filter',
    'common.export': 'Export',
    'common.import': 'Import',
    'common.refresh': 'Refresh',
    'common.back': 'Back',
    'common.next': 'Next',
    'common.previous': 'Previous',
    'common.submit': 'Submit',
    'common.reset': 'Reset',
    'common.close': 'Close',
    'common.yes': 'Yes',
    'common.no': 'No',
    'common.all': 'All',
    'common.none': 'None',
    'common.more': 'More',
    'common.less': 'Less',

    // Navigation
    'nav.dashboard': 'Dashboard',
    'nav.projects': 'Projects',
    'nav.sales': 'Sales',
    'nav.approval': 'Approvals',
    'nav.rewards': 'Rewards',
    'nav.knowledge': 'Knowledge Base',
    'nav.settings': 'Settings',
    'nav.profile': 'Profile',
    'nav.logout': 'Logout',

    // Dashboard
    'dashboard.welcome': 'Welcome back, {name}',
    'dashboard.todayTasks': "Today's Tasks",
    'dashboard.pendingApprovals': 'Pending Approvals',
    'dashboard.salesTarget': 'Sales Target',
    'dashboard.teamPerformance': 'Team Performance',
    'dashboard.recentActivities': 'Recent Activities',

    // AI Assistant
    'ai.title': 'AI Command Center',
    'ai.placeholder': 'Enter command or ask a question...',
    'ai.thinking': 'AI is thinking...',
    'ai.selectAgent': 'Select AI Agent',
    'ai.salesAgent': 'Sales Commander',
    'ai.performanceAgent': 'Performance Coach',
    'ai.assistantAgent': 'Enterprise Assistant',
    'ai.knowledgeAgent': 'Knowledge Assistant',

    // AI Chat
    'ai.sendMessage': 'Send Message',
    'ai.newChat': 'New Chat',
    'ai.chatHistory': 'Chat History',
    'ai.clearChat': 'Clear Chat',
    'ai.copyMessage': 'Copy Message',
    'ai.regenerate': 'Regenerate',
    'ai.stopGeneration': 'Stop',
    'ai.uploadFile': 'Upload File',
    'ai.uploadSuccess': 'File uploaded successfully',
    'ai.uploadFailed': 'File upload failed',
    'ai.loginRequired': 'Please login first',
    'ai.quotaExceeded': 'Quota exceeded',
    'ai.networkError': 'Network error, please retry',
    'ai.safetyBlock': 'Content safety block',
    'ai.thinkingProcess': 'Thinking Process',
    'ai.toolExecution': 'Executing tool',
    'ai.searchingKnowledge': 'Searching knowledge base',

    // Approval
    'approval.pending': 'Pending',
    'approval.approved': 'Approved',
    'approval.rejected': 'Rejected',
    'approval.expired': 'Expired',
    'approval.approve': 'Approve',
    'approval.reject': 'Reject',
    'approval.comment': 'Comment',

    // Notifications
    'notification.title': 'Notifications',
    'notification.markAllRead': 'Mark All as Read',
    'notification.noNotifications': 'No notifications',
    'notification.settings': 'Notification Settings',

    // Settings
    'settings.theme': 'Theme',
    'settings.language': 'Language',
    'settings.notifications': 'Notifications',
    'settings.security': 'Security',
    'settings.about': 'About',

    // Time
    'time.justNow': 'Just now',
    'time.minutesAgo': '{count} minutes ago',
    'time.hoursAgo': '{count} hours ago',
    'time.daysAgo': '{count} days ago',
    'time.today': 'Today',
    'time.yesterday': 'Yesterday',

    // Errors
    'error.network': 'Network error. Please check your connection.',
    'error.unauthorized': 'Session expired. Please login again.',
    'error.forbidden': 'You do not have permission to perform this action.',
    'error.notFound': 'The requested resource was not found.',
    'error.serverError': 'Server error. Please try again later.',
    'error.unknown': 'An unknown error occurred.',
  },

  'ja-JP': {
    // 共通
    'common.loading': '読み込み中...',
    'common.error': 'エラー',
    'common.retry': '再試行',
    'common.cancel': 'キャンセル',
    'common.confirm': '確認',
    'common.save': '保存',
    'common.delete': '削除',
    'common.edit': '編集',
    'common.add': '追加',
    'common.search': '検索',
    'common.filter': 'フィルター',
    'common.export': 'エクスポート',
    'common.import': 'インポート',
    'common.refresh': '更新',
    'common.back': '戻る',
    'common.next': '次へ',
    'common.previous': '前へ',
    'common.submit': '送信',
    'common.reset': 'リセット',
    'common.close': '閉じる',
    'common.yes': 'はい',
    'common.no': 'いいえ',
    'common.all': 'すべて',
    'common.none': 'なし',
    'common.more': 'もっと見る',
    'common.less': '閉じる',

    // ナビゲーション
    'nav.dashboard': 'ダッシュボード',
    'nav.projects': 'プロジェクト',
    'nav.sales': '営業管理',
    'nav.approval': '承認',
    'nav.rewards': '報酬',
    'nav.knowledge': 'ナレッジベース',
    'nav.settings': '設定',
    'nav.profile': 'プロフィール',
    'nav.logout': 'ログアウト',

    // ダッシュボード
    'dashboard.welcome': 'おかえりなさい、{name}さん',
    'dashboard.todayTasks': '今日のタスク',
    'dashboard.pendingApprovals': '承認待ち',
    'dashboard.salesTarget': '売上目標',
    'dashboard.teamPerformance': 'チーム実績',
    'dashboard.recentActivities': '最近のアクティビティ',

    // AI
    'ai.title': 'AIコマンドセンター',
    'ai.placeholder': 'コマンドを入力または質問...',
    'ai.thinking': 'AIが考えています...',
    'ai.selectAgent': 'AIエージェントを選択',
    'ai.salesAgent': '営業コマンダー',
    'ai.performanceAgent': 'パフォーマンスコーチ',
    'ai.assistantAgent': '企業アシスタント',
    'ai.knowledgeAgent': 'ナレッジアシスタント',

    // 承認
    'approval.pending': '保留中',
    'approval.approved': '承認済み',
    'approval.rejected': '却下',
    'approval.expired': '期限切れ',
    'approval.approve': '承認',
    'approval.reject': '却下',
    'approval.comment': 'コメント',

    // 通知
    'notification.title': '通知',
    'notification.markAllRead': 'すべて既読にする',
    'notification.noNotifications': '通知はありません',
    'notification.settings': '通知設定',

    // 設定
    'settings.theme': 'テーマ',
    'settings.language': '言語',
    'settings.notifications': '通知',
    'settings.security': 'セキュリティ',
    'settings.about': '概要',

    // 時間
    'time.justNow': 'たった今',
    'time.minutesAgo': '{count}分前',
    'time.hoursAgo': '{count}時間前',
    'time.daysAgo': '{count}日前',
    'time.today': '今日',
    'time.yesterday': '昨日',

    // エラー
    'error.network': 'ネットワークエラー。接続を確認してください。',
    'error.unauthorized': 'セッションが期限切れです。再度ログインしてください。',
    'error.forbidden': 'この操作を実行する権限がありません。',
    'error.notFound': 'リソースが見つかりません。',
    'error.serverError': 'サーバーエラー。後でもう一度お試しください。',
    'error.unknown': '不明なエラーが発生しました。',
  },
};

// ==================== Store (使用 React Context 替代 zustand) ====================

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
}

const I18nContext = createContext<I18nContextValue | undefined>(undefined);

const STORAGE_KEY = 'nexus-i18n-locale';

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && (saved === 'zh-CN' || saved === 'en-US' || saved === 'ja-JP')) {
        return saved as Locale;
      }
    }
    return 'zh-CN';
  });

  const setLocale = (newLocale: Locale) => {
    setLocaleState(newLocale);
    localStorage.setItem(STORAGE_KEY, newLocale);
  };

  return React.createElement(
    I18nContext.Provider,
    { value: { locale, setLocale } },
    children
  );
}

function useI18nContext() {
  const context = useContext(I18nContext);
  // 如果没有 Provider，返回默认值
  if (!context) {
    return {
      locale: 'zh-CN' as Locale,
      setLocale: () => console.warn('I18nProvider not found'),
    };
  }
  return context;
}

// 用于在组件外部获取当前 locale 的简单方法
let currentLocale: Locale = 'zh-CN';
if (typeof window !== 'undefined') {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved && (saved === 'zh-CN' || saved === 'en-US' || saved === 'ja-JP')) {
    currentLocale = saved as Locale;
  }
}

function getLocale(): Locale {
  if (typeof window !== 'undefined') {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && (saved === 'zh-CN' || saved === 'en-US' || saved === 'ja-JP')) {
      return saved as Locale;
    }
  }
  return currentLocale;
}

// ==================== 翻译函数 ====================

/**
 * 获取翻译文本
 */
export function t(key: TranslationKey, values?: TranslationValues): string {
  const locale = getLocale();
  const translation = translations[locale]?.[key] || translations['zh-CN']?.[key] || key;

  if (typeof translation !== 'string') {
    return key;
  }

  if (!values) {
    return translation;
  }

  // 替换占位符 {key}
  return translation.replace(/\{(\w+)\}/g, (_, k) => {
    return values[k]?.toString() || `{${k}}`;
  });
}

/**
 * 格式化数字
 */
export function formatNumber(value: number, options?: Intl.NumberFormatOptions): string {
  const locale = getLocale();
  const config = localeConfigs[locale];
  return new Intl.NumberFormat(locale, { ...config.numberFormat, ...options }).format(value);
}

/**
 * 格式化货币
 */
export function formatCurrency(value: number, currency: string = 'CNY'): string {
  const locale = getLocale();
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
  }).format(value);
}

/**
 * 格式化日期
 */
export function formatDate(
  date: Date | string | number,
  options?: Intl.DateTimeFormatOptions
): string {
  const locale = getLocale();
  const dateObj = typeof date === 'string' || typeof date === 'number' ? new Date(date) : date;
  return new Intl.DateTimeFormat(locale, options).format(dateObj);
}

/**
 * 格式化相对时间
 */
export function formatRelativeTime(date: Date | string | number): string {
  const locale = getLocale();
  const dateObj = typeof date === 'string' || typeof date === 'number' ? new Date(date) : date;
  const now = new Date();
  const diffMs = now.getTime() - dateObj.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return t('time.justNow');
  if (diffMins < 60) return t('time.minutesAgo', { count: diffMins });
  if (diffHours < 24) return t('time.hoursAgo', { count: diffHours });
  if (diffDays < 7) return t('time.daysAgo', { count: diffDays });

  return formatDate(dateObj, { year: 'numeric', month: 'short', day: 'numeric' });
}

// ==================== React Hook ====================

import { useMemo } from 'react';

export function useTranslation() {
  const { locale, setLocale } = useI18nContext();
  const config = localeConfigs[locale];

  const i18n = useMemo(
    () => ({
      locale,
      config,
      setLocale,
      t: (key: TranslationKey, values?: TranslationValues) => t(key, values),
      formatNumber,
      formatCurrency,
      formatDate,
      formatRelativeTime,
      locales: Object.values(localeConfigs),
    }),
    [locale, config, setLocale]
  );

  return i18n;
}

export default {
  I18nProvider,
  useTranslation,
  t,
  formatNumber,
  formatCurrency,
  formatDate,
  formatRelativeTime,
  localeConfigs,
};