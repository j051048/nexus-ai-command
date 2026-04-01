import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/components/auth/AuthContext';
import { httpClient } from '@/lib/httpClient';

// Interfaces for HR tables (not in generated types.ts)

export interface AttendanceRecord {
  id: string;
  user_id: string;
  date: string;
  check_in: string | null;
  check_out: string | null;
  status: 'normal' | 'late' | 'early_leave' | 'absent' | 'leave';
  late_minutes: number;
  early_leave_minutes: number;
  overtime_hours: number;
  source: string;
  created_at: string;
}

export interface SalaryRecord {
  id: string;
  user_id: string;
  period: string;
  base_salary: number;
  performance_bonus: number;
  attendance_bonus: number;
  other_allowances: number;
  gross_salary: number;
  social_insurance: number;
  housing_fund: number;
  tax: number;
  other_deductions: number;
  net_salary: number;
  payment_date: string | null;
  payment_status: 'pending' | 'paid';
  created_at: string;
}

export interface PerformanceReview {
  id: string;
  user_id: string;
  reviewer_id: string | null;
  period: string;
  self_rating: number | null;
  manager_rating: number | null;
  final_rating: number | null;
  ai_rating: number | null;
  ai_analysis: string | null;
  goals: Array<{ title: string; target: string; actual: string; completion_rate: number }>;
  strengths: string | null;
  improvements: string | null;
  status: 'draft' | 'submitted' | 'reviewed' | 'finalized';
  created_at: string;
  updated_at: string;
}

export interface JobPosition {
  id: string;
  title: string;
  department: string | null;
  description: string | null;
  requirements: string | null;
  salary_range_min: number | null;
  salary_range_max: number | null;
  headcount: number;
  hired_count: number;
  status: 'open' | 'paused' | 'closed';
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface HRCandidate {
  id: string;
  position_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  resume_url: string | null;
  status: string;
  ai_score: number | null;
  ai_analysis: string | null;
  interview_date: string | null;
  created_at: string;
}

// --- Hooks ---

export function useAttendanceRecords(month?: string) {
  const { user } = useAuth();

  return useQuery({
    queryKey: ['hr-attendance', user?.id, month],
    queryFn: async () => {
      const response = await httpClient.get('/api/hr/attendance');
      return response.data?.records || [];
    },
    enabled: !!user?.id,
  });
}

export function useAttendanceStats(month?: string) {
  const { data: records = [], isLoading } = useAttendanceRecords(month);

  const stats = {
    workDays: records.length,
    actualDays: records.filter(r => r.status !== 'absent' && r.status !== 'leave').length,
    lateTimes: records.filter(r => r.status === 'late').length,
    earlyLeaveTimes: records.filter(r => r.status === 'early_leave').length,
    overtimeHours: records.reduce((sum, r) => sum + Number(r.overtime_hours || 0), 0),
    attendanceRate: records.length > 0
      ? ((records.filter(r => r.status !== 'absent' && r.status !== 'leave').length / records.length) * 100)
      : 0,
  };

  return { stats, records, isLoading };
}

export function useSalaryRecords(period?: string) {
  const { user } = useAuth();

  return useQuery({
    queryKey: ['hr-salary', user?.id, period],
    queryFn: async () => {
      const response = await httpClient.get('/api/hr/salary');
      return response.data?.records?.[0] || null;
    },
    enabled: !!user?.id,
  });
}

export function usePerformanceData(period?: string) {
  const { user } = useAuth();

  return useQuery({
    queryKey: ['hr-performance', user?.id, period],
    queryFn: async () => {
      const response = await httpClient.get('/api/hr/performance');
      return response.data?.reviews?.[0] || null;
    },
    enabled: !!user?.id,
  });
}

export function useRecruitmentList() {
  const { profile } = useAuth();

  return useQuery({
    queryKey: ['hr-positions', profile?.organization_id],
    queryFn: async () => {
      const response = await httpClient.get('/api/hr/positions');
      return response.data?.positions || [];
    },
    enabled: !!profile?.organization_id,
  });
}

export function useCandidates(positionId: string | null) {
  return useQuery({
    queryKey: ['hr-candidates', positionId],
    queryFn: async () => {
      const response = await httpClient.get('/api/hr/candidates');
      return response.data?.candidates || [];
    },
    enabled: !!positionId,
  });
}
