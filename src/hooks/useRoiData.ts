import { useQuery } from "@tanstack/react-query";
import { httpClient } from "@/lib/httpClient";

export interface RoiSummary {
  total_ai_cost: number;
  total_tokens: number;
  total_llm_calls: number;
  total_tool_calls: number;
  total_tool_success: number;
  total_minutes_saved: number;
  total_labor_saved: number;
  avg_roi_percent: number;
  total_positive_feedback: number;
  total_negative_feedback: number;
  avg_response_time_ms: number;
}

export interface RoiDaily {
  date: string;
  cost: number;
  saved: number;
  tool_calls: number;
  minutes_saved: number;
  roi: number;
}

export interface RoiData {
  summary: RoiSummary;
  daily: RoiDaily[];
  by_category: Record<string, number>;
  days: number;
}

export interface RoiBaseline {
  action_category: string;
  baseline_minutes: number;
  hourly_labor_cost: number;
  description: string;
}

export function useRoiData(days: number = 30) {
  return useQuery<RoiData>({
    queryKey: ["ai-roi", days],
    queryFn: async () => {
      const res = await httpClient.get(`/api/dashboard/roi?days=${days}`);
      return res.data?.data ?? res.data;
    },
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

export function useRoiBaselines() {
  return useQuery<RoiBaseline[]>({
    queryKey: ["ai-roi-baselines"],
    queryFn: async () => {
      const res = await httpClient.get("/api/dashboard/roi/baselines");
      return res.data?.data ?? res.data;
    },
    staleTime: 30 * 60 * 1000,
  });
}
