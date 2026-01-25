// Project Nexus Type Definitions

export type UserRole = 'boss' | 'employee';

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
