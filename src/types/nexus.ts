// Project Nexus Type Definitions

// 三级权限系统
// Level 1: boss (founder) - 最高权限，完整管理后台
// Level 2: ai_assistant - AI助手，可代理员工操作
// Level 3: employee - 普通员工
export type UserRole = 'boss' | 'ai_assistant' | 'employee' | 'sales' | 'manager';

export interface User {
  id: string;
  name: string;
  avatar: string;
  role: UserRole;
  department: string;
  score: number;
  rank: number;
  totalBonus: number;
  badges: Badge[];
}

export interface Badge {
  id: string;
  name: string;
  icon: string;
  description: string;
  unlockedAt?: Date;
  tier: 'bronze' | 'silver' | 'gold';
}

export interface SalesLead {
  id: string;
  name: string;
  company: string;
  title: string;
  score: number;
  stage: 'new' | 'contacted' | 'qualified' | 'proposal' | 'negotiation' | 'won' | 'lost';
  aiSuggestion: string;
  lastContact?: Date;
  winProbability: number;
}

export interface ApprovalRequest {
  id: string;
  type: 'travel' | 'purchase' | 'expense' | 'leave' | 'activity';
  description: string;
  amount: number;
  status: 'pending' | 'auto_approved' | 'requires_boss' | 'approved' | 'rejected';
  submittedBy: User;
  submittedAt: Date;
  aiReason?: string;
  // 新增：支持AI代理提交
  onBehalfOf?: string;        // 被代理的员工ID
  submittedVia?: 'direct' | 'ai_assistant' | 'api';  // 提交渠道
}

export interface ActiveCard {
  id: string;
  type: 'lead' | 'bonus' | 'task' | 'alert' | 'ranking' | 'script';
  title: string;
  content: string;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  timestamp: Date;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export interface PerformanceMetric {
  id: string;
  name: string;
  current: number;
  target: number;
  unit: string;
  trend: 'up' | 'down' | 'stable';
  change: number;
}

export interface AIMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  agent?: string;
  cards?: ActiveCard[];
}

export interface WeeklyReport {
  cashFlow: number;
  cashFlowTrend: number;
  salesRisks: string[];
  totalIncentives: number;
  topPerformers: { name: string; score: number; bonus: number }[];
  winRateTrend: number[];
}

export interface NexusDocument {
  id: string;
  name: string;
  doc_type: 'contract' | 'bid' | 'product' | 'other' | 'proposal' | 'invoice';
  extracted_data?: {
    client_name?: string;
    amount?: number;
    date?: string;
    summary?: string;
  };
  status: 'processing' | 'completed' | 'error';
  created_at: string;
  size?: string;
}

export interface Project {
  id: string;
  owner_id: string;
  name: string;
  description: string;
  status: 'planning' | 'in_progress' | 'completed' | 'on_hold';
  progress: number;
  start_date: string;
  end_date: string;
  created_at: string;
  updated_at: string;
  // UI Helpers
  stage?: string;
  type?: string;
}

export interface ProjectTimeline {
  id: string;
  project_id: string;
  title: string;
  content: string;
  event_type: 'milestone' | 'meeting' | 'dinner' | 'task';
  created_by: string;
  created_at: string;
  // UI Helper
  occurred_at?: string;
}
