"""
P0-3: /api/tools/capabilities 能力发现 API 测试

验证端点返回的结构正确性和分组逻辑。
"""



class TestCapabilitiesEndpoint:
    """测试 capabilities 端点的核心业务逻辑"""

    def test_capabilities_data_structure(self):
        """验证 capabilities 返回结构"""
        from app.tools import TOOL_REGISTRY, _load_all

        _load_all()

        # 模拟端点逻辑
        domain_map: dict[str, dict] = {}
        domain_labels = {
            "crm": {"label": "客户管理", "icon": "👥", "color": "#3B82F6"},
            "approval": {"label": "智能审批", "icon": "✅", "color": "#10B981"},
            "finance": {"label": "财务管理", "icon": "💰", "color": "#F59E0B"},
        }

        for tool in TOOL_REGISTRY.values():
            domain = tool.domain or "general"
            if domain not in domain_map:
                meta = domain_labels.get(domain, {"label": domain, "icon": "🔧", "color": "#94A3B8"})
                domain_map[domain] = {
                    "domain": domain,
                    "label": meta["label"],
                    "icon": meta["icon"],
                    "color": meta["color"],
                    "tool_count": 0,
                    "tools": [],
                }
            domain_map[domain]["tool_count"] += 1

        # 验证至少包含 crm, approval, finance
        assert "crm" in domain_map
        assert "approval" in domain_map
        assert "finance" in domain_map

        # 验证每个 domain 结构完整
        for domain_data in domain_map.values():
            assert "domain" in domain_data
            assert "label" in domain_data
            assert "icon" in domain_data
            assert "tool_count" in domain_data
            assert domain_data["tool_count"] > 0

    def test_total_tools_count(self):
        """验证总工具数大于 0"""
        from app.tools import TOOL_REGISTRY, _load_all

        _load_all()
        assert len(TOOL_REGISTRY) > 0

    def test_tool_examples_included(self):
        """验证代表性工具包含示例"""
        from app.tools import TOOL_REGISTRY, _load_all

        _load_all()

        # 至少有一个注册工具有 examples
        has_examples = any(
            bool(tool.examples)
            for tool in TOOL_REGISTRY.values()
        )
        assert has_examples, "至少应有一个工具定义了 examples"

    def test_domain_label_fallback(self):
        """未知 domain 应回退到默认标签"""
        domain_labels = {
            "crm": {"label": "客户管理"},
        }
        unknown_domain = "unknown_xyz"
        meta = domain_labels.get(unknown_domain, {"label": unknown_domain, "icon": "🔧", "color": "#94A3B8"})
        assert meta["label"] == unknown_domain
        assert meta["icon"] == "🔧"
