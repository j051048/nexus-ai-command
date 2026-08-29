"""
Item 11: API Documentation Enhancement
API 文档增强配置 - 自定义 Swagger UI 和 OpenAPI 元数据。

提供:
- 增强版 API 分组描述
- 请求/响应示例
- Swagger UI 自定义配置
- OpenAPI schema 增强工具
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ==================== Swagger UI 配置 ====================

SWAGGER_UI_CONFIG = {
    "docExpansion": "list",
    "defaultModelsExpandDepth": 3,
    "filter": True,
    "syntaxHighlight.theme": "monokai",
    "displayRequestDuration": True,
    "tryItOutEnabled": True,
    "persistAuthorization": True,
    "showExtensions": True,
    "showCommonExtensions": True,
    "deepLinking": True,
}


# ==================== API 分组描述 ====================

API_TAGS_METADATA: list[dict[str, Any]] = [
    {
        "name": "Chat",
        "description": (
            "**AI 对话和会话管理**\n\n"
            "基于 LangGraph 的多 Agent 对话系统，支持:\n"
            "- 多轮对话（含上下文保持）\n"
            "- 流式输出 (SSE)\n"
            "- 工具调用 (Tool Calling)\n"
            "- 知识库检索增强生成 (RAG)\n"
            "- 对话历史管理"
        ),
    },
    {
        "name": "Approval",
        "description": (
            "**智能审批流程管理**\n\n"
            "多级审批链系统，支持:\n"
            "- AI 自动审批/人工审批分流\n"
            "- 可视化工作流引擎\n"
            "- 自定义表单模板\n"
            "- 审批超时自动升级"
        ),
    },
    {
        "name": "Workflows",
        "description": (
            "**可视化流程设计器**\n\n"
            "拖拽式工作流编辑器后端 API:\n"
            "- 工作流 CRUD\n"
            "- 步骤定义与条件分支\n"
            "- 画布布局持久化\n"
            "- 工作流启用/禁用"
        ),
    },
    {
        "name": "Form Schemas",
        "description": (
            "**自定义表单引擎**\n\n"
            "动态表单模板管理:\n"
            "- JSON Schema 定义表单字段\n"
            "- 字段校验规则\n"
            "- 与审批类型绑定\n"
            "- 版本管理"
        ),
    },
    {
        "name": "Documents",
        "description": (
            "**文档上传和知识库 RAG**\n\n"
            "企业知识库管理:\n"
            "- 文档上传（PDF/Word/TXT）\n"
            "- 向量化存储\n"
            "- 混合检索（向量 + 关键词 + 重排序）\n"
            "- QA 对自动生成"
        ),
    },
    {
        "name": "Permissions",
        "description": (
            "**ABAC 权限管理**\n\n"
            "基于属性的访问控制:\n"
            "- 角色权限查询\n"
            "- 单项权限检查\n"
            "- 条件约束评估（同部门、资源所有者等）\n"
            "- 角色层级继承"
        ),
    },
    {
        "name": "Data Transfer",
        "description": (
            "**数据导入/导出**\n\n"
            "批量数据传输:\n"
            "- CSV 数据导出（审批/考勤/销售/员工/客户）\n"
            "- 导入模板下载\n"
            "- CSV 批量导入（含预验证）\n"
            "- 自动编码检测（UTF-8/GBK）"
        ),
    },
    {
        "name": "Push Notifications",
        "description": (
            "**Web Push 推送通知**\n\n"
            "浏览器推送服务:\n"
            "- VAPID 密钥管理\n"
            "- 订阅注册/取消\n"
            "- 单播/广播推送\n"
            "- 审批事件自动通知"
        ),
    },
    {
        "name": "Import",
        "description": (
            "**基础数据导入**\n\n员工和客户数据的文件上传导入:\n- CSV/Excel 文件解析\n- 数据预览\n- 增量/全量导入模式"
        ),
    },
    {
        "name": "Billing",
        "description": (
            "**订阅计划和计费**\n\n"
            "SaaS 多租户计费系统:\n"
            "- 订阅计划管理（Free/Pro/Enterprise）\n"
            "- 试用期管理\n"
            "- 使用量统计和配额\n"
            "- 账单和发票"
        ),
    },
    {
        "name": "Performance",
        "description": (
            "**绩效管理**\n\n员工绩效评估:\n- 考核指标定义\n- 团队排名\n- AI 辅助绩效分析"
        ),
    },
    {
        "name": "Incentive",
        "description": (
            "**激励钱包**\n\n员工积分和奖金管理:\n- 积分发放/扣减\n- 奖金池管理\n- 排行榜"
        ),
    },
    {
        "name": "Organization",
        "description": (
            "**组织管理**\n\n多租户组织管理:\n- 组织信息维护\n- 部门结构\n- 成员管理"
        ),
    },
    {
        "name": "Profile",
        "description": (
            "**个人资料**\n\n用户个人信息管理:\n- 资料查看和编辑\n- 头像上传\n- 偏好设置"
        ),
    },
    {
        "name": "Projects",
        "description": (
            "**项目管理**\n\n项目和任务追踪:\n- 项目 CRUD\n- 任务分配\n- 进度跟踪"
        ),
    },
    {
        "name": "Webhooks",
        "description": (
            "**Webhook 订阅和投递**\n\n外部系统集成:\n- Webhook 端点注册\n- 事件订阅\n- 投递日志和重试"
        ),
    },
    {
        "name": "OAuth",
        "description": (
            "**OAuth 2.0 授权服务**\n\n第三方应用授权:\n- 授权码流程\n- Access Token 管理\n- Scope 权限控制"
        ),
    },
    {
        "name": "Compliance",
        "description": (
            "**合规管理**\n\n数据合规和安全:\n- 内容安全审核\n- 数据脱敏\n- 合规报告"
        ),
    },
    {
        "name": "Usage",
        "description": (
            "**使用量统计**\n\nAPI 调用和资源使用统计:\n- Token 使用量\n- API 调用次数\n- 存储使用量"
        ),
    },
    {
        "name": "MCP Server",
        "description": (
            "**Model Context Protocol**\n\nAI 模型互操作工具注册:\n- 工具列表暴露\n- 工具执行代理\n- Schema 发现"
        ),
    },
    {
        "name": "Robot/RPA",
        "description": (
            "**机器人/RPA 接口**\n\n设备控制和 RPA 指令:\n- 设备注册\n- 指令下发\n- 状态查询"
        ),
    },
    {
        "name": "Kingdee",
        "description": (
            "**金蝶 ERP 集成**\n\n通过配置的金蝶 HTTP 网关对接真实业务系统:\n- 库存查询\n- 薪资同步\n- 缺少凭据时生产环境 fail-closed"
        ),
    },
    {
        "name": "QA Pairs",
        "description": (
            "**QA 问答对管理**\n\n知识库问答对:\n- QA 对 CRUD\n- 批量导入\n- 与文档关联"
        ),
    },
    {
        "name": "API Docs",
        "description": (
            "**API 文档增强**\n\nAPI 文档和元数据:\n- 增强版 OpenAPI spec\n- 端点统计\n- 变更日志"
        ),
    },
]


# ==================== 示例请求/响应 ====================

APPROVAL_REQUEST_EXAMPLE = {
    "type": "expense",
    "amount": 3500.00,
    "details": "报销上周客户拜访餐费",
    "form_data": {
        "expense_category": "餐饮",
        "receipt_count": 3,
        "business_purpose": "客户关系维护",
    },
}

APPROVAL_RESPONSE_EXAMPLE = {
    "success": True,
    "data": {
        "request_id": "uuid-1234-5678",
        "status": "pending",
        "chain_result": {
            "auto_approved": False,
            "assigned_to": "manager-uuid",
            "step": 1,
        },
    },
    "message": "审批请求已提交",
}

CHAT_REQUEST_EXAMPLE = {
    "message": "帮我查看本月销售排名前三的员工",
    "session_id": "session-uuid-1234",
    "agent_type": "sales",
    "stream": True,
}

CHAT_RESPONSE_EXAMPLE = {
    "success": True,
    "data": {
        "response": "本月销售排名前三的员工是:\n1. 张三 - ¥150,000\n2. 李四 - ¥120,000\n3. 王五 - ¥95,000",
        "session_id": "session-uuid-1234",
        "tool_calls": [
            {
                "tool": "query_sales_ranking",
                "result": "success",
            }
        ],
    },
}

WORKFLOW_CREATE_EXAMPLE = {
    "name": "大额报销审批流",
    "description": "超过5000元的报销需经过三级审批",
    "applies_to": ["expense"],
    "steps": [
        {
            "id": "step-1",
            "type": "approval",
            "name": "直属主管审批",
            "approver_type": "direct_manager",
        },
        {
            "id": "step-2",
            "type": "condition",
            "name": "金额判断",
            "condition": {"field": "amount", "operator": "gt", "value": 10000},
        },
        {
            "id": "step-3",
            "type": "approval",
            "name": "财务总监审批",
            "approver_role": "boss",
        },
    ],
}

PERMISSION_CHECK_EXAMPLE = {
    "success": True,
    "data": {
        "permission": "approval.approve",
        "granted": True,
        "reason": "权限通过",
        "evaluated_conditions": [
            {"condition": "is_approver", "result": True},
        ],
    },
}

DATA_EXPORT_REQUEST_EXAMPLE = {
    "filters": {"status": "approved"},
    "date_from": "2024-01-01",
    "date_to": "2024-12-31",
}

DATA_IMPORT_VALIDATE_EXAMPLE = {
    "import_type": "employees",
    "csv_content": "姓名,邮箱,部门,角色,手机号\n张三,zhangsan@example.com,技术部,employee,13800138001",
}


# ==================== API 版本和变更日志 ====================

API_VERSION = "2.0.0"

API_CHANGELOG: list[dict[str, Any]] = [
    {
        "version": "2.0.0",
        "date": "2025-01-15",
        "changes": [
            "新增 ABAC 权限管理 API",
            "新增数据导入/导出增强 API",
            "新增 API 文档增强端点",
            "新增 Web Push 推送通知",
            "升级 LangGraph Agent 架构",
            "新增可视化工作流引擎",
            "新增自定义表单引擎",
        ],
    },
    {
        "version": "1.5.0",
        "date": "2024-10-01",
        "changes": [
            "新增多租户支持",
            "新增 OAuth 2.0 授权服务",
            "新增 Webhook 订阅系统",
            "新增计费和订阅管理",
        ],
    },
    {
        "version": "1.0.0",
        "date": "2024-06-01",
        "changes": [
            "初始发布",
            "AI 对话（多 Agent）",
            "审批系统",
            "知识库 RAG",
            "销售管理",
        ],
    },
]


# ==================== 工具函数 ====================


def get_enhanced_openapi_description() -> str:
    """生成增强版 OpenAPI 描述文本"""
    return (
        "# Project Nexus Backend API\n\n"
        "AI 驱动的企业低代码后端平台。\n\n"
        "## 核心能力\n"
        "- **AI 对话**: LangGraph 多 Agent 对话系统，支持流式输出和工具调用\n"
        "- **智能审批**: 多级审批链 + AI 自动决策\n"
        "- **知识库**: RAG 混合检索（向量 + 关键词 + 重排序）\n"
        "- **工作流**: 可视化拖拽式流程设计器\n"
        "- **表单引擎**: JSON Schema 驱动的动态表单\n"
        "- **权限管理**: ABAC 基于属性的访问控制\n"
        "- **多租户**: Row Level Security + 按组织隔离\n\n"
        "## 认证方式\n"
        "所有 API（除 `/health`、`/docs`）需要 Bearer JWT Token。\n"
        "Token 通过 Supabase Auth 获取。\n\n"
        "```\n"
        "Authorization: Bearer <your-jwt-token>\n"
        "```\n\n"
        "## 错误格式\n"
        "```json\n"
        '{\n  "success": false,\n  "error": {\n'
        '    "code": "AUTH_PERMISSION_DENIED",\n'
        '    "message": "权限不足"\n  }\n}\n'
        "```\n\n"
        "## 成功格式\n"
        "```json\n"
        '{\n  "success": true,\n  "data": { ... },\n'
        '  "message": "操作成功"\n}\n'
        "```\n"
    )


def get_endpoint_stats(app) -> dict[str, Any]:
    """获取 API 端点统计信息"""
    from app.core.route_introspection import iter_effective_routes

    stats = {
        "total_routes": 0,
        "methods": {},
        "tags": {},
    }

    for route in iter_effective_routes(app.routes):
        if hasattr(route, "methods"):
            stats["total_routes"] += 1
            for method in route.methods:
                stats["methods"][method] = stats["methods"].get(method, 0) + 1

            if hasattr(route, "tags"):
                for tag in route.tags:
                    stats["tags"][tag] = stats["tags"].get(tag, 0) + 1

    return stats


def get_all_examples() -> dict[str, Any]:
    """获取所有 API 示例"""
    return {
        "approval_request": APPROVAL_REQUEST_EXAMPLE,
        "approval_response": APPROVAL_RESPONSE_EXAMPLE,
        "chat_request": CHAT_REQUEST_EXAMPLE,
        "chat_response": CHAT_RESPONSE_EXAMPLE,
        "workflow_create": WORKFLOW_CREATE_EXAMPLE,
        "permission_check": PERMISSION_CHECK_EXAMPLE,
        "data_export_request": DATA_EXPORT_REQUEST_EXAMPLE,
        "data_import_validate": DATA_IMPORT_VALIDATE_EXAMPLE,
    }
