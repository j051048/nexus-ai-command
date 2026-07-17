import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import VMDCenter from "@/pages/VMDCenter";

const growthData = {
  schema_version: "growth-command.v1",
  generated_at: "2026-07-17T08:00:00+00:00",
  metrics: {
    open_opportunities: 2,
    pipeline_value: 880000,
    high_priority_signals: 1,
    active_tasks: 1,
    active_tenders: 1,
    conversion_rate: 20,
    classified_records: 1,
  },
  actions: [
    {
      id: "next:clue:1",
      priority: "high",
      title: "高分辨质谱采购意向",
      recommendation: "确认预算与采购时间",
      reason: "行业线索 · 2 条可核验证据",
      confidence: "high",
      execution_mode: "recommend",
      target_url: "/vmd/clues?detail=1",
      source_signal_id: "clue:1",
      instrument_line_code: "mass_spectrometry",
      instrument_line_name: "质谱",
      application_field: "环境痕量检测",
      domain_context: {
        domain_version: "scientific-instrument.v1",
        instrument_line_code: "mass_spectrometry",
        instrument_line_name: "质谱",
        product_models: ["ICP-MS 9000"],
        classification_status: "classified",
      },
    },
  ],
  signals: [],
  accounts: [],
  tenders: [],
  review: {
    completed_growth_tasks: 2,
    accepted_actions: 3,
    completed_actions: 2,
    action_adoption_rate: 75,
    estimated_hours_saved: 8,
    qualified_leads: 1,
    wins: 0,
    attributed_revenue: 580000,
    outcome_evidence_count: 2,
    evidence_note: "估算说明",
  },
  context_graph: { nodes: 4, links: 2, entity_types: ["clue"] },
  playbooks: [],
  capabilities: [
    {
      key: "crm.accounts",
      name: "客户与项目",
      category: "signal",
      status: "ready",
      risk_level: "low",
      requires_confirmation: false,
      contract_version: "v1",
    },
  ],
  source_health: { clues: "ready" },
  domain_catalog: {
    domain_version: "scientific-instrument.v1",
    instrument_lines: [],
  },
  instrument_line_summary: [
    { code: "mass_spectrometry", name: "质谱", signals: 1, accounts: 0, tenders: 0, tasks: 0 },
  ],
  sandbox: { enabled: false, data_isolation: "workspace", production_data_mixed: false },
};

vi.mock("@/hooks/useGrowthCommand", () => ({
  useGrowthCommand: vi.fn(() => ({
    data: growthData,
    isLoading: false,
    isError: false,
    isFetching: false,
    refetch: vi.fn(),
  })),
}));

function renderPage(path = "/dashboard") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <VMDCenter />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Growth command center", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows a compact outcome-first action workspace", () => {
    renderPage();

    expect(screen.getByTestId("growth-command-center")).toBeDefined();
    expect(screen.getByText("今天最值得推进的业务")).toBeDefined();
    expect(screen.getByText("高分辨质谱采购意向")).toBeDefined();
    expect(screen.getByText("确认预算与采购时间")).toBeDefined();
  });

  it("selects the radar view from the versioned route", () => {
    renderPage("/growth/radar");
    expect(screen.getByText("值得核验的行业信号")).toBeDefined();
  });

  it("filters the workspace by the canonical instrument line", () => {
    renderPage("/dashboard?line=mass_spectrometry");

    expect(screen.getByText("质谱")).toBeDefined();
    expect(screen.getByText("高分辨质谱采购意向")).toBeDefined();
  });
});
