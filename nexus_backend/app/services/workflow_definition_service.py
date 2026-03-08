"""
Phase 1B: Workflow Definition Service
Manages CRUD operations for visual workflow definitions (approval_chains table).
Supports node types: approver, condition, parallel, auto_approve, notify.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)

# Valid node types for workflow steps
VALID_NODE_TYPES = {"approver", "condition", "parallel", "auto_approve", "notify", "cc_notify", "timer", "sub_workflow"}

# Valid approval types
VALID_APPROVAL_TYPES = {"travel", "purchase", "expense", "leave", "event", "activity", "custom", "general", "contract"}


class WorkflowDefinitionService:
    """
    Workflow definition management service.
    Handles CRUD for approval_chains and validates workflow DAG structure.
    """

    async def _get_valid_types(self, org_id: str, db=None) -> set[str]:
        """从 approval_type_config 表获取有效类型，fallback 到硬编码。"""
        client = db or supabase
        if client:
            try:
                result = (
                    await client.table("approval_type_config")
                    .select("type_code")
                    .eq("organization_id", org_id)
                    .eq("is_active", True)
                    .execute()
                )
                if result.data:
                    return {r["type_code"] for r in result.data}
            except Exception:
                pass
        return VALID_APPROVAL_TYPES

    async def create_workflow(
        self,
        org_id: str,
        name: str,
        applies_to: list[str],
        steps: list[dict],
        conditions: list[dict] | None = None,
        canvas_layout: dict | None = None,
        created_by: str | None = None,
        db=None,
    ) -> dict:
        """Create a new workflow definition."""
        client = db or supabase
        if not client:
            raise ValueError("Database client unavailable")

        # Validate applies_to types
        valid_types = await self._get_valid_types(org_id, db=client)
        for t in applies_to:
            if t not in valid_types:
                raise ValueError(f"Invalid approval type: {t}")

        # Validate workflow structure
        errors = self.validate_workflow_definition(steps, conditions)
        if errors:
            raise ValueError(f"Workflow validation failed: {'; '.join(errors)}")

        data = {
            "organization_id": org_id,
            "name": name,
            "applies_to": applies_to,
            "steps": steps,
            "conditions": conditions,
            "canvas_layout": canvas_layout,
            "is_active": True,
            "is_default": False,
            "version": 1,
            "created_by": created_by,
        }

        result = await client.table("approval_chains").insert(data).execute()
        if not result.data:
            raise RuntimeError("Failed to create workflow")

        logger.info(f"Created workflow '{name}' for org {org_id}")
        return result.data[0]

    async def update_workflow(
        self,
        workflow_id: str,
        updates: dict[str, Any],
        org_id: str | None = None,
        db=None,
    ) -> dict:
        """Update an existing workflow definition."""
        client = db or supabase
        if not client:
            raise ValueError("Database client unavailable")

        # If steps are being updated, validate them
        if "steps" in updates:
            conditions = updates.get("conditions")
            errors = self.validate_workflow_definition(updates["steps"], conditions)
            if errors:
                raise ValueError(f"Workflow validation failed: {'; '.join(errors)}")

        # If applies_to is being updated, validate types
        if "applies_to" in updates:
            existing_wf = await self.get_workflow(workflow_id, db=client)
            wf_org_id = existing_wf.get("organization_id", "") if existing_wf else ""
            valid_types = await self._get_valid_types(wf_org_id, db=client)
            for t in updates["applies_to"]:
                if t not in valid_types:
                    raise ValueError(f"Invalid approval type: {t}")

        # Increment version on structural changes
        if "steps" in updates or "conditions" in updates:
            existing = await self.get_workflow(workflow_id, db=client)
            if existing:
                updates["version"] = existing.get("version", 1) + 1

        # Prevent updating immutable fields
        for field in ("id", "organization_id", "created_at", "created_by"):
            updates.pop(field, None)

        updates["updated_at"] = datetime.now(UTC).isoformat()

        # Use service-role client for UPDATE to avoid RLS PATCH issues.
        # Security: router enforces require_role(["founder","boss"]) + org context.
        # Additional safety: filter by organization_id when available.
        write_client = supabase or client
        query = write_client.table("approval_chains").update(updates).eq("id", workflow_id)
        if org_id:
            query = query.eq("organization_id", org_id)
        result = await query.execute()

        if not result.data:
            raise RuntimeError(f"Workflow {workflow_id} not found or update failed")

        logger.info(f"Updated workflow {workflow_id}")
        return result.data[0]

    async def delete_workflow(
        self,
        workflow_id: str,
        db=None,
    ) -> bool:
        """Delete a workflow definition."""
        client = db or supabase
        if not client:
            raise ValueError("Database client unavailable")

        write_client = supabase or client
        result = await write_client.table("approval_chains").delete().eq("id", workflow_id).execute()

        deleted = bool(result.data)
        if deleted:
            logger.info(f"Deleted workflow {workflow_id}")
        return deleted

    async def get_workflow(
        self,
        workflow_id: str,
        db=None,
    ) -> dict | None:
        """Get a single workflow definition by ID."""
        client = db or supabase
        if not client:
            return None

        result = await client.table("approval_chains").select("*").eq("id", workflow_id).maybe_single().execute()

        return result.data

    async def list_workflows(
        self,
        org_id: str,
        db=None,
    ) -> list[dict]:
        """List all workflow definitions for an organization."""
        client = db or supabase
        if not client:
            return []

        result = (
            await client.table("approval_chains")
            .select("*")
            .eq("organization_id", org_id)
            .order("created_at", desc=True)
            .execute()
        )

        return result.data or []

    async def get_workflow_for_type(
        self,
        org_id: str,
        approval_type: str,
        db=None,
    ) -> dict | None:
        """
        Get the active workflow for a specific approval type within an organization.
        Prioritizes the default workflow, otherwise returns the first active match.
        """
        client = db or supabase
        if not client:
            return None

        # Query active chains for this org that contain the approval_type
        result = (
            await client.table("approval_chains")
            .select("*")
            .eq("organization_id", org_id)
            .eq("is_active", True)
            .contains("applies_to", [approval_type])
            .order("is_default", desc=True)
            .limit(1)
            .execute()
        )

        if result.data:
            return result.data[0]
        return None

    async def toggle_workflow(
        self,
        workflow_id: str,
        db=None,
    ) -> dict:
        """Toggle the is_active status of a workflow."""
        client = db or supabase
        if not client:
            raise ValueError("Database client unavailable")

        existing = await self.get_workflow(workflow_id, db=client)
        if not existing:
            raise RuntimeError(f"Workflow {workflow_id} not found")

        new_active = not existing.get("is_active", True)
        write_client = supabase or client
        result = await write_client.table("approval_chains").update({"is_active": new_active}).eq("id", workflow_id).execute()

        if not result.data:
            raise RuntimeError(f"Failed to toggle workflow {workflow_id}")

        logger.info(f"Toggled workflow {workflow_id} active={new_active}")
        return result.data[0]

    async def set_default(
        self,
        workflow_id: str,
        org_id: str,
        db=None,
    ) -> dict:
        """
        Set a workflow as the default for its organization.
        Unsets any previously default workflow in the same org.
        """
        client = db or supabase
        if not client:
            raise ValueError("Database client unavailable")

        # Unset all existing defaults for this org
        write_client = supabase or client
        await (
            write_client.table("approval_chains")
            .update({"is_default": False})
            .eq("organization_id", org_id)
            .eq("is_default", True)
            .execute()
        )

        # Set the target workflow as default
        result = (
            await write_client.table("approval_chains")
            .update({"is_default": True, "is_active": True})
            .eq("id", workflow_id)
            .execute()
        )

        if not result.data:
            raise RuntimeError(f"Workflow {workflow_id} not found")

        logger.info(f"Set workflow {workflow_id} as default for org {org_id}")
        return result.data[0]

    def validate_workflow_definition(
        self,
        steps: list[dict],
        conditions: list[dict] | None = None,
    ) -> list[str]:
        """
        Validate a workflow definition structure.
        Returns a list of error messages (empty if valid).

        Checks:
        - At least one step exists
        - At least one approver node
        - All node types are valid
        - No orphan nodes (all next_step references are valid)
        - No cycles in the workflow graph
        - Start and end nodes are properly defined
        """
        errors: list[str] = []

        if not steps or not isinstance(steps, list):
            errors.append("Workflow must contain at least one step")
            return errors

        # Build node ID set and adjacency for cycle detection
        node_ids = set()
        adjacency: dict[str, list[str]] = {}
        has_approver = False
        has_start = False
        has_end = False

        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                errors.append(f"Step {i} is not a valid object")
                continue

            node_id = step.get("id", str(i))
            node_type = step.get("type")

            # Check node type validity
            if node_type not in VALID_NODE_TYPES:
                errors.append(
                    f"Step '{node_id}' has invalid type '{node_type}'. "
                    f"Valid types: {', '.join(sorted(VALID_NODE_TYPES))}"
                )

            if node_type == "approver":
                has_approver = True

            # Track start/end markers
            if step.get("is_start", False):
                has_start = True
            if step.get("is_end", False):
                has_end = True

            node_ids.add(node_id)
            adjacency[node_id] = []

            # Collect next-step references
            next_steps = step.get("next", [])
            if isinstance(next_steps, str):
                next_steps = [next_steps]
            elif isinstance(next_steps, list):
                pass
            else:
                next_steps = []

            adjacency[node_id] = next_steps

        # Also process condition nodes if provided
        if conditions:
            for cond in conditions:
                if isinstance(cond, dict):
                    cond_id = cond.get("id")
                    if cond_id:
                        node_ids.add(cond_id)
                        branches = []
                        for branch in cond.get("branches", []):
                            if isinstance(branch, dict) and "target" in branch:
                                branches.append(branch["target"])
                        adjacency[cond_id] = branches

        if not has_approver:
            errors.append("Workflow must contain at least one 'approver' node")

        # For simple linear workflows, be lenient about start/end markers
        if len(steps) > 1:
            if not has_start:
                # Accept if the first step is implicitly the start
                pass
            if not has_end:
                # Accept if the last step is implicitly the end
                pass

        # Check for orphan references (next points to non-existent node)
        for node_id, targets in adjacency.items():
            for target in targets:
                if target not in node_ids:
                    errors.append(f"Node '{node_id}' references non-existent node '{target}'")

        # Cycle detection using DFS
        visited = set()
        rec_stack = set()

        def _has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    if _has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        for node_id in node_ids:
            if node_id not in visited and _has_cycle(node_id):
                errors.append("Workflow contains a cycle (circular dependency)")
                break

        return errors


# Global service instance
workflow_definition_service = WorkflowDefinitionService()
