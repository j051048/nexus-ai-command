/**
 * 新功能 API 调用
 */
import { getApiBaseUrl } from './apiConfig';

const API_BASE = getApiBaseUrl();

// Excel 导出
export async function exportToExcel(data: any[], filename?: string) {
  const res = await fetch(`${API_BASE}/api/export/excel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ data, filename }),
  });
  if (!res.ok) throw new Error('导出失败');
  return res.json();
}

// PDF 导出
export async function exportToPDF(content: string, title?: string, filename?: string) {
  const res = await fetch(`${API_BASE}/api/export/pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ content, title, filename, format_type: 'markdown' }),
  });
  if (!res.ok) throw new Error('导出失败');
  return res.json();
}

// 生成图表
export async function generateChart(params: {
  chart_type: 'line' | 'bar' | 'pie' | 'funnel' | 'scatter' | 'heatmap';
  data: any;
  title?: string;
  x_label?: string;
  y_label?: string;
  output_format?: 'html' | 'json';
}) {
  const res = await fetch(`${API_BASE}/api/charts/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error('生成失败');
  return res.json();
}

// 智能数据分析
export async function analyzeData(query: string, context?: string) {
  const res = await fetch(`${API_BASE}/api/analysis/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ query, context }),
  });
  if (!res.ok) throw new Error('分析失败');
  return res.json();
}

// 批量导入客户
export async function batchImportCustomers(data: any[]) {
  const res = await fetch(`${API_BASE}/api/batch/import-customers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ data }),
  });
  if (!res.ok) throw new Error('导入失败');
  return res.json();
}

// 批量分配线索
export async function batchAssignLeads(lead_ids: string[], owner_id: string) {
  const res = await fetch(`${API_BASE}/api/batch/assign-leads`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ lead_ids, owner_id }),
  });
  if (!res.ok) throw new Error('分配失败');
  return res.json();
}
