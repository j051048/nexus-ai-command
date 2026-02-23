"""
P1 Enhancement: Structured Output Schema Validation

Implements Pydantic-based schema validation for LLM outputs.
Fixes Issue #6: Missing structured output schema validation.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ValidationError, validator

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity level for validation errors."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    """Result of schema validation."""

    is_valid: bool
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    corrected_data: dict[str, Any] | None = None


# Common Schemas for Tool Parameters


class SearchQuerySchema(BaseModel):
    """Schema for search query parameters."""

    query: str = Field(..., min_length=1, max_length=500)
    filters: dict[str, Any] | None = None
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class DateRangeSchema(BaseModel):
    """Schema for date range parameters."""

    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")

    @validator("end_date")
    def end_after_start(self, v, values):
        if "start_date" in values and v < values["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


class PaginationSchema(BaseModel):
    """Schema for pagination parameters."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class UserIdSchema(BaseModel):
    """Schema for user ID parameters."""

    user_id: str = Field(..., pattern=r"^[a-zA-Z0-9-_]+$", min_length=1, max_length=100)


class OrgIdSchema(BaseModel):
    """Schema for organization ID parameters."""

    org_id: str = Field(..., pattern=r"^[a-zA-Z0-9-_]+$", min_length=1, max_length=100)


class AmountSchema(BaseModel):
    """Schema for monetary amounts."""

    amount: float = Field(..., ge=0)
    currency: str = Field(default="CNY", pattern=r"^[A-Z]{3}$")


class EmailSchema(BaseModel):
    """Schema for email parameters."""

    email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class PhoneSchema(BaseModel):
    """Schema for phone number parameters."""

    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")


class StatusUpdateSchema(BaseModel):
    """Schema for status update operations."""

    entity_id: str = Field(..., min_length=1)
    new_status: str = Field(..., min_length=1)
    reason: str | None = Field(None, max_length=500)


class BulkOperationSchema(BaseModel):
    """Schema for bulk operations."""

    entity_ids: list[str] = Field(..., min_items=1, max_items=100)
    operation: str = Field(..., min_length=1)
    parameters: dict[str, Any] | None = None


class OutputSchemaService:
    """
    P1 Enhancement: Structured output validation service.

    Features:
    - Pydantic schema validation
    - Automatic type coercion
    - Error correction suggestions
    - Custom schema registration
    """

    def __init__(self):
        self._schemas: dict[str, type[BaseModel]] = {}
        self._register_default_schemas()

    def _register_default_schemas(self):
        """Register default schemas."""
        self._schemas = {
            "search_query": SearchQuerySchema,
            "date_range": DateRangeSchema,
            "pagination": PaginationSchema,
            "user_id": UserIdSchema,
            "org_id": OrgIdSchema,
            "amount": AmountSchema,
            "email": EmailSchema,
            "phone": PhoneSchema,
            "status_update": StatusUpdateSchema,
            "bulk_operation": BulkOperationSchema,
        }

    def register_schema(self, name: str, schema: type[BaseModel]):
        """Register a custom schema."""
        self._schemas[name] = schema
        logger.info(f"Registered schema: {name}")

    def validate(self, data: dict[str, Any], schema_name: str) -> ValidationResult:
        """Validate data against a named schema."""
        schema = self._schemas.get(schema_name)
        if not schema:
            return ValidationResult(
                is_valid=False, errors=[{"message": f"Schema '{schema_name}' not found"}], warnings=[]
            )

        return self.validate_against_schema(data, schema)

    def validate_against_schema(self, data: dict[str, Any], schema: type[BaseModel]) -> ValidationResult:
        """Validate data against a Pydantic schema."""
        errors = []
        warnings = []
        corrected_data = None

        try:
            # Attempt to parse and validate
            validated = schema(**data)
            corrected_data = validated.dict()

            return ValidationResult(is_valid=True, errors=[], warnings=[], corrected_data=corrected_data)

        except ValidationError as e:
            # Parse validation errors
            for error in e.errors():
                errors.append(
                    {
                        "field": ".".join(str(loc) for loc in error["loc"]),
                        "message": error["msg"],
                        "type": error["type"],
                        "input": str(error["input"])[:100],
                    }
                )

            # Try to correct common issues
            corrected_data = self._attempt_correction(data, schema, errors)

        except Exception as e:
            errors.append({"field": "unknown", "message": str(e), "type": "unknown_error"})

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, corrected_data=corrected_data
        )

    def _attempt_correction(
        self, data: dict[str, Any], schema: type[BaseModel], errors: list[dict]
    ) -> dict[str, Any] | None:
        """Attempt to correct common validation errors."""
        corrected = data.copy()

        for error in errors:
            field = error.get("field", "")
            error_type = error.get("type", "")

            # Type coercion
            if error_type == "type_error.integer":
                try:
                    if field in corrected:
                        corrected[field] = int(float(corrected[field]))
                except (ValueError, TypeError):
                    pass

            elif error_type == "type_error.float":
                try:
                    if field in corrected:
                        corrected[field] = float(corrected[field])
                except (ValueError, TypeError):
                    pass

            elif error_type == "type_error.bool":
                if field in corrected:
                    val = str(corrected[field]).lower()
                    corrected[field] = val in ("true", "1", "yes", "on")

            # Missing required field - try to set default
            elif error_type == "value_error.missing":
                try:
                    schema_fields = schema.__fields__
                    if field in schema_fields:
                        field_info = schema_fields[field]
                        if field_info.default is not None:
                            corrected[field] = field_info.default
                        elif field_info.default_factory is not None:
                            corrected[field] = field_info.default_factory()
                except Exception:
                    pass

        # Re-validate corrected data
        try:
            validated = schema(**corrected)
            return validated.dict()
        except ValidationError:
            return None

    async def validate_llm_tool_params(
        self, tool_name: str, params: dict[str, Any], tool_schemas: dict[str, type[BaseModel]] = None
    ) -> ValidationResult:
        """
        Validate tool parameters from LLM output.
        Uses tool-specific schemas if provided.
        """
        if tool_schemas and tool_name in tool_schemas:
            return self.validate_against_schema(params, tool_schemas[tool_name])

        # Try to infer schema from tool name
        schema_name = self._infer_schema_from_tool(tool_name)
        if schema_name:
            return self.validate(params, schema_name)

        # No schema available - do basic validation
        return self._basic_validation(params)

    def _infer_schema_from_tool(self, tool_name: str) -> str | None:
        """Infer validation schema from tool name."""
        tool_schema_map = {
            "search": "search_query",
            "query": "search_query",
            "get_user": "user_id",
            "update_user": "user_id",
            "get_org": "org_id",
            "update_status": "status_update",
            "bulk_update": "bulk_operation",
            "send_email": "email",
            "send_sms": "phone",
            "get_report": "date_range",
        }

        for key, schema in tool_schema_map.items():
            if key in tool_name.lower():
                return schema

        return None

    def _basic_validation(self, params: dict[str, Any]) -> ValidationResult:
        """Perform basic validation when no schema is available."""
        warnings = []

        # Check for empty strings
        for key, value in params.items():
            if isinstance(value, str) and not value.strip():
                warnings.append({"field": key, "message": "Empty string value", "type": "warning"})

        # Check for None values
        for key, value in params.items():
            if value is None:
                warnings.append({"field": key, "message": "None value", "type": "warning"})

        return ValidationResult(is_valid=True, errors=[], warnings=warnings, corrected_data=params)

    def get_schema_json(self, schema_name: str) -> dict | None:
        """Get JSON schema definition for documentation."""
        schema = self._schemas.get(schema_name)
        if not schema:
            return None

        return schema.schema()

    def list_schemas(self) -> list[str]:
        """List all registered schema names."""
        return list(self._schemas.keys())


# Global instance
output_schema_service = OutputSchemaService()
