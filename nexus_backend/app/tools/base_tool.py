import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ConfirmationType(Enum):
    """P2-1: Structured HITL confirmation types."""

    IRREVERSIBLE = "irreversible"  # Delete, reject, cancel operations
    HIGH_VALUE = "high_value"  # Amount exceeds threshold
    BULK_OPERATION = "bulk"  # Batch operations affecting multiple records
    EXTERNAL = "external"  # Actions affecting external systems (email, webhook)
    PERMISSION_ESCALATION = "escalation"  # Actions requiring elevated privileges


# P2-1: Thresholds for automatic confirmation triggers
CONFIRMATION_THRESHOLDS = {
    "high_value_amount": 50_000,  # CNY
    "bulk_record_count": 5,
}


class ConfirmationRequired(Exception):  # noqa: N818
    """Raised when a tool requires human confirmation before execution."""

    def __init__(
        self,
        preview_message: str,
        tool_name: str,
        args: dict[str, Any],
        confirmation_type: ConfirmationType = ConfirmationType.IRREVERSIBLE,
    ):
        self.preview_message = preview_message
        self.tool_name = tool_name
        self.args = args
        self.confirmation_type = confirmation_type
        super().__init__(preview_message)


class BaseTool(ABC):
    """
    Abstract Base Class for all AI Agent Tools.
    Enforces the Strategy Pattern to decouple tool logic from the router.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for the tool parameters"""
        pass

    @property
    def domain(self) -> str | None:
        """Tool domain for intent-based filtering (e.g. 'finance', 'crm', 'hr').
        If set, auto-registered into _DOMAIN_TOOL_MAP during discovery."""
        return None

    @property
    def required_role(self) -> str:
        """
        Optional: user role required to execute this tool.
        Returns 'all' by default, meaning no restriction.
        Possible values: 'boss', 'manager', 'sales', 'all', 'ai_assistant'
        """
        return "all"

    @property
    def is_irreversible(self) -> bool:
        """
        Whether this tool performs irreversible operations (approve, reject, delete, publish).
        If True, the system-level confirmation gate will intercept calls
        where confirm != True, regardless of what the LLM decides.
        """
        return False

    @property
    def confirmation_message(self) -> str:
        """
        Message to show when confirmation is required.
        Override in subclass for custom messages.
        """
        return "⚠️ 这是一个不可逆操作。请确认后再执行。"

    @property
    def examples(self) -> list[dict]:
        """Optional: example invocations [{input: {...}, output_summary: "..."}].
        Appended to description in tool schema to help LLM pick correct params."""
        return []

    @property
    def gotchas(self) -> str:
        """Optional: common pitfalls or constraints for this tool.
        Appended to description in tool schema to prevent LLM mistakes."""
        return ""

    @property
    def related_tools(self) -> list[str]:
        """Optional: names of related tools the LLM should consider.
        Helps LLM self-correct when it picks the wrong tool."""
        return []

    def check_confirmation(self, args: dict[str, Any], system_confirmed: bool = False) -> str | None:
        """
        System-level confirmation gate.
        Called BEFORE run() for irreversible tools.
        Returns None if confirmed, or a preview message string if confirmation needed.

        P0 Fix #2: This NOW requires system_confirmed=True (from frontend action)
        and ignores the LLM-generated 'confirm' argument to prevent bypass.

        P2-1: Enhanced with structured confirmation types:
        - Irreversible operations (delete, reject, cancel)
        - High-value transactions (above threshold)
        - Bulk operations (affecting multiple records)
        """
        reasons: list[str] = []

        # Check irreversible flag
        if self.is_irreversible:
            reasons.append(f"🔒 不可逆操作: {self.confirmation_message}")

        # P2-1: Check high-value amount
        amount = args.get("amount") or args.get("value") or args.get("total")
        if amount and isinstance(amount, int | float) and amount >= CONFIRMATION_THRESHOLDS["high_value_amount"]:
            reasons.append(f"💰 大额操作: ¥{amount:,.0f} (超过 ¥{CONFIRMATION_THRESHOLDS['high_value_amount']:,} 阈值)")

        # P2-1: Check bulk operations
        items = args.get("ids") or args.get("items") or args.get("batch")
        if isinstance(items, list | tuple) and len(items) >= CONFIRMATION_THRESHOLDS["bulk_record_count"]:
            reasons.append(f"📦 批量操作: 将影响 {len(items)} 条记录")

        if not reasons:
            return None

        # System-level enforcement: if not explicitly confirmed by the system (human click), block
        if system_confirmed is True:
            return None  # Confirmed by human, allow execution

        return "\n".join(["⚠️ 操作需要确认:"] + reasons + ["请确认后再执行。"])

    async def validate(self, args: dict[str, Any]) -> None:
        """
        Validate arguments against the tool's JSON schema parameters.
        Throws jsonschema.ValidationError if invalid.
        """
        if not self.parameters:
            return

        import jsonschema

        try:
            jsonschema.validate(instance=args, schema=self.parameters)
        except jsonschema.SchemaError as se:
            logger.error(f"Invalid schema for tool {self.name}: {se.message}")
            # Don't fail the user for a developer error, but log it
        except jsonschema.ValidationError as ve:
            raise ValueError(f"工具 {self.name} 参数校验失败: {ve.message}") from ve

    @abstractmethod
    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        """
        Execute the tool logic.
        :param args: Arguments parsed from the LLM's JSON output
        :param user_id: ID of the user invoking the tool
        :param config: AI Configuration (API Key, Base URL) for nested LLM calls
        :return: Text result to be fed back to the LLM
        """
        pass
