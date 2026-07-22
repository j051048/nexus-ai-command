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

const HIGH_VALUE_DELIVERABLE = /(?:客户|对外|正式|精品|完整|不少于|至少|约\s*\d+\s*字|\d{3,5}\s*字)?.*(?:方案|标书|投标|报告|竞品分析|政策解读|技术响应|解决方案|产品文案|Word|PDF)/i;

const DEFAULT_CHARACTER_COUNTS: Record<string, number> = {
  customer_solution: 3000,
  tender: 5000,
  competitor_analysis: 3000,
  policy_brief: 2200,
  service_proposal: 3000,
  technical_report: 3000,
};

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
  const highValueDeliverable = HIGH_VALUE_DELIVERABLE.test(`${originalRequest}\n${value.slice(0, 800)}`);
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
    canQuickExport: length >= 120 && !containsInternalOutput && !highValueDeliverable,
    reason: containsInternalOutput
      ? '包含内部检索信息，将通过精品成果流程清洗后再交付'
      : highValueDeliverable
        ? '方案与报告将重新检索资料、验收篇幅并专业排版后交付'
        : undefined,
    containsInternalOutput,
  };
}

export function inferTargetCharacterCount(request: string, artifactType: string) {
  const value = String(request || '');
  const direct = value.match(/(?:不少于|至少|达到|约|大约)?\s*(\d{3,5})\s*(?:字|汉字|字符)/);
  if (direct) return Math.min(12000, Math.max(600, Number(direct[1])));
  const thousands = value.match(/(?:不少于|至少|达到|约|大约)?\s*(\d+(?:\.\d+)?)\s*(?:千|k)\s*字/i);
  if (thousands) return Math.min(12000, Math.max(600, Math.round(Number(thousands[1]) * 1000)));
  const chinese = value.match(/(?:不少于|至少|达到|约|大约)?\s*([一两二三四五六八])千字/);
  if (chinese) {
    const values: Record<string, number> = { 一: 1000, 两: 2000, 二: 2000, 三: 3000, 四: 4000, 五: 5000, 六: 6000, 八: 8000 };
    return values[chinese[1]];
  }
  return DEFAULT_CHARACTER_COUNTS[artifactType] ?? 3000;
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
