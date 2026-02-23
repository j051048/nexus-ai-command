"""
IM 平台互动消息卡片模板

根据不同 IM 平台（企微/钉钉/飞书）生成对应格式的互动消息卡片。
主要场景：
- 审批通知卡片（含批准/拒绝按钮）
- 通用通知卡片
"""

import logging

logger = logging.getLogger(__name__)


def approval_notification_card(
    platform: str,
    approval_id: str,
    approval_type: str,
    amount: float,
    requester_name: str,
    description: str,
    callback_url: str,
) -> dict:
    """
    生成审批通知卡片（含批准/拒绝按钮）。

    根据平台返回不同格式的卡片数据：
    - wecom: template_card (button_interaction 类型)
    - dingtalk: action_card (独立跳转多按钮)
    - feishu: interactive card (message card)

    Args:
        platform: 平台标识 (wecom/dingtalk/feishu)
        approval_id: 审批请求 ID
        approval_type: 审批类型（如 expense, purchase, travel）
        amount: 审批金额
        requester_name: 申请人姓名
        description: 审批说明
        callback_url: 按钮回调 URL 基地址

    Returns:
        对应平台格式的卡片数据 Dict
    """
    if platform == "wecom":
        return _wecom_approval_card(
            approval_id,
            approval_type,
            amount,
            requester_name,
            description,
            callback_url,
        )
    elif platform == "dingtalk":
        return _dingtalk_approval_card(
            approval_id,
            approval_type,
            amount,
            requester_name,
            description,
            callback_url,
        )
    elif platform == "feishu":
        return _feishu_approval_card(
            approval_id,
            approval_type,
            amount,
            requester_name,
            description,
            callback_url,
        )
    else:
        logger.warning(f"Unknown platform for card: {platform}")
        return {}


def general_notification_card(
    platform: str,
    title: str,
    content: str,
    url: str | None = None,
) -> dict:
    """
    生成通用通知卡片。

    Args:
        platform: 平台标识
        title: 通知标题
        content: 通知内容
        url: 可选的跳转链接

    Returns:
        对应平台格式的卡片数据 Dict
    """
    if platform == "wecom":
        return _wecom_general_card(title, content, url)
    elif platform == "dingtalk":
        return _dingtalk_general_card(title, content, url)
    elif platform == "feishu":
        return _feishu_general_card(title, content, url)
    else:
        logger.warning(f"Unknown platform for card: {platform}")
        return {}


# ── 企业微信卡片 ──────────────────────────────────────────────────


def _wecom_approval_card(
    approval_id: str,
    approval_type: str,
    amount: float,
    requester_name: str,
    description: str,
    callback_url: str,
) -> dict:
    """
    企微审批通知卡片 - button_interaction 类型。

    参考：https://developer.work.weixin.qq.com/document/path/96488
    """
    type_labels = {
        "expense": "费用报销",
        "purchase": "采购申请",
        "travel": "差旅申请",
        "leave": "请假申请",
    }

    return {
        "card_type": "button_interaction",
        "source": {
            "icon_url": "",
            "desc": "Nexus AI Command",
            "desc_color": 0,
        },
        "main_title": {
            "title": f"审批通知 - {type_labels.get(approval_type, approval_type)}",
        },
        "sub_title_text": description[:60] if description else "",
        "horizontal_content_list": [
            {"keyname": "申请人", "value": requester_name},
            {"keyname": "类型", "value": type_labels.get(approval_type, approval_type)},
            {"keyname": "金额", "value": f"¥{amount:,.2f}"},
        ],
        "task_id": approval_id,
        "button_list": [
            {
                "text": "批准",
                "style": 1,  # 绿色
                "key": f"approve_{approval_id}",
            },
            {
                "text": "拒绝",
                "style": 3,  # 红色
                "key": f"reject_{approval_id}",
            },
        ],
    }


def _wecom_general_card(title: str, content: str, url: str | None = None) -> dict:
    """企微通用通知卡片 - text_notice 类型"""
    card = {
        "card_type": "text_notice",
        "source": {
            "desc": "Nexus AI Command",
        },
        "main_title": {"title": title},
        "sub_title_text": content[:200],
    }
    if url:
        card["card_action"] = {
            "type": 1,
            "url": url,
        }
    return card


# ── 钉钉卡片 ────────────────────────────────────────────────────


def _dingtalk_approval_card(
    approval_id: str,
    approval_type: str,
    amount: float,
    requester_name: str,
    description: str,
    callback_url: str,
) -> dict:
    """
    钉钉审批通知 ActionCard - 独立跳转（多按钮）。

    参考：https://open.dingtalk.com/document/orgapp/message-types-and-data-format
    """
    type_labels = {
        "expense": "费用报销",
        "purchase": "采购申请",
        "travel": "差旅申请",
        "leave": "请假申请",
    }

    approve_url = f"{callback_url}?approval_id={approval_id}&action=approve"
    reject_url = f"{callback_url}?approval_id={approval_id}&action=reject"

    markdown_body = (
        f"### 审批通知 - {type_labels.get(approval_type, approval_type)}\n\n"
        f"**申请人：** {requester_name}\n\n"
        f"**金额：** ¥{amount:,.2f}\n\n"
        f"**说明：** {description[:100]}\n\n"
        f"---\n"
    )

    return {
        "title": f"审批通知 - {type_labels.get(approval_type, approval_type)}",
        "markdown": markdown_body,
        "btn_orientation": "1",  # 横向排列按钮
        "btn_json_list": [
            {"title": "批准", "action_url": approve_url},
            {"title": "拒绝", "action_url": reject_url},
        ],
    }


def _dingtalk_general_card(title: str, content: str, url: str | None = None) -> dict:
    """钉钉通用通知 ActionCard - 整体跳转"""
    card = {
        "title": title,
        "markdown": f"### {title}\n\n{content[:500]}",
        "btn_orientation": "0",
    }
    if url:
        card["single_title"] = "查看详情"
        card["single_url"] = url
    return card


# ── 飞书卡片 ────────────────────────────────────────────────────


def _feishu_approval_card(
    approval_id: str,
    approval_type: str,
    amount: float,
    requester_name: str,
    description: str,
    callback_url: str,
) -> dict:
    """
    飞书审批通知互动卡片（Interactive Message Card）。

    参考：https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/card-components
    """
    type_labels = {
        "expense": "费用报销",
        "purchase": "采购申请",
        "travel": "差旅申请",
        "leave": "请假申请",
    }

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"审批通知 - {type_labels.get(approval_type, approval_type)}",
            },
            "template": "blue",
        },
        "elements": [
            {
                "tag": "div",
                "fields": [
                    {
                        "is_short": True,
                        "text": {
                            "tag": "lark_md",
                            "content": f"**申请人：**\n{requester_name}",
                        },
                    },
                    {
                        "is_short": True,
                        "text": {
                            "tag": "lark_md",
                            "content": f"**金额：**\n¥{amount:,.2f}",
                        },
                    },
                ],
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**说明：**\n{description[:200]}",
                },
            },
            {"tag": "hr"},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "批准",
                        },
                        "type": "primary",
                        "value": {
                            "action": "approve",
                            "approval_id": approval_id,
                        },
                    },
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "拒绝",
                        },
                        "type": "danger",
                        "value": {
                            "action": "reject",
                            "approval_id": approval_id,
                        },
                    },
                ],
            },
        ],
    }


def _feishu_general_card(title: str, content: str, url: str | None = None) -> dict:
    """飞书通用通知卡片"""
    elements = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": content[:500],
            },
        },
    ]

    if url:
        elements.append({"tag": "hr"})
        elements.append(
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "查看详情",
                        },
                        "type": "default",
                        "url": url,
                    },
                ],
            }
        )

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": title,
            },
        },
        "elements": elements,
    }
