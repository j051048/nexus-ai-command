export interface DeliverableEligibility {
  canCreateArtifact: boolean;
  canQuickExport: boolean;
  reason?: string;
  containsInternalOutput: boolean;
}

const INTERNAL_MARKERS = [
  /\[(?:企业资料检索结果|知识检索结果|工具调用结果|TOOL_RESULT)\]/i,
  /\b(?:tool_name|tool_args|tool_result|trace_id|chunk_id)\s*[:：]/i,
  /\[EVID:[^\]]+\]/i,
  /```(?:json|tool|trace)[\s\S]*?```/i,
];

function plainLength(content: string) {
  return content
    .replace(/```[\s\S]*?```/g, '')
    .replace(/[#>*_`|\s]/g, '')
    .length;
}

export function assessDeliverableEligibility(
  content: string,
  originalRequest = '',
): DeliverableEligibility {
  const value = String(content || '').trim();
  const containsInternalOutput = INTERNAL_MARKERS.some((pattern) => pattern.test(value));
  const length = plainLength(value);
  const hasIntent = /(方案|报告|标书|分析|文档|文件|清单|总结|对比|建议|计划)/.test(
    `${originalRequest}\n${value.slice(0, 500)}`,
  );
  if (length < 40) {
    return {
      canCreateArtifact: false,
      canQuickExport: false,
      reason: '内容尚不足以生成成果',
      containsInternalOutput,
    };
  }
  return {
    canCreateArtifact: hasIntent || length >= 120,
    canQuickExport: length >= 120 && !containsInternalOutput,
    reason: containsInternalOutput ? '包含内部检索信息，将通过精品成果流程清洗后再交付' : undefined,
    containsInternalOutput,
  };
}

export function inferArtifactType(request: string, content: string) {
  const value = `${request}\n${content.slice(0, 1200)}`.toLowerCase();
  if (/(标书|投标|招标|tender)/.test(value)) return 'tender';
  if (/(竞品|竞争对手|横向对比|competitor)/.test(value)) return 'competitor_analysis';
  if (/(政策|法规|合规报告|policy)/.test(value)) return 'policy_brief';
  if (/(售后|维保|服务方案|校准方案)/.test(value)) return 'service_proposal';
  if (/(技术报告|验证报告|实验报告|分析报告)/.test(value)) return 'technical_report';
  return 'customer_solution';
}
