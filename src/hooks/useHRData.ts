import { useQuery } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from '@/components/auth/AuthContext';

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
  const targetMonth = month || new Date().toISOString().slice(0, 7);

  return useQuery({
    queryKey: ['hr-attendance', user?.id, targetMonth],
    queryFn: async () => {
      const startDate = `${targetMonth}-01`;
      const [y, m] = targetMonth.split('-').map(Number);
      const lastDay = new Date(y, m, 0).getDate();
      const endDate = `${targetMonth}-${String(lastDay).padStart(2, '0')}`;

      const { data, error } = await supabase.from('hr_attendance')
        .select('*')
        .eq('user_id', user?.id)
        .gte('date', startDate)
        .lte('date', endDate)
        .order('date', { ascending: false });

      if (error) throw error;
      return (data || []) as AttendanceRecord[];
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
  const targetPeriod = period || new Date().toISOString().slice(0, 7);

  return useQuery({
    queryKey: ['hr-salary', user?.id, targetPeriod],
    queryFn: async () => {
      const { data, error } = await supabase.from('hr_salary_records')
        .select('*')
        .eq('user_id', user?.id)
        .eq('period', targetPeriod)
        .maybeSingle();

      if (error) throw error;
      return data as SalaryRecord | null;
    },
    enabled: !!user?.id,
  });
}

export function usePerformanceData(period?: string) {
  const { user } = useAuth();

  return useQuery({
    queryKey: ['hr-performance', user?.id, period],
    queryFn: async () => {
      let query = supabase.from('hr_performance_reviews')
        .select('*')
        .eq('user_id', user?.id)
        .order('created_at', { ascending: false });

      if (period) {
        query = query.eq('period', period);
      }

      const { data, error } = await query.limit(1).maybeSingle();
      if (error) throw error;
      return data as PerformanceReview | null;
    },
    enabled: !!user?.id,
  });
}

export function useRecruitmentList() {
  const { profile } = useAuth();

  return useQuery({
    queryKey: ['hr-positions', profile?.organization_id],
    queryFn: async () => {
      const { data, error } = await supabase.from('hr_job_positions')
        .select('*')
        .eq('organization_id', profile?.organization_id)
        .order('created_at', { ascending: false });

      if (error) throw error;
      return (data || []) as JobPosition[];
    },
    enabled: !!profile?.organization_id,
  });
}

export function useCandidates(positionId: string | null) {
  return useQuery({
    queryKey: ['hr-candidates', positionId],
    queryFn: async () => {
      const { data, error } = await supabase.from('hr_candidates')
        .select('*')
        .eq('position_id', positionId)
        .order('created_at', { ascending: false });

      if (error) throw error;
      return (data || []) as HRCandidate[];
    },
    enabled: !!positionId,
  });
}
