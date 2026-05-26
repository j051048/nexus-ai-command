import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const out = path.join(root, "nexus_backend", "tests", "production_proof", "fixtures", "agent_eval_cases_200.json");

const templates = [
  ["crm_followup", "critical", "CRM", "客户{n}已经{d}天没有跟进，请生成下一步行动。"],
  ["crm_followup", "high", "CRM", "Summarize the next best action for lead {n} after a delayed visit."],
  ["approval_decision", "critical", "Approval", "报销单{n}金额偏高，请判断是否需要老板复核。"],
  ["approval_decision", "high", "Approval", "Approve or reject reimbursement request {n} with risk notes."],
  ["tender_support", "critical", "Tender", "招标文件{n}要求评分标准，帮我提取技术扣分风险。"],
  ["tender_support", "high", "Tender", "RFP {n} needs a compliance checklist and score estimate."],
  ["battlecard", "high", "Competitive", "对比 Thermo Fisher 和我们的质谱方案，生成战卡{n}。"],
  ["battlecard", "medium", "Competitive", "Compare Agilent competitor claims against our product for case {n}."],
  ["renewal_or_contract", "critical", "Contract", "合同{n}还有60天到期，请生成续签计划。"],
  ["renewal_or_contract", "high", "Contract", "Customer contract {n} expires soon; prepare renewal risk summary."],
  ["knowledge_search", "medium", "Knowledge", "从知识库找出关于液相色谱维护的标准答案{n}。"],
  ["vmd_campaign", "high", "VMD", "为科学仪器展会线索{n}设计一轮虚拟营销部跟进。"],
  ["finance_roi", "medium", "ROI", "计算本周 AI 自动化为团队节省了多少时间，样本{n}。"],
  ["risk_alert", "high", "Risk", "发现客户{n}连续30天无互动，请触发风险预警。"],
  ["general_assistant", "medium", "General", "帮我把今天的客户会议纪要整理成三条行动项{n}。"],
];

const cases = [];
for (let i = 0; i < 210; i += 1) {
  const [expected_intent, criticality, dimension, template] = templates[i % templates.length];
  const text = template.replaceAll("{n}", String(i + 1)).replaceAll("{d}", String(14 + (i % 45)));
  cases.push({
    id: `agent-eval-${String(i + 1).padStart(3, "0")}`,
    dimension,
    criticality,
    text,
    expected_intent,
    expected_tools: expected_intent === "general_assistant" ? [] : [`${expected_intent}_tool`],
    assertions: [
      "routes_to_expected_intent",
      "respects_tenant_context",
      criticality === "critical" ? "requires_high_confidence_or_handoff" : "allows_standard_confidence",
    ],
  });
}

fs.writeFileSync(out, `${JSON.stringify(cases, null, 2)}\n`, "utf8");
console.log(`Wrote ${cases.length} eval cases to ${path.relative(root, out)}`);
