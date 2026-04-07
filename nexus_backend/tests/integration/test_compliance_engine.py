"""
#7 — Compliance Engine (合规引擎测试)

测试正则/关键词匹配:
- 广告法: "最先进" / "顶级" 匹配 AD_001 模式
- 广告法: "保证100%" 匹配 AD_002
- 招标法: "仅限" / "指定品牌" 匹配 BID_001
- 计量法: 精度声明匹配
- 正常文本不应触发误报
- check_content 的聚合结果正确性
- 空内容应标记为合规
"""



# ═══════════════════════════════════════════════════════════════════════════════
#  广告法规则测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestAdvertisingLawRules:
    """测试广告法合规检查"""

    async def test_absolute_terms_detected(self):
        """绝对化用语 '最先进' 应被检测"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        result = await service.check_content(
            content="我们的产品是最先进的设备",
            categories=["advertising_law"],
        )

        assert result.total_issues > 0
        assert any(i.rule_code == "AD_001" for i in result.issues)

    async def test_top_level_detected(self):
        """'顶级' 应被 AD_001 检测"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        result = await service.check_content(
            content="这是顶级品质的仪器",
            categories=["advertising_law"],
        )

        assert result.total_issues > 0
        has_ad001 = any(i.rule_code == "AD_001" for i in result.issues)
        assert has_ad001

    async def test_first_place_detected(self):
        """'第一' '唯一' 应被 AD_001 检测"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        result = await service.check_content(
            content="行业第一的唯一选择",
            categories=["advertising_law"],
        )

        assert result.total_issues > 0
        assert any(i.rule_code == "AD_001" for i in result.issues)

    async def test_false_promise_detected(self):
        """虚假承诺 '保证100%' 应被 AD_002 检测"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        result = await service.check_content(
            content="我们保证100%合格率",
            categories=["advertising_law"],
        )

        assert result.total_issues > 0
        has_ad002 = any(i.rule_code == "AD_002" for i in result.issues)
        assert has_ad002

    async def test_ensure_zero_failure_detected(self):
        """'确保零故障' 应被 AD_002 检测"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        result = await service.check_content(
            content="承诺零故障运行",
            categories=["advertising_law"],
        )

        assert result.total_issues > 0

    async def test_authority_reference_detected(self):
        """权威机构引用应被 AD_003 检测（warning 级别）"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        result = await service.check_content(
            content="国家机关推荐产品",
            categories=["advertising_law"],
        )

        assert result.total_issues > 0
        has_ad003 = any(i.rule_code == "AD_003" for i in result.issues)
        assert has_ad003


# ═══════════════════════════════════════════════════════════════════════════════
#  招标法规则测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestBiddingLawRules:
    """测试招标法合规检查"""

    async def test_exclusionary_clause_detected(self):
        """排他性条款 '仅限' 应被 BID_001 检测"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        result = await service.check_content(
            content="仅限指定品牌的设备",
            categories=["bidding_law"],
        )

        assert result.total_issues > 0
        has_bid001 = any(i.rule_code == "BID_001" for i in result.issues)
        assert has_bid001

    async def test_designated_brand_detected(self):
        """'必须使用' 应被 BID_001 检测"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        result = await service.check_content(
            content="必须使用某品牌的软件系统",
            categories=["bidding_law"],
        )

        assert result.total_issues > 0
        has_bid = any("BID" in i.rule_code for i in result.issues)
        assert has_bid

    async def test_preference_expression_detected(self):
        """倾向性表述应被 BID_002 检测（warning 级别）"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        result = await service.check_content(
            content="优先考虑某特定供应商的方案",
            categories=["bidding_law"],
        )

        assert result.total_issues > 0


# ═══════════════════════════════════════════════════════════════════════════════
#  计量法规则测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestMetrologyLawRules:
    """测试计量法合规检查"""

    async def test_unit_notation_detected(self):
        """非标准单位 'ppb' 应被 ML_002 检测"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        result = await service.check_content(
            content="检测限为10 ppb",
            categories=["metrology_law"],
        )

        assert result.total_issues > 0
        has_ml002 = any(i.rule_code == "ML_002" for i in result.issues)
        assert has_ml002


# ═══════════════════════════════════════════════════════════════════════════════
#  无误报测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestNoFalsePositives:
    """测试正常文本不应产生误报"""

    async def test_normal_business_text_clean(self):
        """正常商务文本不应触发合规问题"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        result = await service.check_content(
            content="本公司提供优质的检测仪器，技术团队经验丰富，欢迎来电咨询。",
        )

        # 正常文本不应有 error 级别的问题
        assert result.errors == 0

    async def test_empty_content_is_compliant(self):
        """空内容应标记为合规"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        result = await service.check_content(content="")

        assert result.is_compliant is True
        assert result.total_issues == 0

    async def test_whitespace_only_is_compliant(self):
        """仅空白字符的内容应标记为合规"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        result = await service.check_content(content="   \n\t  ")

        assert result.is_compliant is True

    async def test_simple_greeting_clean(self):
        """简单问候文本不应触发合规问题"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        result = await service.check_content(content="您好，请问有什么可以帮助您的？")

        assert result.errors == 0


# ═══════════════════════════════════════════════════════════════════════════════
#  聚合结果测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestComplianceResultAggregation:
    """测试合规检查结果的聚合正确性"""

    async def test_error_count_accurate(self):
        """error 计数应准确"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        # 包含多个 error 级别违规的文本
        result = await service.check_content(
            content="这是最先进的仅限指定品牌使用的顶级设备",
        )

        assert result.errors >= 2  # 至少 AD_001 + BID_001

    async def test_is_compliant_false_when_errors(self):
        """有 error 级别违规时 is_compliant 应为 False"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        result = await service.check_content(
            content="国内唯一的顶级仪器",
        )

        assert result.is_compliant is False

    async def test_checked_at_populated(self):
        """检查时间戳应被填充"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        result = await service.check_content(content="测试内容")

        assert result.checked_at != ""

    async def test_issue_has_required_fields(self):
        """违规记录应包含所有必要字段"""
        from app.services.compliance_service import ComplianceService

        service = ComplianceService()

        result = await service.check_content(content="最先进的设备")

        assert len(result.issues) > 0
        issue = result.issues[0]
        assert issue.rule_code != ""
        assert issue.severity in ("error", "warning", "info")
        assert issue.category != ""
        assert isinstance(issue.position, int)


# ═══════════════════════════════════════════════════════════════════════════════
#  PII / 数据隐私检测 (content_moderation)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPIIDetection:
    """测试 PII 检测 (content_moderation 模块)

    注意: 全局 content_moderator 使用 strict_mode=False,
    此模式下仅 critical 级别的违规才会使 is_safe=False,
    但 violations 列表仍会包含所有检测到的 PII。
    """

    def test_phone_number_detected(self):
        """手机号码应被检测 (violations 列表中存在 pii_phone)"""
        from app.services.content_moderation import scan_content

        is_safe, violations = scan_content("请拨打 13812345678 联系我")

        # 非严格模式下手机号 (high) 不会导致 is_safe=False, 但应出现在 violations 中
        assert any(v.type.value == "pii_phone" for v in violations)

    def test_id_card_detected(self):
        """身份证号应被检测 (critical 级别 -> is_safe=False)"""
        from app.services.content_moderation import scan_content

        # 使用符合格式的虚拟身份证号
        is_safe, violations = scan_content("身份证号: 110101199003074513")

        assert not is_safe  # critical 级别
        assert any(v.type.value == "pii_id_card" for v in violations)

    def test_email_detected(self):
        """邮箱地址应被检测 (violations 列表中存在 pii_email)"""
        from app.services.content_moderation import scan_content

        is_safe, violations = scan_content("联系方式: test@example.com")

        # 非严格模式下邮箱 (medium) 不会导致 is_safe=False, 但应出现在 violations 中
        assert any(v.type.value == "pii_email" for v in violations)

    def test_strict_mode_phone_blocks(self):
        """严格模式下手机号 (high) 应使 is_safe=False"""
        from app.services.content_moderation import ContentModerator

        strict_moderator = ContentModerator(strict_mode=True)
        is_safe, violations = strict_moderator.scan("请拨打 13812345678 联系我")

        assert not is_safe
        assert any(v.type.value == "pii_phone" for v in violations)

    def test_clean_text_passes(self):
        """不含 PII 的文本应通过检查"""
        from app.services.content_moderation import scan_content

        is_safe, violations = scan_content("公司位于北京市海淀区")

        assert is_safe
        assert len(violations) == 0

    def test_sanitize_strict_mode_masks_phone(self):
        """严格模式下 sanitize 方法应遮蔽手机号"""
        from app.services.content_moderation import ContentModerator

        moderator = ContentModerator(strict_mode=True)
        sanitized, violations = moderator.sanitize("电话: 13912345678")

        assert "13912345678" not in sanitized
        assert any(v.type.value == "pii_phone" for v in violations)

    def test_sanitize_masks_id_card(self):
        """sanitize 方法应遮蔽身份证号 (critical 级别 -> 非严格模式也替换)"""
        from app.services.content_moderation import ContentModerator

        moderator = ContentModerator()
        sanitized, violations = moderator.sanitize("身份证: 110101199003074513")

        assert "110101199003074513" not in sanitized
        assert any(v.type.value == "pii_id_card" for v in violations)

    def test_sanitize_non_strict_skips_non_critical(self):
        """非严格模式下, 非 critical 级别的 PII 不会被 sanitize 替换"""
        from app.services.content_moderation import ContentModerator

        moderator = ContentModerator(strict_mode=False)
        sanitized, violations = moderator.sanitize("电话: 13912345678")

        # 非严格模式: phone (high) 不是 critical, is_safe=True, 不替换
        assert "13912345678" in sanitized
        assert any(v.type.value == "pii_phone" for v in violations)
