# AI Assistant 固定 UUID
AI_ASSISTANT_ID = "00000000-0000-0000-0000-000000000001"

# P0 Security Fix #1: Maximum batch size for approvals
MAX_BATCH_SIZE = 10

# ── 审批级别到角色的映射 ──
_LEVEL_ROLE_MAP = {
    "manager": ["manager"],
    "director": ["manager", "director"],
    "cfo": ["manager", "founder"],
    "ceo": ["founder"],
    "board": ["founder"],
    "founder": ["founder"],
}

_LEVEL_NAMES = {
    "manager": "部门经理",
    "director": "总监",
    "cfo": "财务总监",
    "ceo": "总经理/CEO",
    "board": "董事会",
    "founder": "老板",
}
