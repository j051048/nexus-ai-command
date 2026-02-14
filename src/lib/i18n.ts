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
    'common.actions': '操作',
    'common.status': '状态',
    'common.type': '类型',
    'common.name': '名称',
    'common.description': '描述',
    'common.date': '日期',
    'common.time': '时间',
    'common.amount': '金额',
    'common.total': '合计',
    'common.detail': '详情',
    'common.download': '下载',
    'common.upload': '上传',
    'common.preview': '预览',
    'common.success': '成功',
    'common.failed': '失败',
    'common.enabled': '已启用',
    'common.disabled': '已禁用',
    'common.required': '必填',
    'common.optional': '选填',
    'common.noData': '暂无数据',
    'common.copySuccess': '已复制到剪贴板',
    'common.operationSuccess': '操作成功',
    'common.operationFailed': '操作失败',
    'common.confirmDelete': '确认删除？此操作不可撤销。',

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
    'nav.workflows': '流程设计',
    'nav.formDesigner': '表单设计',
    'nav.audit': '审计日志',
    'nav.permissions': '权限管理',
    'nav.dataImport': '数据导入',
    'nav.billing': '订阅计费',
    'nav.organization': '组织管理',
    'nav.performance': '绩效管理',
    'nav.attendance': '考勤管理',

    // 仪表盘
    'dashboard.welcome': '欢迎回来，{name}',
    'dashboard.todayTasks': '今日待办',
    'dashboard.pendingApprovals': '待审批',
    'dashboard.salesTarget': '销售目标',
    'dashboard.teamPerformance': '团队绩效',
    'dashboard.recentActivities': '最近活动',
    'dashboard.quickActions': '快捷操作',
    'dashboard.systemStatus': '系统状态',
    'dashboard.totalEmployees': '员工总数',
    'dashboard.monthlyRevenue': '本月营收',

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
    'approval.submit': '提交审批',
    'approval.history': '审批历史',
    'approval.detail': '审批详情',
    'approval.chain': '审批链',
    'approval.currentStep': '当前步骤',
    'approval.autoApproved': '自动通过',
    'approval.escalated': '已升级',
    'approval.amount': '审批金额',
    'approval.type': '审批类型',
    'approval.expense': '费用报销',
    'approval.leave': '请假',
    'approval.purchase': '采购',
    'approval.travel': '出差',
    'approval.overtime': '加班',

    // 工作流
    'workflow.title': '工作流管理',
    'workflow.create': '创建工作流',
    'workflow.edit': '编辑工作流',
    'workflow.delete': '删除工作流',
    'workflow.name': '工作流名称',
    'workflow.description': '工作流描述',
    'workflow.steps': '流程步骤',
    'workflow.conditions': '条件分支',
    'workflow.active': '已激活',
    'workflow.inactive': '未激活',
    'workflow.setDefault': '设为默认',
    'workflow.toggle': '启用/禁用',
    'workflow.canvas': '画布设计器',
    'workflow.addStep': '添加步骤',
    'workflow.addCondition': '添加条件',
    'workflow.approvalNode': '审批节点',
    'workflow.conditionNode': '条件节点',
    'workflow.notifyNode': '通知节点',
    'workflow.endNode': '结束节点',
    'workflow.appliesTo': '适用类型',
    'workflow.noWorkflows': '暂无工作流，点击创建',
    'workflow.confirmDelete': '确认删除此工作流？关联的审批将使用默认流程。',

    // 表单设计器
    'formDesigner.title': '表单设计器',
    'formDesigner.create': '创建表单',
    'formDesigner.edit': '编辑表单',
    'formDesigner.preview': '预览表单',
    'formDesigner.publish': '发布',
    'formDesigner.draft': '草稿',
    'formDesigner.fields': '字段列表',
    'formDesigner.addField': '添加字段',
    'formDesigner.fieldType': '字段类型',
    'formDesigner.fieldLabel': '字段标签',
    'formDesigner.fieldRequired': '必填',
    'formDesigner.fieldPlaceholder': '占位文本',
    'formDesigner.textInput': '文本输入',
    'formDesigner.numberInput': '数字输入',
    'formDesigner.dateInput': '日期选择',
    'formDesigner.selectInput': '下拉选择',
    'formDesigner.fileUpload': '文件上传',
    'formDesigner.textarea': '多行文本',
    'formDesigner.bindApprovalType': '绑定审批类型',
    'formDesigner.noForms': '暂无表单，点击创建',

    // 审计日志
    'audit.title': '审计日志',
    'audit.action': '操作',
    'audit.actor': '操作人',
    'audit.target': '目标',
    'audit.timestamp': '时间',
    'audit.status': '状态',
    'audit.details': '详情',
    'audit.ipAddress': 'IP 地址',
    'audit.filterByAction': '按操作筛选',
    'audit.filterByUser': '按用户筛选',
    'audit.filterByDate': '按日期筛选',
    'audit.exportLogs': '导出日志',
    'audit.noLogs': '暂无审计日志',

    // 权限管理
    'permission.title': '权限管理',
    'permission.myPermissions': '我的权限',
    'permission.check': '权限检查',
    'permission.granted': '已授权',
    'permission.denied': '未授权',
    'permission.conditional': '条件授权',
    'permission.role': '角色',
    'permission.roles.employee': '员工',
    'permission.roles.manager': '经理',
    'permission.roles.boss': '总监',
    'permission.roles.founder': '创始人',
    'permission.rolePermissions': '角色权限',
    'permission.allRules': '所有权限规则',
    'permission.noPermission': '您没有此操作的权限',

    // 数据导入/导出
    'dataTransfer.title': '数据导入/导出',
    'dataTransfer.import': '导入数据',
    'dataTransfer.export': '导出数据',
    'dataTransfer.template': '下载模板',
    'dataTransfer.preview': '数据预览',
    'dataTransfer.validate': '预验证',
    'dataTransfer.selectFile': '选择文件',
    'dataTransfer.fileFormat': '支持 CSV 格式（UTF-8 编码）',
    'dataTransfer.maxSize': '文件大小不超过 10MB',
    'dataTransfer.importResult': '导入结果',
    'dataTransfer.successCount': '成功: {count} 条',
    'dataTransfer.skipCount': '跳过: {count} 条',
    'dataTransfer.errorCount': '失败: {count} 条',
    'dataTransfer.exportType': '选择导出类型',
    'dataTransfer.approvals': '审批记录',
    'dataTransfer.attendance': '考勤数据',
    'dataTransfer.sales': '销售数据',
    'dataTransfer.employees': '员工数据',
    'dataTransfer.customers': '客户数据',
    'dataTransfer.dateRange': '日期范围',
    'dataTransfer.downloading': '正在导出...',
    'dataTransfer.importInProgress': '正在导入...',

    // 计费/订阅
    'billing.title': '订阅计费',
    'billing.currentPlan': '当前套餐',
    'billing.freePlan': '免费版',
    'billing.proPlan': '专业版',
    'billing.enterprisePlan': '企业版',
    'billing.upgrade': '升级套餐',
    'billing.downgrade': '降级套餐',
    'billing.cancelSubscription': '取消订阅',
    'billing.billingHistory': '账单历史',
    'billing.nextBilling': '下次扣费日期',
    'billing.usage': '使用量',
    'billing.quota': '配额',
    'billing.trialDaysLeft': '试用剩余 {days} 天',
    'billing.trialExpired': '试用已到期',
    'billing.paymentMethod': '支付方式',

    // 组织管理
    'org.title': '组织管理',
    'org.name': '组织名称',
    'org.members': '成员管理',
    'org.departments': '部门管理',
    'org.inviteMember': '邀请成员',
    'org.removeMember': '移除成员',
    'org.changeRole': '变更角色',
    'org.totalMembers': '成员总数: {count}',

    // 绩效管理
    'performance.title': '绩效管理',
    'performance.myPerformance': '我的绩效',
    'performance.teamRanking': '团队排名',
    'performance.score': '绩效评分',
    'performance.period': '考核周期',
    'performance.review': '绩效评审',
    'performance.goals': '目标设定',
    'performance.feedback': '反馈',

    // 销售管理
    'sales.title': '销售管理',
    'sales.pipeline': '销售漏斗',
    'sales.leads': '潜在客户',
    'sales.opportunities': '商机',
    'sales.customers': '客户列表',
    'sales.deals': '成交记录',
    'sales.target': '销售目标',
    'sales.achievement': '达成率',
    'sales.ranking': '销售排行',

    // 知识库
    'knowledge.title': '知识库',
    'knowledge.upload': '上传文档',
    'knowledge.search': '搜索知识',
    'knowledge.documents': '文档列表',
    'knowledge.categories': '分类',
    'knowledge.recentViewed': '最近查看',
    'knowledge.fileTypes': '支持 PDF、Word、TXT 格式',
    'knowledge.processing': '文档处理中...',
    'knowledge.indexed': '已索引',

    // 通知
    'notification.title': '通知中心',
    'notification.markAllRead': '全部已读',
    'notification.noNotifications': '暂无通知',
    'notification.settings': '通知设置',
    'notification.push': '推送通知',
    'notification.email': '邮件通知',
    'notification.inApp': '站内通知',
    'notification.enablePush': '开启浏览器推送',
    'notification.disablePush': '关闭浏览器推送',

    // 设置
    'settings.theme': '主题设置',
    'settings.language': '语言设置',
    'settings.notifications': '通知设置',
    'settings.security': '安全设置',
    'settings.about': '关于',
    'settings.darkMode': '深色模式',
    'settings.lightMode': '浅色模式',
    'settings.systemMode': '跟随系统',
    'settings.changePassword': '修改密码',
    'settings.twoFactor': '两步验证',
    'settings.apiKeys': 'API 密钥',

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
    'error.validation': '数据校验失败，请检查输入',
    'error.fileTooLarge': '文件过大，请选择较小的文件',
    'error.unsupportedFormat': '不支持的文件格式',
    'error.timeout': '请求超时，请重试',
    'error.quotaExceeded': '已超出使用配额',
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
    'common.actions': 'Actions',
    'common.status': 'Status',
    'common.type': 'Type',
    'common.name': 'Name',
    'common.description': 'Description',
    'common.date': 'Date',
    'common.time': 'Time',
    'common.amount': 'Amount',
    'common.total': 'Total',
    'common.detail': 'Detail',
    'common.download': 'Download',
    'common.upload': 'Upload',
    'common.preview': 'Preview',
    'common.success': 'Success',
    'common.failed': 'Failed',
    'common.enabled': 'Enabled',
    'common.disabled': 'Disabled',
    'common.required': 'Required',
    'common.optional': 'Optional',
    'common.noData': 'No data available',
    'common.copySuccess': 'Copied to clipboard',
    'common.operationSuccess': 'Operation successful',
    'common.operationFailed': 'Operation failed',
    'common.confirmDelete': 'Are you sure you want to delete? This action cannot be undone.',

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
    'nav.workflows': 'Workflows',
    'nav.formDesigner': 'Form Designer',
    'nav.audit': 'Audit Logs',
    'nav.permissions': 'Permissions',
    'nav.dataImport': 'Data Import',
    'nav.billing': 'Billing',
    'nav.organization': 'Organization',
    'nav.performance': 'Performance',
    'nav.attendance': 'Attendance',

    // Dashboard
    'dashboard.welcome': 'Welcome back, {name}',
    'dashboard.todayTasks': "Today's Tasks",
    'dashboard.pendingApprovals': 'Pending Approvals',
    'dashboard.salesTarget': 'Sales Target',
    'dashboard.teamPerformance': 'Team Performance',
    'dashboard.recentActivities': 'Recent Activities',
    'dashboard.quickActions': 'Quick Actions',
    'dashboard.systemStatus': 'System Status',
    'dashboard.totalEmployees': 'Total Employees',
    'dashboard.monthlyRevenue': 'Monthly Revenue',

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
    'approval.submit': 'Submit Approval',
    'approval.history': 'Approval History',
    'approval.detail': 'Approval Detail',
    'approval.chain': 'Approval Chain',
    'approval.currentStep': 'Current Step',
    'approval.autoApproved': 'Auto Approved',
    'approval.escalated': 'Escalated',
    'approval.amount': 'Amount',
    'approval.type': 'Type',
    'approval.expense': 'Expense',
    'approval.leave': 'Leave',
    'approval.purchase': 'Purchase',
    'approval.travel': 'Travel',
    'approval.overtime': 'Overtime',

    // Workflows
    'workflow.title': 'Workflow Management',
    'workflow.create': 'Create Workflow',
    'workflow.edit': 'Edit Workflow',
    'workflow.delete': 'Delete Workflow',
    'workflow.name': 'Workflow Name',
    'workflow.description': 'Description',
    'workflow.steps': 'Steps',
    'workflow.conditions': 'Conditions',
    'workflow.active': 'Active',
    'workflow.inactive': 'Inactive',
    'workflow.setDefault': 'Set as Default',
    'workflow.toggle': 'Enable/Disable',
    'workflow.canvas': 'Canvas Designer',
    'workflow.addStep': 'Add Step',
    'workflow.addCondition': 'Add Condition',
    'workflow.approvalNode': 'Approval Node',
    'workflow.conditionNode': 'Condition Node',
    'workflow.notifyNode': 'Notification Node',
    'workflow.endNode': 'End Node',
    'workflow.appliesTo': 'Applies To',
    'workflow.noWorkflows': 'No workflows yet. Click to create one.',
    'workflow.confirmDelete': 'Delete this workflow? Associated approvals will use the default process.',

    // Form Designer
    'formDesigner.title': 'Form Designer',
    'formDesigner.create': 'Create Form',
    'formDesigner.edit': 'Edit Form',
    'formDesigner.preview': 'Preview Form',
    'formDesigner.publish': 'Publish',
    'formDesigner.draft': 'Draft',
    'formDesigner.fields': 'Fields',
    'formDesigner.addField': 'Add Field',
    'formDesigner.fieldType': 'Field Type',
    'formDesigner.fieldLabel': 'Label',
    'formDesigner.fieldRequired': 'Required',
    'formDesigner.fieldPlaceholder': 'Placeholder',
    'formDesigner.textInput': 'Text Input',
    'formDesigner.numberInput': 'Number Input',
    'formDesigner.dateInput': 'Date Picker',
    'formDesigner.selectInput': 'Dropdown',
    'formDesigner.fileUpload': 'File Upload',
    'formDesigner.textarea': 'Text Area',
    'formDesigner.bindApprovalType': 'Bind to Approval Type',
    'formDesigner.noForms': 'No forms yet. Click to create one.',

    // Audit
    'audit.title': 'Audit Logs',
    'audit.action': 'Action',
    'audit.actor': 'Actor',
    'audit.target': 'Target',
    'audit.timestamp': 'Timestamp',
    'audit.status': 'Status',
    'audit.details': 'Details',
    'audit.ipAddress': 'IP Address',
    'audit.filterByAction': 'Filter by Action',
    'audit.filterByUser': 'Filter by User',
    'audit.filterByDate': 'Filter by Date',
    'audit.exportLogs': 'Export Logs',
    'audit.noLogs': 'No audit logs',

    // Permissions
    'permission.title': 'Permission Management',
    'permission.myPermissions': 'My Permissions',
    'permission.check': 'Permission Check',
    'permission.granted': 'Granted',
    'permission.denied': 'Denied',
    'permission.conditional': 'Conditional',
    'permission.role': 'Role',
    'permission.roles.employee': 'Employee',
    'permission.roles.manager': 'Manager',
    'permission.roles.boss': 'Director',
    'permission.roles.founder': 'Founder',
    'permission.rolePermissions': 'Role Permissions',
    'permission.allRules': 'All Permission Rules',
    'permission.noPermission': 'You do not have permission for this action',

    // Data Transfer
    'dataTransfer.title': 'Data Import / Export',
    'dataTransfer.import': 'Import Data',
    'dataTransfer.export': 'Export Data',
    'dataTransfer.template': 'Download Template',
    'dataTransfer.preview': 'Data Preview',
    'dataTransfer.validate': 'Pre-validate',
    'dataTransfer.selectFile': 'Select File',
    'dataTransfer.fileFormat': 'CSV format supported (UTF-8 encoding)',
    'dataTransfer.maxSize': 'Max file size: 10MB',
    'dataTransfer.importResult': 'Import Result',
    'dataTransfer.successCount': 'Success: {count}',
    'dataTransfer.skipCount': 'Skipped: {count}',
    'dataTransfer.errorCount': 'Failed: {count}',
    'dataTransfer.exportType': 'Select Export Type',
    'dataTransfer.approvals': 'Approval Records',
    'dataTransfer.attendance': 'Attendance Data',
    'dataTransfer.sales': 'Sales Data',
    'dataTransfer.employees': 'Employee Data',
    'dataTransfer.customers': 'Customer Data',
    'dataTransfer.dateRange': 'Date Range',
    'dataTransfer.downloading': 'Exporting...',
    'dataTransfer.importInProgress': 'Importing...',

    // Billing
    'billing.title': 'Billing',
    'billing.currentPlan': 'Current Plan',
    'billing.freePlan': 'Free',
    'billing.proPlan': 'Pro',
    'billing.enterprisePlan': 'Enterprise',
    'billing.upgrade': 'Upgrade Plan',
    'billing.downgrade': 'Downgrade Plan',
    'billing.cancelSubscription': 'Cancel Subscription',
    'billing.billingHistory': 'Billing History',
    'billing.nextBilling': 'Next Billing Date',
    'billing.usage': 'Usage',
    'billing.quota': 'Quota',
    'billing.trialDaysLeft': '{days} trial days left',
    'billing.trialExpired': 'Trial expired',
    'billing.paymentMethod': 'Payment Method',

    // Organization
    'org.title': 'Organization',
    'org.name': 'Organization Name',
    'org.members': 'Members',
    'org.departments': 'Departments',
    'org.inviteMember': 'Invite Member',
    'org.removeMember': 'Remove Member',
    'org.changeRole': 'Change Role',
    'org.totalMembers': 'Total members: {count}',

    // Performance
    'performance.title': 'Performance',
    'performance.myPerformance': 'My Performance',
    'performance.teamRanking': 'Team Ranking',
    'performance.score': 'Score',
    'performance.period': 'Review Period',
    'performance.review': 'Performance Review',
    'performance.goals': 'Goals',
    'performance.feedback': 'Feedback',

    // Sales
    'sales.title': 'Sales Management',
    'sales.pipeline': 'Pipeline',
    'sales.leads': 'Leads',
    'sales.opportunities': 'Opportunities',
    'sales.customers': 'Customers',
    'sales.deals': 'Deals',
    'sales.target': 'Target',
    'sales.achievement': 'Achievement',
    'sales.ranking': 'Sales Ranking',

    // Knowledge Base
    'knowledge.title': 'Knowledge Base',
    'knowledge.upload': 'Upload Document',
    'knowledge.search': 'Search Knowledge',
    'knowledge.documents': 'Documents',
    'knowledge.categories': 'Categories',
    'knowledge.recentViewed': 'Recently Viewed',
    'knowledge.fileTypes': 'Supports PDF, Word, TXT formats',
    'knowledge.processing': 'Processing document...',
    'knowledge.indexed': 'Indexed',

    // Notifications
    'notification.title': 'Notifications',
    'notification.markAllRead': 'Mark All as Read',
    'notification.noNotifications': 'No notifications',
    'notification.settings': 'Notification Settings',
    'notification.push': 'Push Notifications',
    'notification.email': 'Email Notifications',
    'notification.inApp': 'In-App Notifications',
    'notification.enablePush': 'Enable Push Notifications',
    'notification.disablePush': 'Disable Push Notifications',

    // Settings
    'settings.theme': 'Theme',
    'settings.language': 'Language',
    'settings.notifications': 'Notifications',
    'settings.security': 'Security',
    'settings.about': 'About',
    'settings.darkMode': 'Dark Mode',
    'settings.lightMode': 'Light Mode',
    'settings.systemMode': 'System Default',
    'settings.changePassword': 'Change Password',
    'settings.twoFactor': 'Two-Factor Authentication',
    'settings.apiKeys': 'API Keys',

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
    'error.validation': 'Validation failed. Please check your input.',
    'error.fileTooLarge': 'File is too large. Please select a smaller file.',
    'error.unsupportedFormat': 'Unsupported file format.',
    'error.timeout': 'Request timed out. Please try again.',
    'error.quotaExceeded': 'Usage quota exceeded.',
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
    'common.actions': '操作',
    'common.status': 'ステータス',
    'common.type': 'タイプ',
    'common.name': '名前',
    'common.description': '説明',
    'common.date': '日付',
    'common.time': '時間',
    'common.amount': '金額',
    'common.total': '合計',
    'common.detail': '詳細',
    'common.download': 'ダウンロード',
    'common.upload': 'アップロード',
    'common.preview': 'プレビュー',
    'common.success': '成功',
    'common.failed': '失敗',
    'common.enabled': '有効',
    'common.disabled': '無効',
    'common.required': '必須',
    'common.optional': '任意',
    'common.noData': 'データがありません',
    'common.copySuccess': 'クリップボードにコピーしました',
    'common.operationSuccess': '操作が成功しました',
    'common.operationFailed': '操作が失敗しました',
    'common.confirmDelete': '削除してもよろしいですか？この操作は元に戻せません。',

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
    'nav.workflows': 'ワークフロー',
    'nav.formDesigner': 'フォームデザイナー',
    'nav.audit': '監査ログ',
    'nav.permissions': '権限管理',
    'nav.dataImport': 'データインポート',
    'nav.billing': '請求管理',
    'nav.organization': '組織管理',
    'nav.performance': '業績管理',
    'nav.attendance': '勤怠管理',

    // ダッシュボード
    'dashboard.welcome': 'おかえりなさい、{name}さん',
    'dashboard.todayTasks': '今日のタスク',
    'dashboard.pendingApprovals': '承認待ち',
    'dashboard.salesTarget': '売上目標',
    'dashboard.teamPerformance': 'チーム実績',
    'dashboard.recentActivities': '最近のアクティビティ',
    'dashboard.quickActions': 'クイックアクション',
    'dashboard.systemStatus': 'システム状態',
    'dashboard.totalEmployees': '従業員数',
    'dashboard.monthlyRevenue': '月間売上',

    // AI
    'ai.title': 'AIコマンドセンター',
    'ai.placeholder': 'コマンドを入力または質問...',
    'ai.thinking': 'AIが考えています...',
    'ai.selectAgent': 'AIエージェントを選択',
    'ai.salesAgent': '営業コマンダー',
    'ai.performanceAgent': 'パフォーマンスコーチ',
    'ai.assistantAgent': '企業アシスタント',
    'ai.knowledgeAgent': 'ナレッジアシスタント',

    // AI チャット
    'ai.sendMessage': 'メッセージを送信',
    'ai.newChat': '新しいチャット',
    'ai.chatHistory': '履歴',
    'ai.clearChat': 'チャットをクリア',
    'ai.copyMessage': 'メッセージをコピー',
    'ai.regenerate': '再生成',
    'ai.stopGeneration': '停止',
    'ai.uploadFile': 'ファイルをアップロード',
    'ai.uploadSuccess': 'ファイルのアップロードに成功しました',
    'ai.uploadFailed': 'ファイルのアップロードに失敗しました',
    'ai.loginRequired': 'ログインしてください',
    'ai.quotaExceeded': 'クォータを超過しました',
    'ai.networkError': 'ネットワークエラー。再試行してください',
    'ai.safetyBlock': 'コンテンツセーフティブロック',
    'ai.thinkingProcess': '思考プロセス',
    'ai.toolExecution': 'ツール実行中',
    'ai.searchingKnowledge': 'ナレッジベースを検索中',

    // 承認
    'approval.pending': '保留中',
    'approval.approved': '承認済み',
    'approval.rejected': '却下',
    'approval.expired': '期限切れ',
    'approval.approve': '承認',
    'approval.reject': '却下',
    'approval.comment': 'コメント',
    'approval.submit': '承認を申請',
    'approval.history': '承認履歴',
    'approval.detail': '承認詳細',
    'approval.chain': '承認チェーン',
    'approval.currentStep': '現在のステップ',
    'approval.autoApproved': '自動承認',
    'approval.escalated': 'エスカレーション済み',
    'approval.amount': '金額',
    'approval.type': 'タイプ',
    'approval.expense': '経費精算',
    'approval.leave': '休暇',
    'approval.purchase': '購入',
    'approval.travel': '出張',
    'approval.overtime': '残業',

    // ワークフロー
    'workflow.title': 'ワークフロー管理',
    'workflow.create': 'ワークフローを作成',
    'workflow.edit': 'ワークフローを編集',
    'workflow.delete': 'ワークフローを削除',
    'workflow.name': 'ワークフロー名',
    'workflow.description': '説明',
    'workflow.steps': 'ステップ',
    'workflow.conditions': '条件',
    'workflow.active': '有効',
    'workflow.inactive': '無効',
    'workflow.setDefault': 'デフォルトに設定',
    'workflow.toggle': '有効/無効',
    'workflow.canvas': 'キャンバスデザイナー',
    'workflow.addStep': 'ステップを追加',
    'workflow.addCondition': '条件を追加',
    'workflow.approvalNode': '承認ノード',
    'workflow.conditionNode': '条件ノード',
    'workflow.notifyNode': '通知ノード',
    'workflow.endNode': '終了ノード',
    'workflow.appliesTo': '適用タイプ',
    'workflow.noWorkflows': 'ワークフローがありません。クリックして作成してください。',
    'workflow.confirmDelete': 'このワークフローを削除しますか？関連する承認はデフォルトのプロセスを使用します。',

    // フォームデザイナー
    'formDesigner.title': 'フォームデザイナー',
    'formDesigner.create': 'フォームを作成',
    'formDesigner.edit': 'フォームを編集',
    'formDesigner.preview': 'フォームをプレビュー',
    'formDesigner.publish': '公開',
    'formDesigner.draft': '下書き',
    'formDesigner.fields': 'フィールド',
    'formDesigner.addField': 'フィールドを追加',
    'formDesigner.fieldType': 'フィールドタイプ',
    'formDesigner.fieldLabel': 'ラベル',
    'formDesigner.fieldRequired': '必須',
    'formDesigner.fieldPlaceholder': 'プレースホルダー',
    'formDesigner.textInput': 'テキスト入力',
    'formDesigner.numberInput': '数値入力',
    'formDesigner.dateInput': '日付選択',
    'formDesigner.selectInput': 'ドロップダウン',
    'formDesigner.fileUpload': 'ファイルアップロード',
    'formDesigner.textarea': 'テキストエリア',
    'formDesigner.bindApprovalType': '承認タイプに紐付け',
    'formDesigner.noForms': 'フォームがありません。クリックして作成してください。',

    // 監査ログ
    'audit.title': '監査ログ',
    'audit.action': '操作',
    'audit.actor': '操作者',
    'audit.target': '対象',
    'audit.timestamp': 'タイムスタンプ',
    'audit.status': 'ステータス',
    'audit.details': '詳細',
    'audit.ipAddress': 'IPアドレス',
    'audit.filterByAction': '操作で絞り込み',
    'audit.filterByUser': 'ユーザーで絞り込み',
    'audit.filterByDate': '日付で絞り込み',
    'audit.exportLogs': 'ログをエクスポート',
    'audit.noLogs': '監査ログはありません',

    // 権限管理
    'permission.title': '権限管理',
    'permission.myPermissions': 'マイ権限',
    'permission.check': '権限チェック',
    'permission.granted': '許可',
    'permission.denied': '拒否',
    'permission.conditional': '条件付き',
    'permission.role': 'ロール',
    'permission.roles.employee': '一般社員',
    'permission.roles.manager': 'マネージャー',
    'permission.roles.boss': 'ディレクター',
    'permission.roles.founder': '創業者',
    'permission.rolePermissions': 'ロール権限',
    'permission.allRules': 'すべての権限ルール',
    'permission.noPermission': 'この操作の権限がありません',

    // データ転送
    'dataTransfer.title': 'データインポート/エクスポート',
    'dataTransfer.import': 'データをインポート',
    'dataTransfer.export': 'データをエクスポート',
    'dataTransfer.template': 'テンプレートをダウンロード',
    'dataTransfer.preview': 'データプレビュー',
    'dataTransfer.validate': '事前検証',
    'dataTransfer.selectFile': 'ファイルを選択',
    'dataTransfer.fileFormat': 'CSV形式対応（UTF-8エンコーディング）',
    'dataTransfer.maxSize': 'ファイルサイズ上限: 10MB',
    'dataTransfer.importResult': 'インポート結果',
    'dataTransfer.successCount': '成功: {count}件',
    'dataTransfer.skipCount': 'スキップ: {count}件',
    'dataTransfer.errorCount': '失敗: {count}件',
    'dataTransfer.exportType': 'エクスポートタイプを選択',
    'dataTransfer.approvals': '承認記録',
    'dataTransfer.attendance': '勤怠データ',
    'dataTransfer.sales': '売上データ',
    'dataTransfer.employees': '従業員データ',
    'dataTransfer.customers': '顧客データ',
    'dataTransfer.dateRange': '日付範囲',
    'dataTransfer.downloading': 'エクスポート中...',
    'dataTransfer.importInProgress': 'インポート中...',

    // 請求管理
    'billing.title': '請求管理',
    'billing.currentPlan': '現在のプラン',
    'billing.freePlan': '無料プラン',
    'billing.proPlan': 'プロプラン',
    'billing.enterprisePlan': 'エンタープライズ',
    'billing.upgrade': 'プランをアップグレード',
    'billing.downgrade': 'プランをダウングレード',
    'billing.cancelSubscription': 'サブスクリプションをキャンセル',
    'billing.billingHistory': '請求履歴',
    'billing.nextBilling': '次回請求日',
    'billing.usage': '使用量',
    'billing.quota': 'クォータ',
    'billing.trialDaysLeft': 'トライアル残り{days}日',
    'billing.trialExpired': 'トライアル期限切れ',
    'billing.paymentMethod': '支払い方法',

    // 組織管理
    'org.title': '組織管理',
    'org.name': '組織名',
    'org.members': 'メンバー管理',
    'org.departments': '部門管理',
    'org.inviteMember': 'メンバーを招待',
    'org.removeMember': 'メンバーを削除',
    'org.changeRole': 'ロールを変更',
    'org.totalMembers': 'メンバー数: {count}',

    // 業績管理
    'performance.title': '業績管理',
    'performance.myPerformance': 'マイ業績',
    'performance.teamRanking': 'チームランキング',
    'performance.score': '評価スコア',
    'performance.period': '評価期間',
    'performance.review': '業績レビュー',
    'performance.goals': '目標設定',
    'performance.feedback': 'フィードバック',

    // 営業管理
    'sales.title': '営業管理',
    'sales.pipeline': 'パイプライン',
    'sales.leads': 'リード',
    'sales.opportunities': '商談',
    'sales.customers': '顧客一覧',
    'sales.deals': '成約記録',
    'sales.target': '売上目標',
    'sales.achievement': '達成率',
    'sales.ranking': '営業ランキング',

    // ナレッジベース
    'knowledge.title': 'ナレッジベース',
    'knowledge.upload': 'ドキュメントをアップロード',
    'knowledge.search': 'ナレッジを検索',
    'knowledge.documents': 'ドキュメント一覧',
    'knowledge.categories': 'カテゴリー',
    'knowledge.recentViewed': '最近の閲覧',
    'knowledge.fileTypes': 'PDF、Word、TXT形式に対応',
    'knowledge.processing': 'ドキュメント処理中...',
    'knowledge.indexed': 'インデックス済み',

    // 通知
    'notification.title': '通知',
    'notification.markAllRead': 'すべて既読にする',
    'notification.noNotifications': '通知はありません',
    'notification.settings': '通知設定',
    'notification.push': 'プッシュ通知',
    'notification.email': 'メール通知',
    'notification.inApp': 'アプリ内通知',
    'notification.enablePush': 'プッシュ通知を有効にする',
    'notification.disablePush': 'プッシュ通知を無効にする',

    // 設定
    'settings.theme': 'テーマ',
    'settings.language': '言語',
    'settings.notifications': '通知',
    'settings.security': 'セキュリティ',
    'settings.about': '概要',
    'settings.darkMode': 'ダークモード',
    'settings.lightMode': 'ライトモード',
    'settings.systemMode': 'システム設定に従う',
    'settings.changePassword': 'パスワードを変更',
    'settings.twoFactor': '二段階認証',
    'settings.apiKeys': 'APIキー',

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
    'error.validation': 'バリデーションに失敗しました。入力内容を確認してください。',
    'error.fileTooLarge': 'ファイルが大きすぎます。小さいファイルを選択してください。',
    'error.unsupportedFormat': 'サポートされていないファイル形式です。',
    'error.timeout': 'リクエストがタイムアウトしました。再試行してください。',
    'error.quotaExceeded': '使用量クォータを超過しました。',
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