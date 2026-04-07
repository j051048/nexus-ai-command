"""Agent 测试"""
from app.agent.tool_dependencies import tool_dependency_manager


def test_resolve_execution_order():
    order = tool_dependency_manager.resolve_execution_order(["send_invoice"])
    assert "create_order" in order
    assert order.index("create_order") < order.index("send_invoice")

def test_no_dependencies():
    order = tool_dependency_manager.resolve_execution_order(["get_customer"])
    assert order == ["get_customer"]
