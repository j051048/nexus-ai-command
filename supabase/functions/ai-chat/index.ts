import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const SYSTEM_PROMPT = `你是 Project Nexus 的 AI 指挥官，一个专业的企业级销售管理助手。你的职责包括：

## 角色定位
- @销售指挥官：提供销售策略、线索分析、商机建议
- @绩效教练：分析绩效数据、提供改进建议、激励员工
- @审批管家：处理审批请求、解析自然语言申请、自动判断合规性
- @知识助手：提供产品知识、竞品对比、技术参数

## 模拟数据背景
你管理的是一家精密科研仪器创业公司的销售团队。主要产品包括：
- 高精度光谱仪（价格 50-200万）
- 示波器系列（价格 5000-50000）
- 电子显微镜（价格 100-500万）

## 销售团队数据
- 王晓明：绩效95分，本周冠军，擅长高校客户
- 刘芳：绩效91分，第二名，擅长科研院所
- 张明（当前用户）：绩效87分，第三名，正在追赶
- 陈伟：绩效82分，需要激励
- 李娜：绩效78分，新人潜力股

## 重要商机
- 张教授（北大物理系）：对光谱仪感兴趣，赢率78%，建议今日跟进
- 李博士（清华化学系）：报价已发5天，需确认
- 王主任（中科院物理所）：需求明确，可安排演示

## 审批规则
- 出差预算：一线城市 3000元/天，二线 2000元/天
- 采购：1万以下自动通过，1-5万需主管审批，5万以上需老板
- 报销：餐饮单次300以内自动通过

## 激励规则
- 新客户首次成单：+500元即时奖金
- 商机推进至技术验证：+300元
- 通话质量评分90+：+200元
- 连续5日跟进达标（每日≥3线索）：+200元
- 月度排行前三：额外红包

## 回复风格
- 专业但友好，像一个资深销售教练
- 使用emoji增加亲和力
- 数据驱动，给出具体建议
- 主动推送相关信息和下一步行动
- 如涉及审批，明确说明是"模拟执行"还是需要后端确认

请根据用户的问题，提供专业、具体、可操作的建议。`;

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { messages, agent } = await req.json();
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");

    if (!LOVABLE_API_KEY) {
      throw new Error("LOVABLE_API_KEY is not configured");
    }

    // Build the system prompt based on agent
    let agentContext = "";
    if (agent) {
      switch (agent) {
        case "@销售指挥官":
          agentContext = "\n\n当前角色：销售指挥官 - 专注于销售策略、线索分析和商机建议。";
          break;
        case "@绩效教练":
          agentContext = "\n\n当前角色：绩效教练 - 专注于绩效分析、激励建议和个人成长。";
          break;
        case "@审批管家":
          agentContext = "\n\n当前角色：审批管家 - 专注于审批处理、费用管控和流程优化。";
          break;
        case "@知识助手":
          agentContext = "\n\n当前角色：知识助手 - 专注于产品知识、竞品对比和技术支持。";
          break;
      }
    }

    const response = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${LOVABLE_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "google/gemini-3-flash-preview",
        messages: [
          { role: "system", content: SYSTEM_PROMPT + agentContext },
          ...messages,
        ],
        stream: true,
      }),
    });

    if (!response.ok) {
      if (response.status === 429) {
        return new Response(
          JSON.stringify({ error: "请求过于频繁，请稍后再试。" }),
          { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      if (response.status === 402) {
        return new Response(
          JSON.stringify({ error: "AI 额度已用完，请充值后继续使用。" }),
          { status: 402, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
      const errorText = await response.text();
      console.error("AI gateway error:", response.status, errorText);
      return new Response(
        JSON.stringify({ error: "AI 服务暂时不可用，请稍后再试。" }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    return new Response(response.body, {
      headers: { ...corsHeaders, "Content-Type": "text/event-stream" },
    });
  } catch (e) {
    console.error("AI chat error:", e);
    return new Response(
      JSON.stringify({ error: e instanceof Error ? e.message : "Unknown error" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
