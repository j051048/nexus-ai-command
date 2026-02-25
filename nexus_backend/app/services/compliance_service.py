"""
VMD Compliance Checking Service - Two-level content compliance engine.

Level 1: Fast regex/keyword scan (advertising law, metrology law, bidding law)
Level 2: LLM deep analysis for nuanced violations

Covers:
- 广告法 (Advertising Law)
- 计量法 (Metrology Law)
- 招投标法 (Bidding Law)
- 医疗器械法规 (Medical Device Regulations)
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Data Models
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ComplianceIssue:
    """A single compliance issue found during checking."""

    rule_code: str
    rule_name: str
    severity: str  # error / warning / info
    category: str
    matched_text: str
    position: int
    suggestion: str


@dataclass
class ComplianceResult:
    """Aggregate result from a compliance check."""

    is_compliant: bool
    total_issues: int
    errors: int
    warnings: int
    issues: list[ComplianceIssue] = field(default_factory=list)
    checked_at: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
#  Built-in Rules (Level 1)
# ═══════════════════════════════════════════════════════════════════════════════

_BUILTIN_RULES: list[dict[str, Any]] = [
    # ── 广告法 ─────────────────────────────────────────────
    {
        "code": "AD_001",
        "name": "广告法-绝对化用语",
        "category": "advertising_law",
        "severity": "error",
        "pattern": r"(最先进|最好|第一|唯一|国内首创|全球领先|业界最|NO\.?\s*1|顶级|极致|绝对)",
        "suggestion": "删除或替换为'领先'、'优秀'等非绝对化用语",
    },
    {
        "code": "AD_002",
        "name": "广告法-虚假承诺",
        "category": "advertising_law",
        "severity": "error",
        "pattern": r"(保证|承诺|确保).{0,10}(100%|零故障|永不|绝不)",
        "suggestion": "删除虚假承诺表述，改为'致力于'、'努力'等",
    },
    {
        "code": "AD_003",
        "name": "广告法-权威机构引用",
        "category": "advertising_law",
        "severity": "warning",
        "pattern": r"(国家机关|政府|军队|专家推荐|指定产品).{0,10}(推荐|指定|认证)",
        "suggestion": "删除涉及权威机构推荐的表述，除非有真实授权文件",
    },
    # ── 计量法 ─────────────────────────────────────────────
    {
        "code": "ML_001",
        "name": "计量法-精度声明",
        "category": "metrology_law",
        "severity": "warning",
        "pattern": r"(精度|准确度|测量范围|分辨率|灵敏度).{0,20}(?!（.*?证书|检定|校准）)",
        "suggestion": "精度声明应注明计量检定/校准证书编号",
    },
    {
        "code": "ML_002",
        "name": "计量法-单位规范",
        "category": "metrology_law",
        "severity": "info",
        "pattern": r"\d+\s*(ppb|ppm|PPB|PPM)(?!\s*[\(（])",
        "suggestion": "建议同时标注国际单位制(SI)单位",
    },
    # ── 招标法 ─────────────────────────────────────────────
    {
        "code": "BID_001",
        "name": "招标法-排他性条款",
        "category": "bidding_law",
        "severity": "error",
        "pattern": r"(仅限|必须使用|指定品牌|唯一供应商|排除)",
        "suggestion": "招标文件不得含有排他性条款",
    },
    {
        "code": "BID_002",
        "name": "招标法-倾向性表述",
        "category": "bidding_law",
        "severity": "warning",
        "pattern": r"(优先考虑|倾向于|偏好|特别推荐).{0,10}(某|特定|指定)",
        "suggestion": "删除带有倾向性的评标条件表述",
    },
    # ── 医疗器械 ───────────────────────────────────────────
    {
        "code": "MD_001",
        "name": "医疗器械-注册证要求",
        "category": "medical_device",
        "severity": "error",
        "pattern": r"(医疗|诊断|临床|体外诊断|IVD)(?!.{0,30}(注册证|备案号|许可证))",
        "suggestion": "涉及医疗器械的描述必须附带注册证/备案号",
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
#  Service
# ═══════════════════════════════════════════════════════════════════════════════


class ComplianceService:
    """
    Two-level compliance checker for scientific instrument industry.

    Level 1 — regex / keyword fast scan (< 50 ms typical)
    Level 2 — LLM deep analysis for context-dependent violations
    """

    _BUILTIN_RULES = _BUILTIN_RULES

    # ─── Public API ────────────────────────────────────────

    async def check_content(
        self,
        content: str,
        categories: list[str] | None = None,
        org_id: str | None = None,
        use_llm: bool = False,
        *,
        tenant_id: str | None = None,
        enable_llm: bool | None = None,
    ) -> ComplianceResult:
        """
        Run two-level compliance check on *content*.

        Args:
            content: Text to check.
            categories: Optional filter — only apply rules from these categories.
            org_id: Organisation / tenant id (used to load custom DB rules).
            use_llm: Whether to enable Level-2 LLM deep analysis.

        Returns:
            ComplianceResult with all found issues.
        """
        if not content or not content.strip():
            return ComplianceResult(
                is_compliant=True,
                total_issues=0,
                errors=0,
                warnings=0,
                issues=[],
                checked_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )

        # Support alternate parameter names from router
        effective_org_id = tenant_id or org_id
        effective_use_llm = enable_llm if enable_llm is not None else use_llm

        issues: list[ComplianceIssue] = []

        # ── Level 1: Regex / keyword fast scan ─────────────
        rules = await self._load_rules(effective_org_id, categories)

        for rule in rules:
            # Skip rules meant for LLM-only checking
            if rule.get("check_type") == "llm":
                continue

            pattern = rule.get("pattern", "")
            if not pattern:
                continue

            try:
                for match in re.finditer(pattern, content):
                    issues.append(
                        ComplianceIssue(
                            rule_code=rule.get("code", rule.get("rule_code", "UNKNOWN")),
                            rule_name=rule.get("name", rule.get("rule_name", "")),
                            severity=rule.get("severity", "warning"),
                            category=rule.get("category", ""),
                            matched_text=match.group()[:100],
                            position=match.start(),
                            suggestion=rule.get("suggestion", ""),
                        )
                    )
            except re.error as e:
                logger.warning(
                    "Invalid regex in rule %s: %s",
                    rule.get("code", rule.get("rule_code")),
                    e,
                )

        # ── Level 2: LLM deep analysis (optional) ─────────
        if effective_use_llm and content.strip():
            llm_issues = await self._llm_check(content, categories)
            issues.extend(llm_issues)

        # ── Aggregate ──────────────────────────────────────
        errors = sum(1 for i in issues if i.severity == "error")
        warnings = sum(1 for i in issues if i.severity == "warning")

        return ComplianceResult(
            is_compliant=errors == 0,
            total_issues=len(issues),
            errors=errors,
            warnings=warnings,
            issues=issues,
            checked_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

    async def check_bid_document(self, content: str, tender_requirements: str | None = None) -> dict[str, Any]:
        """
        Specialized bid-document compliance check.

        Checks for waste-bid risk, qualification gaps, technical deviation,
        commercial issues, and legal risks.
        """
        # First run standard Level-1 scan on bid-related categories
        base_result = await self.check_content(content, categories=["bidding_law"], use_llm=False)

        prompt = f"请对以下投标文件内容进行专项合规审查：\n\n" f"## 投标文件\n{content[:5000]}\n\n"
        if tender_requirements:
            prompt += f"## 招标要求\n{tender_requirements[:3000]}\n\n"

        prompt += (
            "请重点检查：\n"
            "1. **废标风险** — 是否存在导致废标的严重问题\n"
            "2. **资质缺失** — 是否遗漏了必须的资质证明\n"
            "3. **技术偏差** — 技术响应与要求的重大偏离\n"
            "4. **商务问题** — 报价格式、有效期、密封等问题\n"
            "5. **法律风险** — 是否存在法律合规问题\n\n"
            '按JSON数组格式输出：[{"issue": "...", "severity": "error/warning/info", '
            '"category": "废标风险/资质/技术/商务/法律", "suggestion": "..."}]\n'
            "如无问题输出空数组: []"
        )

        bid_issues: list[ComplianceIssue] = []
        try:
            from app.services.ai_service import AIService

            result = await AIService.call_llm(
                prompt,
                "你是资深招投标合规审查专家。请严格按照《招标投标法》检查。废标风险标记为error。只输出JSON。",
            )
            result = result.strip()
            if result.startswith("```"):
                lines = result.split("\n")
                result = "\n".join(lines[1:-1]).strip()

            parsed = json.loads(result)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        bid_issues.append(
                            ComplianceIssue(
                                rule_code="BID_LLM",
                                rule_name=item.get("issue", "投标合规问题"),
                                severity=item.get("severity", "warning"),
                                category=item.get("category", "bid"),
                                matched_text="",
                                position=-1,
                                suggestion=item.get("suggestion", ""),
                            )
                        )
        except Exception as e:
            logger.warning("Bid document LLM check failed: %s", e)

        all_issues = base_result.issues + bid_issues
        errors = sum(1 for i in all_issues if i.severity == "error")
        warnings = sum(1 for i in all_issues if i.severity == "warning")

        return {
            "status": "blocked" if errors > 0 else ("has_issues" if warnings > 0 else "passed"),
            "total_issues": len(all_issues),
            "errors": errors,
            "warnings": warnings,
            "issues": [
                {
                    "rule_code": i.rule_code,
                    "rule_name": i.rule_name,
                    "severity": i.severity,
                    "category": i.category,
                    "matched_text": i.matched_text,
                    "suggestion": i.suggestion,
                }
                for i in all_issues
            ],
            "document_type": "bid",
        }

    async def log_check(
        self,
        tenant_id: str,
        task_id: str,
        agent_code: str,
        result: dict[str, Any],
    ) -> None:
        """Persist compliance-check result to ``compliance_check_log``."""
        try:
            if not supabase:
                logger.warning("Database not available, skipping compliance log")
                return

            log_entry = {
                "tenant_id": tenant_id,
                "task_id": task_id,
                "agent_code": agent_code,
                "check_status": (
                    "compliant" if result.get("is_compliant", result.get("status") == "passed") else "non_compliant"
                ),
                "total_issues": result.get("total_issues", 0),
                "errors": result.get("errors", result.get("high_issues", 0)),
                "warnings": result.get("warnings", result.get("medium_issues", 0)),
                "issues_detail": result.get("issues", []),
                "checked_at": datetime.now(UTC).isoformat(),
            }

            await supabase.table("compliance_check_log").insert(log_entry).execute()
            logger.info(
                "Compliance check logged: task=%s, issues=%s",
                task_id,
                result.get("total_issues"),
            )
        except Exception as e:
            logger.error("Failed to log compliance check: %s", e)

    # ─── Internal ──────────────────────────────────────────

    async def _load_rules(
        self,
        org_id: str | None,
        categories: list[str] | None,
    ) -> list[dict]:
        """Load rules from built-in set + optional DB custom rules."""
        rules: list[dict] = list(self._BUILTIN_RULES)

        # Attempt to load tenant-specific rules from DB
        try:
            if org_id and supabase:
                query = supabase.table("compliance_rule").select("*").eq("is_active", True)
                if categories:
                    query = query.in_("category", categories)

                res = await query.execute()
                for r in res.data or []:
                    rules.append(r)
        except Exception as e:
            logger.warning("Failed to load DB compliance rules: %s", e)

        # Filter by category if requested
        if categories:
            rules = [r for r in rules if r.get("category") in categories]

        return rules

    async def _llm_check(
        self,
        content: str,
        categories: list[str] | None,
    ) -> list[ComplianceIssue]:
        """Level 2: LLM deep analysis for context-dependent violations."""
        issues: list[ComplianceIssue] = []
        try:
            from app.services.ai_service import AIService

            category_text = (
                ", ".join(categories) if categories else "advertising_law, metrology_law, bidding_law, medical_device"
            )
            prompt = (
                f"请检查以下内容是否存在合规问题，重点关注{category_text}相关法规。\n\n"
                f"内容：\n{content[:3000]}\n\n"
                "如果发现问题，请用JSON数组格式返回，每项包含：rule_name, severity(error/warning), "
                "matched_text, suggestion。如果无问题返回空数组[]。"
            )
            system = "你是科学仪器行业合规审查专家。只返回JSON。"

            result = await AIService.call_llm(prompt, system)

            # Strip markdown fences if present
            result = result.strip()
            if result.startswith("```"):
                lines = result.split("\n")
                result = "\n".join(lines[1:-1]).strip()

            parsed = json.loads(result)
            if not isinstance(parsed, list):
                return issues

            for item in parsed:
                if isinstance(item, dict):
                    issues.append(
                        ComplianceIssue(
                            rule_code="LLM_CHECK",
                            rule_name=item.get("rule_name", "LLM检查"),
                            severity=item.get("severity", "warning"),
                            category="llm_analysis",
                            matched_text=item.get("matched_text", ""),
                            position=0,
                            suggestion=item.get("suggestion", ""),
                        )
                    )
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM compliance check response as JSON")
        except Exception as e:
            logger.warning("LLM compliance check failed: %s", e)

        return issues


# Module-level singleton
compliance_service = ComplianceService()
