"""
Custom Form Schema Service

Manages form schema definitions and provides validation for form data
submitted through the approval workflow.

Features:
- CRUD operations for form schemas
- Schema definition validation
- Form data validation against schema
- Organization-scoped access via RLS
"""

import logging
import re
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)

# Supported field types
SUPPORTED_FIELD_TYPES = {
    "text",
    "number",
    "date",
    "daterange",
    "select",
    "multiselect",
    "file",
    "textarea",
}

# ISO 8601 date pattern (YYYY-MM-DD or full datetime)
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?)?$")


class FormSchemaService:
    """自定义表单 Schema 管理与验证服务"""

    async def create_schema(
        self,
        org_id: str,
        approval_type: str,
        name: str,
        fields: list[dict[str, Any]],
        description: str | None = None,
        layout: dict | None = None,
        created_by: str | None = None,
        db=None,
    ) -> dict:
        """
        Create a new form schema for an approval type within an organization.

        Before creating, validates the schema definition itself.
        If an active schema already exists for the same (org, type), it will be
        deactivated first (handled by partial unique index).
        """
        client = db or supabase
        if not client:
            raise RuntimeError("Database client unavailable")

        # Validate schema definition
        errors = self.validate_schema_definition(fields)
        if errors:
            raise ValueError(f"Schema definition invalid: {'; '.join(errors)}")

        # Deactivate existing active schema for same org+type
        try:
            await (
                client.table("form_schemas")
                .update({"is_active": False})
                .eq("organization_id", org_id)
                .eq("approval_type", approval_type)
                .eq("is_active", True)
                .execute()
            )
        except Exception as e:
            logger.warning(f"Deactivation of previous schema skipped: {e}")

        # Build insert data
        data = {
            "organization_id": org_id,
            "approval_type": approval_type,
            "name": name,
            "fields": fields,
            "is_active": True,
            "version": 1,
        }
        if description is not None:
            data["description"] = description
        if layout is not None:
            data["layout"] = layout
        if created_by is not None:
            data["created_by"] = created_by

        result = await client.table("form_schemas").insert(data).execute()

        if not result.data:
            raise RuntimeError("Failed to create form schema")

        created = result.data[0] if isinstance(result.data, list) else result.data
        logger.info(f"Form schema created: {created.get('id')} for type={approval_type} org={org_id}")
        return created

    async def update_schema(self, schema_id: str, updates: dict[str, Any], db=None) -> dict:
        """
        Update an existing form schema.

        If 'fields' is in updates, validates the new definition.
        Increments the version number automatically.
        """
        client = db or supabase
        if not client:
            raise RuntimeError("Database client unavailable")

        # Validate fields if being updated
        if "fields" in updates:
            errors = self.validate_schema_definition(updates["fields"])
            if errors:
                raise ValueError(f"Schema definition invalid: {'; '.join(errors)}")

        # Fetch current version for incrementing
        current = await client.table("form_schemas").select("version").eq("id", schema_id).maybe_single().execute()

        if not current.data:
            raise ValueError("Schema not found")

        current_version = current.data.get("version", 1)
        updates["version"] = current_version + 1

        # Remove fields that should not be directly updated
        safe_updates = {
            k: v for k, v in updates.items() if k in ("name", "description", "fields", "layout", "is_active", "version")
        }

        result = await client.table("form_schemas").update(safe_updates).eq("id", schema_id).execute()

        if not result.data:
            raise RuntimeError("Failed to update form schema")

        updated = result.data[0] if isinstance(result.data, list) else result.data
        logger.info(f"Form schema updated: {schema_id} -> v{updates['version']}")
        return updated

    async def delete_schema(self, schema_id: str, db=None) -> bool:
        """
        Delete a form schema by ID.

        Returns True if deletion was successful.
        """
        client = db or supabase
        if not client:
            raise RuntimeError("Database client unavailable")

        result = await client.table("form_schemas").delete().eq("id", schema_id).execute()

        deleted = bool(result.data)
        if deleted:
            logger.info(f"Form schema deleted: {schema_id}")
        else:
            logger.warning(f"Form schema not found for deletion: {schema_id}")
        return deleted

    async def get_schema(self, schema_id: str, db=None) -> dict | None:
        """
        Get a single form schema by ID.
        """
        client = db or supabase
        if not client:
            raise RuntimeError("Database client unavailable")

        result = await client.table("form_schemas").select("*").eq("id", schema_id).maybe_single().execute()

        return result.data

    async def list_schemas(self, org_id: str, db=None) -> list[dict]:
        """
        List all form schemas for an organization.

        Returns schemas ordered by approval_type and creation time.
        """
        client = db or supabase
        if not client:
            raise RuntimeError("Database client unavailable")

        result = (
            await client.table("form_schemas")
            .select("*")
            .eq("organization_id", org_id)
            .order("approval_type")
            .order("created_at", desc=True)
            .execute()
        )

        return result.data or []

    async def get_schema_for_type(self, org_id: str, approval_type: str, db=None) -> dict | None:
        """
        Get the active form schema for a specific approval type within an organization.
        """
        client = db or supabase
        if not client:
            raise RuntimeError("Database client unavailable")

        result = (
            await client.table("form_schemas")
            .select("*")
            .eq("organization_id", org_id)
            .eq("approval_type", approval_type)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )

        return result.data

    def validate_form_data(self, schema_fields: list[dict], form_data: dict) -> list[str]:
        """
        Validate user-submitted form data against the schema definition.

        Returns a list of error messages. An empty list means validation passed.

        Validation rules:
        - required fields must have a non-empty value
        - number type checks min/max range
        - select/multiselect checks option validity
        - date type checks ISO 8601 format
        - file type checks count (max_files) and type (file_types)
        - text/textarea checks max length
        """
        errors = []

        # Iterate through schema fields and validate corresponding form data
        for field in schema_fields:
            key = field["key"]
            field_type = field.get("type", "text")
            required = field.get("required", False)
            value = form_data.get(key)

            # Required check
            if required:
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    errors.append(f"字段 '{field.get('label', key)}' 为必填项")
                    continue
                if isinstance(value, list) and len(value) == 0:
                    errors.append(f"字段 '{field.get('label', key)}' 为必填项")
                    continue

            # Skip further validation if value is not provided and not required
            if value is None or (isinstance(value, str) and value.strip() == ""):
                continue

            # Type-specific validation
            if field_type == "number":
                try:
                    num_val = float(value)
                except (TypeError, ValueError):
                    errors.append(f"字段 '{field.get('label', key)}' 必须为数字")
                    continue

                if "min" in field and num_val < field["min"]:
                    errors.append(f"字段 '{field.get('label', key)}' 不能小于 {field['min']}")
                if "max" in field and num_val > field["max"]:
                    errors.append(f"字段 '{field.get('label', key)}' 不能大于 {field['max']}")

            elif field_type == "date":
                if not isinstance(value, str) or not ISO_DATE_PATTERN.match(value):
                    errors.append(f"字段 '{field.get('label', key)}' 日期格式无效，需符合 ISO 8601 (YYYY-MM-DD)")

            elif field_type == "daterange":
                if not isinstance(value, dict):
                    errors.append(f"字段 '{field.get('label', key)}' 日期范围应为对象 {{start, end}}")
                else:
                    for date_key in ("start", "end"):
                        date_val = value.get(date_key)
                        if date_val and (not isinstance(date_val, str) or not ISO_DATE_PATTERN.match(date_val)):
                            errors.append(f"字段 '{field.get('label', key)}' 的 {date_key} 日期格式无效")

            elif field_type == "select":
                options = field.get("options", [])
                if options and value not in options:
                    errors.append(f"字段 '{field.get('label', key)}' 的值 '{value}' 不在可选项中")

            elif field_type == "multiselect":
                options = field.get("options", [])
                if not isinstance(value, list):
                    errors.append(f"字段 '{field.get('label', key)}' 应为数组")
                elif options:
                    invalid = [v for v in value if v not in options]
                    if invalid:
                        errors.append(
                            f"字段 '{field.get('label', key)}' 包含无效选项: {', '.join(str(v) for v in invalid)}"
                        )

            elif field_type == "file":
                if not isinstance(value, list):
                    errors.append(f"字段 '{field.get('label', key)}' 文件列表应为数组")
                else:
                    max_files = field.get("max_files")
                    if max_files and len(value) > max_files:
                        errors.append(f"字段 '{field.get('label', key)}' 最多上传 {max_files} 个文件")

                    file_types = field.get("file_types", [])
                    if file_types:
                        for file_item in value:
                            file_name = file_item if isinstance(file_item, str) else file_item.get("name", "")
                            if not any(file_name.lower().endswith(ft.lower()) for ft in file_types):
                                errors.append(
                                    f"字段 '{field.get('label', key)}' 中文件 '{file_name}' 类型不被允许，"
                                    f"支持的类型: {', '.join(file_types)}"
                                )

            elif field_type in ("text", "textarea"):
                if isinstance(value, str):
                    max_len = field.get("max")
                    if max_len and len(value) > max_len:
                        errors.append(f"字段 '{field.get('label', key)}' 长度不能超过 {max_len} 个字符")
                    min_len = field.get("min")
                    if min_len and len(value) < min_len:
                        errors.append(f"字段 '{field.get('label', key)}' 长度不能少于 {min_len} 个字符")

        return errors

    def validate_schema_definition(self, fields: list[dict]) -> list[str]:
        """
        Validate the form schema definition itself.

        Checks:
        - Each field must have key, label, type
        - Keys must be unique
        - Type must be in supported list
        - select/multiselect must have options
        """
        errors = []

        if not isinstance(fields, list):
            return ["fields 必须为数组"]

        if len(fields) == 0:
            return ["fields 不能为空"]

        seen_keys = set()

        for i, field in enumerate(fields):
            if not isinstance(field, dict):
                errors.append(f"第 {i + 1} 个字段定义必须为对象")
                continue

            # Required properties
            if "key" not in field:
                errors.append(f"第 {i + 1} 个字段缺少 'key'")
            if "label" not in field:
                errors.append(f"第 {i + 1} 个字段缺少 'label'")
            if "type" not in field:
                errors.append(f"第 {i + 1} 个字段缺少 'type'")

            # Key uniqueness
            key = field.get("key")
            if key:
                if key in seen_keys:
                    errors.append(f"字段 key '{key}' 重复")
                seen_keys.add(key)

            # Type validation
            field_type = field.get("type")
            if field_type and field_type not in SUPPORTED_FIELD_TYPES:
                errors.append(
                    f"字段 '{key}' 的类型 '{field_type}' 不受支持，"
                    f"支持的类型: {', '.join(sorted(SUPPORTED_FIELD_TYPES))}"
                )

            # select/multiselect must have options
            if field_type in ("select", "multiselect"):
                options = field.get("options")
                if not options or not isinstance(options, list) or len(options) == 0:
                    errors.append(f"字段 '{key}' 类型为 '{field_type}'，必须提供 options 列表")

        return errors


# Global service instance
form_schema_service = FormSchemaService()
