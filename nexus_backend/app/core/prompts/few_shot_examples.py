"""
Few-shot examples for scene-specific prompt injection.

Each scene has 1-2 high-quality example conversations that demonstrate
the expected response style, tool usage pattern, and output format.
Examples are kept concise (≤300 chars each) to minimize token overhead.
"""

# ─── Scene Examples ──────────────────────────────────────────────────────────

_EXAMPLES: dict[str, str] = {
    "general": """【参考对话风格】
用户: 早上好
助手: 早，今天有3条待审批、下午2点华东客户会议。需要先处理哪个？

用户: 你能做什么？
助手: 我能帮你处理请假报销、审批流转、客户跟进、数据报表、知识检索等日常事务。直接说需求就行。""",

    "approval": """【参考对话风格 — 审批场景】
用户: 5000以下的都批了
助手: [调用 smart_approve 工具，条件: amount<5000, action=approve]
已批准4笔：张三差旅报销¥3,200、李四办公采购¥1,800、王五交通费¥960、赵六快递费¥450。
剩余2笔超过¥5,000，需要单独审批。""",

    "crm": """【参考对话风格 — 客户场景】
用户: 华东区这个月跟进情况怎么样
助手: [调用 get_follow_ups + get_sales_pipeline 获取数据，整合后用 GenUI 展示]
华东区本月跟进**47次**，覆盖**23家**客户。重点关注：
- **水厂项目**（A类）：已报价，等回复，建议本周电话催一下
- **化工新客户**（B类）：首次拜访完成，反馈积极，下周安排技术交流

```gen-ui
{"component":"FunnelChart","props":{"stages":[{"label":"线索","value":45},{"label":"跟进中","value":23},{"label":"报价","value":8},{"label":"成交","value":3}],"title":"华东区本月销售漏斗"}}
```""",

    "data_query": """【参考对话风格 — 数据查询】
用户: 这个月业绩怎么样
助手: [调用 get_company_stats 获取数据]
本月销售额**¥428万**，完成率**78%**，同比增长**12.3%**。华东区贡献最大，占比42%。

```gen-ui
{"component":"StatCards","props":{"title":"本月经营概览","cards":[{"label":"销售额","value":4280000,"change":12.3,"unit":"元"},{"label":"完成率","value":78,"unit":"%"},{"label":"新客户","value":15,"change":25}]}}
```""",

    "clarify": """【参考对话风格 — 信息不足时主动追问】
用户: 帮我请假
助手: [调用 ask_user 工具]
请假需要确认几个信息：
1. **从哪天开始？**（比如明天、下周一）
2. **请几天？**
3. **假期类型？** A) 年假 B) 事假 C) 病假

用户: 帮我查一下那个客户
助手: [调用 ask_user 工具]
你说的是哪位客户？
A) **华东水厂** — 上周刚跟进过
B) **深圳光伏科技** — 本月新建线索
C) 其他客户，请告诉我名称""",

    "multi_step": """【参考对话风格 — 多步操作】
用户: 给华东水厂发个报价，顺便安排下周去拜访
助手: [调用 get_customer_detail 查客户信息 → 调用 generate_quotation_template 生成报价 → 调用 book_meeting 安排拜访]
两件事都安排好了：
1. **报价单**已生成，基于最新产品目录（ZY-200系列），总价¥86万。需要你确认后发送。
2. **拜访**已安排在下周三下午2点，地点：华东水厂（上海松江）。已同步到你的日历。""",

    "notification": """【参考对话风格 — 通知/提醒场景】
用户: 通知小王明天上午10点开会
助手: [调用 send_notification 工具, recipient_name="小王", content="明天上午10点开会"]
已通知小王，消息已发送。

用户: 帮我草拟一个会议通知
助手: [不调用工具，直接输出 EmailDraft 组件展示草稿供编辑]""",

    "oa_ops": """【参考对话风格 — OA操作场景】
用户: 帮我请明天一天事假，家里有事
助手: [调用 create_leave_request, leave_type="personal", start_date="2026-03-14", end_date="2026-03-14", reason="家里有事"]
已提交事假申请（3月14日，1天），等待主管审批。

用户: 约个明天下午3点的会，叫上销售部
助手: [调用 book_meeting, title="销售部会议", start_time="2026-03-14 15:00", participants=["销售部"]]
会议已预约：明天下午3点，已通知销售部。""",

    "asset_inventory": """【参考对话风格 — 资产/库存场景】
用户: 笔记本电脑还有多少库存
助手: [调用 list_inventory, keyword="笔记本电脑"]
当前笔记本电脑库存**12台**，其中ThinkPad T14 8台、MacBook Pro 4台。上月出库5台。""",

    "work_order": """【参考对话风格 — 工单场景】
用户: 3楼会议室空调坏了，报个修
助手: [调用 create_work_order, title="3楼会议室空调维修", type="maintenance", priority="normal"]
工单已创建（编号WO-20260313-001），已派给设备维护组，预计24小时内处理。""",

    "content_generation": """【参考对话风格 — 内容生成场景】
用户: 帮我写一篇关于FD-F1560食品安全检测仪的公众号推广软文，结合最近的食品安全热点
助手: [调用 generate_social_post, topic="FD-F1560食品安全检测仪+食品安全热点", platform="wechat", tone="promotional", product_name="FD-F1560"]
（工具内部会自动检索知识库获取产品参数和资料，生成完整长文）

用户: 写一篇3000字的行业白皮书
助手: [调用 query_knowledge_base 获取相关产品和技术资料 → 调用 generate_whitepaper 生成白皮书]
先从知识库收集技术参数和案例数据，再生成完整白皮书，确保内容有据可依。""",
}

# ─── Scene Code → Example Key Mapping ────────────────────────────────────────

_SCENE_EXAMPLE_MAP: dict[str, str] = {
    # Approval scenes
    "approval": "approval",
    "expense_claim": "approval",
    # CRM scenes
    "crm_followup": "crm",
    "sales_pipeline": "crm",
    "sales_enablement": "crm",
    # Leave/OA scenes
    "leave_request": "oa_ops",
    "attendance_check": "oa_ops",
    # Content/analysis scenes
    "content_creation": "content_generation",
    "content_generation": "content_generation",
    "tender_analysis": "multi_step",
    "proposal": "multi_step",
    # Data scenes
    "lead_generation": "data_query",
    "brand_monitoring": "data_query",
    # System admin
    "system_admin": "general",
}

# Intent keywords → example key
_INTENT_EXAMPLE_MAP: dict[str, str] = {
    "审批": "approval",
    "批了": "approval",
    "客户": "crm",
    "跟进": "crm",
    "业绩": "data_query",
    "数据": "data_query",
    "报表": "data_query",
    "统计": "data_query",
    "请假": "oa_ops",
    "报销": "clarify",
    "报价": "multi_step",
    "拜访": "multi_step",
    # Notification / messaging
    "通知": "notification",
    "提醒": "notification",
    "发消息": "notification",
    # Asset / Inventory
    "库存": "asset_inventory",
    "资产": "asset_inventory",
    "设备": "asset_inventory",
    # Work orders
    "工单": "work_order",
    "维修": "work_order",
    "报修": "work_order",
    # Content generation
    "软文": "content_generation",
    "文案": "content_generation",
    "白皮书": "content_generation",
    "推广文": "content_generation",
    "长文": "content_generation",
    "写作": "content_generation",
    "内容创作": "content_generation",
}


def get_few_shot_examples(scene_code: str = "", intent_summary: str = "") -> str:
    """Get the most relevant few-shot example for the current context.

    Resolution order:
      1. scene_code direct match
      2. Intent keyword match
      3. 'general' fallback (always returned so LLM has style reference)

    Returns a formatted string ready to append to the system prompt.
    """
    # 1. Scene code match
    if scene_code and scene_code in _SCENE_EXAMPLE_MAP:
        key = _SCENE_EXAMPLE_MAP[scene_code]
        return _EXAMPLES.get(key, _EXAMPLES["general"])

    # 2. Intent keyword match
    if intent_summary:
        for keyword, key in _INTENT_EXAMPLE_MAP.items():
            if keyword in intent_summary:
                return _EXAMPLES.get(key, _EXAMPLES["general"])

    # 3. Fallback
    return _EXAMPLES["general"]
