import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.models.schemas import BatchDeleteRequest, StandardResponse
from app.services.etl_service import etl_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documents"])


def _is_postgrest_204(e: Exception) -> bool:
    """Check if exception is a PostgREST 204 No Content (success, no body)."""
    return hasattr(e, "code") and str(getattr(e, "code", "")) == "204"


def _is_jwt_expired(e: Exception) -> bool:
    """Check if exception is a PostgREST JWT expired error."""
    msg = str(e)
    return "JWT expired" in msg or "PGRST303" in msg


@router.post("/batch-delete", response_model=StandardResponse)
async def batch_delete_documents(
    payload: BatchDeleteRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Batch delete documents. Embeddings are auto-cleaned via CASCADE DELETE.
    Falls back to global (service-key) client if scoped client fails due to
    missing organization_id on legacy documents.
    """
    if not payload.document_ids:
        return api_success(data={"deleted_count": 0})

    from app.core.database import supabase as global_supabase

    client = req.state.db
    count = 0

    try:
        # With CASCADE DELETE on FK, only need to delete documents.
        # Embeddings are automatically cleaned up by PostgreSQL.
        try:
            res = await client.table("documents").delete().in_("id", payload.document_ids).execute()
            count = len(res.data) if res and res.data else 0
        except Exception as e:
            if _is_postgrest_204(e):
                count = len(payload.document_ids)
            elif _is_jwt_expired(e):
                raise
            else:
                # Fallback: use global (service-key) client for legacy docs
                # where org_id was NULL and RLS blocks the scoped delete
                logger.warning(f"Scoped delete failed ({e}), trying service client...")
                if global_supabase:
                    try:
                        res = (
                            await global_supabase.table("documents").delete().in_("id", payload.document_ids).execute()
                        )
                        count = len(res.data) if res and res.data else 0
                    except Exception as fallback_e:
                        if _is_postgrest_204(fallback_e):
                            count = len(payload.document_ids)
                        else:
                            raise fallback_e
                else:
                    raise

        logger.info(f"User {user_id} deleted {count} documents (cascade cleaned embeddings).")
        return api_success(data={"deleted_count": count})

    except Exception as e:
        if _is_jwt_expired(e):
            raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "登录已过期，请刷新页面后重试")
        logger.error(f"Batch Delete Failed for user {user_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, f"删除失败: {str(e)}")


@router.post("/upload", response_model=StandardResponse)
async def upload_documents(
    background_tasks: BackgroundTasks,
    req: Request,
    files: list[UploadFile] = File(...),
    visibility: str = Form(default="organization"),
    category: str = Form(default="other"),
    user_id: str = Depends(get_current_user_id),
):
    """
    Upload files to the Knowledge Base (ETL Pipeline).
    Queues regular files for background processing.
    """
    api_key = None
    base_url = None
    user_department = None
    client = req.state.db
    org_id = getattr(req.state, "org_id", None)

    # 1. Validate visibility and category parameters
    if visibility not in ("private", "department", "organization"):
        visibility = "organization"

    if category not in (
        "regulation",
        "manual",
        "contract",
        "training",
        "product",
        "bid",
        "proposal",
        "invoice",
        "other",
    ):
        category = "other"

    if user_id:
        try:
            # Fetch user settings and department
            user_settings = (
                await client.table("ai_settings").select("*").eq("user_id", user_id).maybe_single().execute()
            )
            if user_settings.data:
                api_key = user_settings.data.get("api_key")
                base_url = user_settings.data.get("base_url")

            user_data = await client.table("users").select("department").eq("id", user_id).maybe_single().execute()
            if user_data.data:
                user_department = user_data.data.get("department")
        except Exception as e:
            logger.warning(f"Failed to fetch user context for upload: {e}")

    results = []
    processed_count = 0
    skipped_count = 0

    for file in files:
        try:
            content = await file.read()
            filename = file.filename

            # P1 Fix #20: Content hash deduplication
            content_hash = etl_service.compute_content_hash(content)
            existing_doc = await etl_service.check_duplicate(content_hash, user_id)

            if existing_doc:
                skipped_count += 1
                results.append(
                    {
                        "filename": filename,
                        "status": "duplicate",
                        "existing_document_id": existing_doc["id"],
                        "existing_document_name": existing_doc.get("name", ""),
                        "message": f"文件内容与已有文档重复（{existing_doc.get('name', '未知')}），已跳过。",
                    }
                )
                continue

            # Step 1: Create Initial DB Record (with content hash)
            doc_id = await etl_service.create_initial_record(
                filename,
                user_id,
                visibility=visibility,
                department=user_department,
                content_hash=content_hash,
                organization_id=org_id,
            )

            # Step 2: Trigger Background Processing
            background_tasks.add_task(
                etl_service.process_file,
                content=content,
                filename=filename,
                doc_id=doc_id,
                api_key=api_key,
                base_url=base_url,
                user_id=user_id,
                organization_id=org_id,
            )

            results.append(
                {
                    "filename": filename,
                    "status": "pending",
                    "document_id": doc_id,
                    "visibility": visibility,
                    "message": "Processing started in background",
                }
            )
            processed_count += 1

        except Exception as e:
            logger.error(f"Upload Setup Failed for {file.filename}: {e}")
            results.append({"filename": file.filename, "status": "error", "reason": str(e)})

    summary = f"Queued {processed_count} files"
    if skipped_count > 0:
        summary += f", skipped {skipped_count} duplicates"

    return api_success(data={"summary": summary, "results": results}, message="Upload received")


@router.post("/batch-upload", response_model=StandardResponse)
async def batch_upload_documents(
    background_tasks: BackgroundTasks,
    req: Request,
    files: list[UploadFile] = File(...),
    visibility: str = Form(default="organization"),
    user_id: str = Depends(get_current_user_id),
):
    """Upload multiple documents at once (max 10 files)"""
    if len(files) > 10:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "一次最多上传 10 个文件")

    api_key = None
    base_url = None
    user_department = None
    client = req.state.db
    org_id = getattr(req.state, "org_id", None)

    if user_id:
        try:
            user_settings = (
                await client.table("ai_settings").select("*").eq("user_id", user_id).maybe_single().execute()
            )
            if user_settings.data:
                api_key = user_settings.data.get("api_key")
                base_url = user_settings.data.get("base_url")

            user_data = await client.table("users").select("department").eq("id", user_id).maybe_single().execute()
            if user_data.data:
                user_department = user_data.data.get("department")
        except Exception as e:
            logger.warning(f"Failed to fetch user context: {e}")

    results = []
    for file in files:
        try:
            # Validate file type
            allowed_extensions = [".pdf", ".docx", ".txt", ".md", ".csv"]
            ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
            if ext not in allowed_extensions:
                results.append(
                    {
                        "filename": file.filename,
                        "status": "error",
                        "reason": f"不支持的文件类型: {ext}",
                    }
                )
                continue

            # Read content
            content = await file.read()
            if len(content) > 50 * 1024 * 1024:  # 50MB limit per file
                results.append(
                    {
                        "filename": file.filename,
                        "status": "error",
                        "reason": "文件超过 50MB 限制",
                    }
                )
                continue

            # Check for duplicates
            content_hash = etl_service.compute_content_hash(content)
            existing_doc = await etl_service.check_duplicate(content_hash, user_id)

            if existing_doc:
                results.append(
                    {
                        "filename": file.filename,
                        "status": "duplicate",
                        "existing_document_id": existing_doc["id"],
                        "message": f"文件与已有文档重复：{existing_doc.get('name', '未知')}",
                    }
                )
                continue

            # Create document record
            doc_id = await etl_service.create_initial_record(
                file.filename,
                user_id,
                visibility=visibility,
                department=user_department,
                content_hash=content_hash,
                organization_id=org_id,
            )

            # Queue background processing
            background_tasks.add_task(
                etl_service.process_file,
                content=content,
                filename=file.filename,
                doc_id=doc_id,
                api_key=api_key,
                base_url=base_url,
                user_id=user_id,
                organization_id=org_id,
            )

            results.append(
                {
                    "filename": file.filename,
                    "status": "uploaded",
                    "document_id": doc_id,
                    "size": len(content),
                }
            )
        except Exception as e:
            logger.error(f"Failed to upload {file.filename}: {e}")
            results.append({"filename": file.filename, "status": "error", "reason": str(e)[:100]})

    success_count = sum(1 for r in results if r["status"] == "uploaded")
    error_count = sum(1 for r in results if r["status"] == "error")

    return api_success(
        data={
            "total": len(files),
            "success_count": success_count,
            "error_count": error_count,
            "results": results,
        },
        message="批量上传完成",
    )


@router.put("/{document_id}/update", response_model=StandardResponse)
async def update_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    req: Request,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Update an existing document (creates new version, replaces old embeddings)"""
    client = req.state.db

    # 1. Verify document ownership
    doc_res = (
        await client.table("documents")
        .select("*")
        .eq("id", document_id)
        .eq("owner_id", user_id)
        .maybe_single()
        .execute()
    )
    if not doc_res.data:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "文档不存在或无权限")

    # 2. Delete old embeddings
    try:
        await client.table("document_embeddings").delete().eq("document_id", document_id).execute()
    except Exception as e:
        if not _is_postgrest_204(e):
            logger.warning(f"Failed to delete old embeddings: {e}")

    # 3. Read new content
    content = await file.read()

    # 4. Update document metadata
    version = (doc_res.data.get("version", 1) or 1) + 1
    await client.table("documents").update(
        {
            "name": file.filename,
            "file_size": len(content),
            "version": version,
            "status": "processing",
            "updated_at": "now()",
        }
    ).eq("id", document_id).execute()

    # 5. Fetch user settings for reprocessing
    api_key = None
    base_url = None
    try:
        user_settings = await client.table("ai_settings").select("*").eq("user_id", user_id).maybe_single().execute()
        if user_settings.data:
            api_key = user_settings.data.get("api_key")
            base_url = user_settings.data.get("base_url")
    except Exception as e:
        logger.warning(f"Failed to fetch user settings: {e}")

    # 6. Queue reprocessing
    org_id = getattr(req.state, "org_id", None)
    background_tasks.add_task(
        etl_service.process_file,
        content=content,
        filename=file.filename,
        doc_id=document_id,
        api_key=api_key,
        base_url=base_url,
        user_id=user_id,
        organization_id=org_id,
    )

    return api_success(
        data={
            "document_id": document_id,
            "version": version,
            "status": "processing",
            "message": f"文档已更新至第 {version} 版，正在重新处理...",
        },
        message="文档更新中",
    )


class UpdateCategoryRequest(BaseModel):
    doc_type: Literal["contract", "bid", "product", "proposal", "invoice", "other"] = Field(
        ..., description="文档分类"
    )


@router.patch("/{document_id}/category", response_model=StandardResponse)
async def update_document_category(
    document_id: str,
    body: UpdateCategoryRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """手动修改文档分类"""
    client = req.state.db
    try:
        res = (
            await client.table("documents")
            .update({"doc_type": body.doc_type})
            .eq("id", document_id)
            .execute()
        )
        if not res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "文档不存在")

        logger.info(f"User {user_id} updated doc {document_id} category to {body.doc_type}")
        return api_success(data={"document_id": document_id, "doc_type": body.doc_type}, message="分类已更新")
    except Exception as e:
        logger.error(f"Update category failed: doc={document_id} user={user_id} err={e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, f"更新分类失败: {str(e)}")
