/**
 * OpenClaw / MoltBot Built-in Tools
 * 内置工具集合 - 提供常用的企业管理工具
 */

import { Tool, ToolContext } from '../types';

// ==================== 数据查询工具 ====================

/**
 * 查询销售数据
 */
export const querySalesData: Tool = {
  name: 'query_sales_data',
  description: '查询销售数据，包括销售额、订单数、客户数等指标',
  parameters: {
    type: 'object',
    properties: {
      startDate: {
        type: 'string',
        description: '开始日期，格式：YYYY-MM-DD',
      },
      endDate: {
        type: 'string',
        description: '结束日期，格式：YYYY-MM-DD',
      },
      metrics: {
        type: 'array',
        description: '要查询的指标列表',
        items: {
          type: 'string',
          enum: ['revenue', 'orders', 'customers', 'avg_order_value', 'conversion_rate'],
        },
      },
      groupBy: {
        type: 'string',
        description: '分组维度',
        enum: ['day', 'week', 'month', 'salesperson', 'product', 'region'],
      },
    },
    required: ['startDate', 'endDate'],
  },
  execute: async (params, context) => {
    // 实际实现中应该调用后端 API
    console.log('[Tool] query_sales_data:', params);
    return {
      success: true,
      data: {
        period: { start: params.startDate, end: params.endDate },
        metrics: {
          revenue: 1250000,
          orders: 342,
          customers: 156,
          avgOrderValue: 3654,
          conversionRate: 0.125,
        },
        trend: '+12.5%',
      },
    };
  },
};

/**
 * 查询项目状态
 */
export const queryProjectStatus: Tool = {
  name: 'query_project_status',
  description: '查询项目的当前状态、进度和关键信息',
  parameters: {
    type: 'object',
    properties: {
      projectId: {
        type: 'string',
        description: '项目ID',
      },
      projectName: {
        type: 'string',
        description: '项目名称（模糊搜索）',
      },
      status: {
        type: 'string',
        description: '项目状态筛选',
        enum: ['planning', 'in_progress', 'completed', 'on_hold'],
      },
    },
  },
  execute: async (params, context) => {
    console.log('[Tool] query_project_status:', params);
    return {
      success: true,
      projects: [
        {
          id: 'proj-001',
          name: '智慧园区项目',
          status: 'in_progress',
          progress: 65,
          dueDate: '2024-03-15',
          owner: '张经理',
        },
      ],
    };
  },
};

/**
 * 查询审批列表
 */
export const queryApprovals: Tool = {
  name: 'query_approvals',
  description: '查询待审批或已审批的申请列表',
  parameters: {
    type: 'object',
    properties: {
      status: {
        type: 'string',
        description: '审批状态',
        enum: ['pending', 'approved', 'rejected', 'all'],
      },
      type: {
        type: 'string',
        description: '审批类型',
        enum: ['expense', 'leave', 'purchase', 'travel', 'all'],
      },
      limit: {
        type: 'number',
        description: '返回数量限制',
        default: 10,
      },
    },
  },
  execute: async (params, context) => {
    console.log('[Tool] query_approvals:', params);
    return {
      success: true,
      approvals: [
        {
          id: 'appr-001',
          type: 'expense',
          title: '客户拜访差旅费报销',
          amount: 3500,
          submitter: '李销售',
          status: 'pending',
          submitTime: '2024-01-15 10:30',
        },
      ],
      total: 5,
    };
  },
};

// ==================== 操作工具 ====================

/**
 * 创建任务
 */
export const createTask: Tool = {
  name: 'create_task',
  description: '创建新的任务或待办事项',
  parameters: {
    type: 'object',
    properties: {
      title: {
        type: 'string',
        description: '任务标题',
      },
      description: {
        type: 'string',
        description: '任务描述',
      },
      assignee: {
        type: 'string',
        description: '负责人',
      },
      dueDate: {
        type: 'string',
        description: '截止日期，格式：YYYY-MM-DD',
      },
      priority: {
        type: 'string',
        description: '优先级',
        enum: ['low', 'medium', 'high', 'urgent'],
      },
      projectId: {
        type: 'string',
        description: '关联项目ID',
      },
    },
    required: ['title'],
  },
  execute: async (params, context) => {
    console.log('[Tool] create_task:', params);
    return {
      success: true,
      task: {
        id: `task-${Date.now()}`,
        ...params,
        status: 'pending',
        createdAt: new Date().toISOString(),
        createdBy: context.userId,
      },
    };
  },
};

/**
 * 发送通知
 */
export const sendNotification: Tool = {
  name: 'send_notification',
  description: '向指定用户发送通知消息',
  parameters: {
    type: 'object',
    properties: {
      recipients: {
        type: 'array',
        description: '接收者ID列表',
        items: { type: 'string' },
      },
      title: {
        type: 'string',
        description: '通知标题',
      },
      message: {
        type: 'string',
        description: '通知内容',
      },
      type: {
        type: 'string',
        description: '通知类型',
        enum: ['info', 'success', 'warning', 'error'],
      },
      action: {
        type: 'object',
        description: '操作按钮配置',
        properties: {
          label: { type: 'string' },
          url: { type: 'string' },
        },
      },
    },
    required: ['recipients', 'title', 'message'],
  },
  execute: async (params, context) => {
    console.log('[Tool] send_notification:', params);
    return {
      success: true,
      notificationId: `notif-${Date.now()}`,
      sentTo: params.recipients,
      sentAt: new Date().toISOString(),
    };
  },
};

/**
 * 处理审批
 */
export const processApproval: Tool = {
  name: 'process_approval',
  description: '处理审批请求（通过或驳回）',
  parameters: {
    type: 'object',
    properties: {
      approvalId: {
        type: 'string',
        description: '审批ID',
      },
      action: {
        type: 'string',
        description: '审批操作',
        enum: ['approve', 'reject'],
      },
      comment: {
        type: 'string',
        description: '审批意见',
      },
    },
    required: ['approvalId', 'action'],
  },
  permissions: ['approval:write'],
  execute: async (params, context) => {
    console.log('[Tool] process_approval:', params);
    return {
      success: true,
      approvalId: params.approvalId,
      action: params.action,
      processedBy: context.userId,
      processedAt: new Date().toISOString(),
    };
  },
};

// ==================== 分析工具 ====================

/**
 * 生成报告
 */
export const generateReport: Tool = {
  name: 'generate_report',
  description: '生成各类业务报告',
  parameters: {
    type: 'object',
    properties: {
      reportType: {
        type: 'string',
        description: '报告类型',
        enum: ['sales_summary', 'project_progress', 'team_performance', 'financial_overview'],
      },
      period: {
        type: 'string',
        description: '报告周期',
        enum: ['daily', 'weekly', 'monthly', 'quarterly', 'yearly'],
      },
      format: {
        type: 'string',
        description: '输出格式',
        enum: ['text', 'json', 'markdown'],
      },
      includeSections: {
        type: 'array',
        description: '包含的章节',
        items: { type: 'string' },
      },
    },
    required: ['reportType', 'period'],
  },
  execute: async (params, context) => {
    console.log('[Tool] generate_report:', params);
    return {
      success: true,
      report: {
        type: params.reportType,
        period: params.period,
        generatedAt: new Date().toISOString(),
        summary: '本周销售额同比增长 15%，完成目标的 85%。重点客户跟进顺利，3 个大项目进入商务谈判阶段。',
        highlights: [
          '新签约客户 12 家',
          '在谈商机金额 ¥2,500,000',
          '团队人均绩效提升 8%',
        ],
        recommendations: [
          '加强对重点客户的跟进频率',
          '关注竞品动态，及时调整策略',
        ],
      },
    };
  },
};

/**
 * 分析商机
 */
export const analyzeOpportunity: Tool = {
  name: 'analyze_opportunity',
  description: '分析销售商机，提供智能建议',
  parameters: {
    type: 'object',
    properties: {
      opportunityId: {
        type: 'string',
        description: '商机ID',
      },
      analysisType: {
        type: 'string',
        description: '分析类型',
        enum: ['win_probability', 'competitor_analysis', 'next_steps', 'risk_assessment'],
      },
    },
    required: ['opportunityId'],
  },
  execute: async (params, context) => {
    console.log('[Tool] analyze_opportunity:', params);
    return {
      success: true,
      analysis: {
        opportunityId: params.opportunityId,
        winProbability: 0.72,
        stage: 'negotiation',
        estimatedValue: 850000,
        keyFactors: {
          positive: ['决策人关系良好', '技术方案获认可', '预算已确认'],
          negative: ['竞争对手报价较低', '采购流程复杂'],
        },
        recommendations: [
          '安排高层拜访，加强战略层面沟通',
          '准备详细的 ROI 分析报告',
          '考虑提供增值服务提升竞争力',
        ],
        nextActions: [
          { action: '发送定制化方案', deadline: '2024-01-20' },
          { action: '安排产品演示', deadline: '2024-01-25' },
        ],
      },
    };
  },
};

// ==================== 知识库工具 ====================

/**
 * 搜索知识库
 */
export const searchKnowledge: Tool = {
  name: 'search_knowledge',
  description: '搜索企业知识库，包括文档、FAQ、最佳实践等',
  parameters: {
    type: 'object',
    properties: {
      query: {
        type: 'string',
        description: '搜索查询',
      },
      category: {
        type: 'string',
        description: '知识分类',
        enum: ['product', 'sales', 'technical', 'policy', 'faq', 'all'],
      },
      limit: {
        type: 'number',
        description: '返回结果数量',
        default: 5,
      },
    },
    required: ['query'],
  },
  execute: async (params, context) => {
    console.log('[Tool] search_knowledge:', params);
    return {
      success: true,
      results: [
        {
          id: 'doc-001',
          title: '产品报价指南',
          summary: '详细介绍产品定价策略和折扣权限...',
          category: 'sales',
          relevance: 0.95,
          url: '/knowledge/doc-001',
        },
        {
          id: 'doc-002',
          title: '竞品对比分析',
          summary: '主要竞争对手的产品特点和优劣势对比...',
          category: 'sales',
          relevance: 0.88,
          url: '/knowledge/doc-002',
        },
      ],
      totalCount: 15,
    };
  },
};

// ==================== 日程工具 ====================

/**
 * 查询日程
 */
export const queryCalendar: Tool = {
  name: 'query_calendar',
  description: '查询日程安排',
  parameters: {
    type: 'object',
    properties: {
      userId: {
        type: 'string',
        description: '用户ID，不填则查询当前用户',
      },
      startDate: {
        type: 'string',
        description: '开始日期',
      },
      endDate: {
        type: 'string',
        description: '结束日期',
      },
      type: {
        type: 'string',
        description: '日程类型',
        enum: ['meeting', 'task', 'reminder', 'all'],
      },
    },
  },
  execute: async (params, context) => {
    console.log('[Tool] query_calendar:', params);
    return {
      success: true,
      events: [
        {
          id: 'evt-001',
          title: '客户拜访 - ABC公司',
          type: 'meeting',
          startTime: '2024-01-16 14:00',
          endTime: '2024-01-16 16:00',
          location: 'ABC公司总部',
          attendees: ['张三', '李四'],
        },
        {
          id: 'evt-002',
          title: '周例会',
          type: 'meeting',
          startTime: '2024-01-17 09:00',
          endTime: '2024-01-17 10:00',
          location: '会议室A',
        },
      ],
    };
  },
};

/**
 * 创建日程
 */
export const createCalendarEvent: Tool = {
  name: 'create_calendar_event',
  description: '创建新的日程事件',
  parameters: {
    type: 'object',
    properties: {
      title: {
        type: 'string',
        description: '事件标题',
      },
      type: {
        type: 'string',
        description: '事件类型',
        enum: ['meeting', 'task', 'reminder'],
      },
      startTime: {
        type: 'string',
        description: '开始时间，格式：YYYY-MM-DD HH:mm',
      },
      endTime: {
        type: 'string',
        description: '结束时间',
      },
      location: {
        type: 'string',
        description: '地点',
      },
      attendees: {
        type: 'array',
        description: '参与者',
        items: { type: 'string' },
      },
      reminder: {
        type: 'number',
        description: '提前提醒时间（分钟）',
      },
      description: {
        type: 'string',
        description: '事件描述',
      },
    },
    required: ['title', 'startTime'],
  },
  execute: async (params, context) => {
    console.log('[Tool] create_calendar_event:', params);
    return {
      success: true,
      event: {
        id: `evt-${Date.now()}`,
        ...params,
        createdBy: context.userId,
        createdAt: new Date().toISOString(),
      },
    };
  },
};

// ==================== 导出所有工具 ====================

export const builtInTools: Tool[] = [
  querySalesData,
  queryProjectStatus,
  queryApprovals,
  createTask,
  sendNotification,
  processApproval,
  generateReport,
  analyzeOpportunity,
  searchKnowledge,
  queryCalendar,
  createCalendarEvent,
];

export default builtInTools;