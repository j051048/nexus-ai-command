/**
 * 新功能 API 调用（使用统一 HTTP 客户端）
 */
import httpClient from './httpClient';

// Excel 导出
export async function exportToExcel(data: any[], filename?: string) {
  const res = await httpClient.post('/api/export/excel', { data, filename });
  return res.data;
}

// PDF 导出
export async function exportToPDF(content: string, title?: string, filename?: string) {
  const res = await httpClient.post('/api/export/pdf', {
    content,
    title,
    filename,
    format_type: 'markdown',
  });
  return res.data;
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
  const res = await httpClient.post('/api/charts/generate', params);
  return res.data;
}

// 智能数据分析
export async function analyzeData(query: string, context?: string) {
  const res = await httpClient.post('/api/analysis/query', { query, context });
  return res.data;
}

// 批量导入客户
export async function batchImportCustomers(data: any[]) {
  const res = await httpClient.post('/api/batch/import-customers', { data });
  return res.data;
}

// 批量分配线索
export async function batchAssignLeads(lead_ids: string[], owner_id: string) {
  const res = await httpClient.post('/api/batch/assign-leads', { lead_ids, owner_id });
  return res.data;
}
