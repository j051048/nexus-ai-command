"""
Item 66: Document-Level ACL Service

Provides grant/revoke/check access control for documents based on group
membership. Works with the document_access_groups table and the
access_groups column on document_embeddings.
"""

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class DocumentACLService:
    """
    Manages document-level access control lists.

    Documents can be restricted to specific groups. A user must belong to
    at least one of the document's groups to access it. Documents with
    an empty access_groups list are public within the organisation.
    """

    async def grant_access(
        self, document_id: str, group_name: str, *, granted_by: str | None = None, db=None
    ) -> dict[str, Any]:
        """
        Grant a group access to a document.

        Updates both the document_access_groups table and the access_groups
        array on document_embeddings for consistency.
        """
        if not db:
            raise ValueError("Database client is required")

        # 1. Insert into document_access_groups (upsert to handle duplicates)
        await (
            db.table("document_access_groups")
            .upsert(
                {
                    "document_id": document_id,
                    "group_name": group_name,
                    "granted_by": granted_by,
                    "granted_at": datetime.now(UTC).isoformat(),
                },
                on_conflict="document_id,group_name",
            )
            .execute()
        )

        # 2. Update access_groups array on document_embeddings
        # Fetch current groups, add new one if not present
        try:
            doc_result = (
                await db.table("document_embeddings")
                .select("access_groups")
                .eq("id", document_id)
                .limit(1)
                .execute()
            )
            current_groups = []
            if doc_result.data:
                current_groups = doc_result.data[0].get("access_groups") or []

            if group_name not in current_groups:
                current_groups.append(group_name)
                await (
                    db.table("document_embeddings")
                    .update({"access_groups": current_groups})
                    .eq("id", document_id)
                    .execute()
                )
        except Exception as e:
            logger.warning(f"[ACL] Failed to sync access_groups column: {e}")

        logger.info(f"[ACL] Granted group '{group_name}' access to document {document_id}")
        return {"document_id": document_id, "group_name": group_name, "action": "granted"}

    async def revoke_access(
        self, document_id: str, group_name: str, *, db=None
    ) -> dict[str, Any]:
        """
        Revoke a group's access to a document.
        """
        if not db:
            raise ValueError("Database client is required")

        # 1. Delete from document_access_groups
        await (
            db.table("document_access_groups")
            .delete()
            .eq("document_id", document_id)
            .eq("group_name", group_name)
            .execute()
        )

        # 2. Update access_groups array on document_embeddings
        try:
            doc_result = (
                await db.table("document_embeddings")
                .select("access_groups")
                .eq("id", document_id)
                .limit(1)
                .execute()
            )
            current_groups = []
            if doc_result.data:
                current_groups = doc_result.data[0].get("access_groups") or []

            if group_name in current_groups:
                current_groups.remove(group_name)
                await (
                    db.table("document_embeddings")
                    .update({"access_groups": current_groups})
                    .eq("id", document_id)
                    .execute()
                )
        except Exception as e:
            logger.warning(f"[ACL] Failed to sync access_groups column: {e}")

        logger.info(f"[ACL] Revoked group '{group_name}' access from document {document_id}")
        return {"document_id": document_id, "group_name": group_name, "action": "revoked"}

    async def check_access(
        self, user_id: str, document_id: str, *, db=None
    ) -> bool:
        """
        Check if a user has access to a specific document.

        Returns True if:
        - Document has no access restrictions (empty access_groups)
        - User belongs to at least one group in the document's access_groups
        """
        if not db:
            return False

        try:
            # Use the database function for consistent logic
            result = await db.rpc(
                "check_document_access",
                {"p_user_id": user_id, "p_document_id": document_id},
            ).execute()

            if result.data is not None:
                return bool(result.data)
        except Exception as e:
            logger.warning(f"[ACL] RPC check_document_access failed, falling back: {e}")

            # Fallback: manual check
            try:
                doc_result = (
                    await db.table("document_embeddings")
                    .select("access_groups")
                    .eq("id", document_id)
                    .limit(1)
                    .execute()
                )
                if not doc_result.data:
                    return False

                groups = doc_result.data[0].get("access_groups") or []
                if not groups:
                    return True  # No restrictions

                # Check user's groups
                user_groups_result = (
                    await db.table("user_group_memberships")
                    .select("group_name")
                    .eq("user_id", user_id)
                    .execute()
                )
                user_groups = {r["group_name"] for r in (user_groups_result.data or [])}
                return bool(user_groups & set(groups))
            except Exception as e2:
                logger.warning(f"[ACL] Fallback check failed: {e2}")
                return True  # Fail open within org

        return False

    async def list_accessible_documents(
        self, user_id: str, *, db=None, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """
        List documents accessible to a user.

        Returns documents where:
        - access_groups is empty (public)
        - OR user belongs to one of the document's groups
        """
        if not db:
            return []

        try:
            # Get user's groups first
            user_groups: list[str] = []
            try:
                ug_result = (
                    await db.table("user_group_memberships")
                    .select("group_name")
                    .eq("user_id", user_id)
                    .execute()
                )
                user_groups = [r["group_name"] for r in (ug_result.data or [])]
            except Exception:
                pass  # Table may not exist

            # Query documents: public OR matching groups
            # Using overlaps filter for array intersection
            query = (
                db.table("document_embeddings")
                .select("id, metadata, access_groups, created_at")
                .order("created_at", desc=True)
                .range(offset, offset + limit - 1)
            )

            result = await query.execute()
            documents = []
            for doc in (result.data or []):
                doc_groups = doc.get("access_groups") or []
                # Include if public or user has matching group
                if not doc_groups or (user_groups and set(user_groups) & set(doc_groups)):
                    documents.append(doc)

            return documents
        except Exception as e:
            logger.error(f"[ACL] list_accessible_documents failed: {e}")
            return []


# Global singleton
document_acl_service = DocumentACLService()
