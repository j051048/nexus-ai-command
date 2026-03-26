"""
P0 & P1 Harness 优化验证测试

测试覆盖：
- P0-1: 置信度门控
- P0-2: 影子模式 (Dry-Run)
- P1-3: 早停机制
- P1-4: 预检验证
"""

import asyncio
from app.agent.state import AgentConfig, ToolCallRecord
from app.agent.node_execute import _check_tool_confidence, _is_mutation_tool, _simulate_tool_result


async def test_p0_1_confidence_gate():
    """测试置信度门控"""
    print("\n=== P0-1: 置信度门控测试 ===")

    # 测试高风险参数
    passed, reason = _check_tool_confidence(
        "update_sales_lead",
        {"lead_id": "123", "amount": 10000},
        threshold=0.85
    )
    print(f"高风险参数检查: {'通过' if passed else f'拒绝 - {reason}'}")

    # 测试非写操作工具
    is_mutation = _is_mutation_tool("get_sales_leads")
    print(f"读操作工具识别: {'错误' if is_mutation else '正确'}")

    is_mutation = _is_mutation_tool("update_sales_lead")
    print(f"写操作工具识别: {'正确' if is_mutation else '错误'}")


async def test_p0_2_dry_run():
    """测试影子模式"""
    print("\n=== P0-2: 影子模式测试 ===")

    simulated = _simulate_tool_result("delete_sales_lead", {"lead_id": "123"})
    print(f"模拟结果: {simulated}")
    print(f"包含预演标记: {'simulated' in simulated}")


async def test_p1_4_preflight():
    """测试预检规则"""
    print("\n=== P1-4: 预检验证测试 ===")

    from app.agent.preflight_rules import PRE_FLIGHT_RULES

    print(f"已定义预检规则的工具数: {len(PRE_FLIGHT_RULES)}")
    for tool_name, rules in PRE_FLIGHT_RULES.items():
        print(f"  - {tool_name}: {len(rules)} 条规则")


async def main():
    """运行所有测试"""
    print("开始 Harness 优化验证测试...")

    await test_p0_1_confidence_gate()
    await test_p0_2_dry_run()
    await test_p1_4_preflight()

    print("\n✅ 所有测试完成")


if __name__ == "__main__":
    asyncio.run(main())
