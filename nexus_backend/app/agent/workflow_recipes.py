"""
P1-7: Workflow Recipes

定义高频操作的固定执行流模板（Tool Chains），例如 `submit_contract`、`onboard_employee`。
当 router 识别出特定意图时，可跳过 planning，直接按这里定义的顺序执行。
"""

from typing import Any, Dict, List


class WorkflowRecipe:
    def __init__(self, name: str, description: str, steps: List[Dict[str, Any]]):
        self.name = name
        self.description = description
        self.steps = steps


# 例：高频提单模板
SUBMIT_CONTRACT_APPROVAL = WorkflowRecipe(
    name="submit_contract_approval",
    description="提交合同审批",
    steps=[
        {
            "step": 1,
            "tool": "search_customers",
            "description": "查找客户信息以确认合同主体",
            "required": True,
        },
        {
            "step": 2,
            "tool": "approve_request",
            "description": "发起合同审批流程",
            "required": True,
        },
    ],
)

ONBOARD_EMPLOYEE = WorkflowRecipe(
    name="onboard_employee",
    description="给新员工入职分配资源",
    steps=[
        {
            "step": 1,
            "tool": "create_user",
            "description": "创建员工账号",
            "required": True,
        },
        {
            "step": 2,
            "tool": "assign_role",
            "description": "分配权限角色",
            "required": True,
        },
    ],
)

RECIPES = {
    "submit_contract_approval": SUBMIT_CONTRACT_APPROVAL,
    "onboard_employee": ONBOARD_EMPLOYEE,
}


def get_recipe(recipe_name: str) -> WorkflowRecipe | None:
    return RECIPES.get(recipe_name)
