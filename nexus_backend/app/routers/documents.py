import hashlib
import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.dependencies import require_role
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


@router.get("", response_model=StandardResponse)
async def list_documents(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """List all documents for current user."""
    client = req.state.db
    try:
        result = await client.table("documents").select("*").order("created_at", desc=True).execute()
        return api_success(data={"documents": result.data or []})
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取文档列表失败")


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
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "删除失败")


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
        "tender",
        "bid",
        "proposal",
        "invoice",
        "legal",
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

            if len(content) > 50 * 1024 * 1024:
                results.append({"filename": file.filename, "status": "error", "reason": "文件大小超过50MB限制"})
                continue

            # P1 Fix #20: Multi-level deduplication (hash + title similarity)
            content_hash = etl_service.compute_content_hash(content)
            existing_doc = await etl_service.check_duplicate(content_hash, user_id, org_id=org_id, filename=filename)

            if existing_doc:
                dedup_reason = existing_doc.get("dedup_reason", "exact_hash")
                reason_text = {
                    "exact_hash_same_user": "文件内容完全相同",
                    "exact_hash_org": "组织内已有相同内容的文档",
                    "title_exact": "同名文档已存在",
                }.get(dedup_reason, "相似文档已存在")
                if dedup_reason.startswith("title_similar"):
                    reason_text = f"与已有文档「{existing_doc.get('name', '未知')}」高度相似"
                skipped_count += 1
                results.append(
                    {
                        "filename": filename,
                        "status": "duplicate",
                        "existing_document_id": existing_doc["id"],
                        "existing_document_name": existing_doc.get("name", ""),
                        "dedup_reason": dedup_reason,
                        "message": f"{reason_text}（{existing_doc.get('name', '未知')}），已跳过。",
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
            results.append({"filename": file.filename, "status": "error", "reason": "文件处理失败"})

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

            # Multi-level deduplication
            content_hash = etl_service.compute_content_hash(content)
            existing_doc = await etl_service.check_duplicate(
                content_hash, user_id, org_id=org_id, filename=file.filename
            )

            if existing_doc:
                dedup_reason = existing_doc.get("dedup_reason", "exact_hash")
                results.append(
                    {
                        "filename": file.filename,
                        "status": "duplicate",
                        "existing_document_id": existing_doc["id"],
                        "dedup_reason": dedup_reason,
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
            results.append({"filename": file.filename, "status": "error", "reason": "文件处理失败"})

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
    await (
        client.table("documents")
        .update(
            {
                "name": file.filename,
                "file_size": len(content),
                "version": version,
                "status": "processing",
                "updated_at": "now()",
            }
        )
        .eq("id", document_id)
        .execute()
    )

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
    doc_type: Literal["contract", "tender", "bid", "product", "proposal", "invoice", "legal", "other"] = Field(
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
        res = await client.table("documents").update({"doc_type": body.doc_type}).eq("id", document_id).execute()
        if not res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "文档不存在")

        logger.info(f"User {user_id} updated doc {document_id} category to {body.doc_type}")
        return api_success(data={"document_id": document_id, "doc_type": body.doc_type}, message="分类已更新")
    except Exception as e:
        logger.error(f"Update category failed: doc={document_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "更新分类失败")


# ============== Bulk Import Endpoint ==============

# Role check dependency: admin / founder / boss only
require_kb_admin = require_role(["admin", "founder", "boss"])


class BulkImportDocumentItem(BaseModel):
    """Single document in a bulk import request."""

    title: str = Field(..., min_length=1, max_length=500, description="文档标题（将用作文件名）")
    content: str = Field(..., min_length=10, description="文档正文内容")
    doc_type: Literal["contract", "tender", "bid", "product", "proposal", "invoice", "legal", "other"] = Field(
        default="other", description="文档分类"
    )
    library_code: str | None = Field(default=None, description="目标知识库编码（如 product_lib）")
    tags: list[str] = Field(default_factory=list, description="文档标签")
    visibility: Literal["private", "department", "organization"] = Field(default="organization", description="可见性")


class BulkImportRequest(BaseModel):
    """Bulk import request body."""

    documents: list[BulkImportDocumentItem] = Field(
        ..., min_length=1, max_length=50, description="文档列表（最多50条）"
    )


@router.post("/bulk-import", response_model=StandardResponse)
async def bulk_import_documents(
    payload: BulkImportRequest,
    req: Request,
    user_id: str = Depends(require_kb_admin),
):
    """
    批量导入知识库文档（管理员专用）。

    接收 JSON 数组，为每个条目创建 documents 记录。
    不触发 AI 解析或 Embedding 生成（适用于预置的知识库内容）。
    需要 admin / founder / boss 角色。
    """
    from app.core.database import supabase as global_supabase

    client = getattr(req.state, "db", global_supabase)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库服务不可用")

    org_id = getattr(req.state, "org_id", None)

    # Prefetch library code -> id mapping
    library_map: dict[str, int] = {}
    try:
        lib_res = await client.table("knowledge_library").select("id, library_code").execute()
        if lib_res.data:
            library_map = {row["library_code"]: row["id"] for row in lib_res.data}
    except Exception as e:
        logger.warning(f"Failed to fetch knowledge libraries: {e}")

    results = []
    success_count = 0
    skip_count = 0
    error_count = 0

    for item in payload.documents:
        try:
            # Dedup by content hash
            content_bytes = item.content.encode("utf-8")
            content_hash = hashlib.sha256(content_bytes).hexdigest()

            # Check if document with same name already exists (idempotent)
            existing = await client.table("documents").select("id, name").eq("name", item.title).limit(1).execute()
            if existing.data and len(existing.data) > 0:
                skip_count += 1
                results.append(
                    {
                        "title": item.title,
                        "status": "skipped",
                        "existing_id": existing.data[0]["id"],
                        "message": "同名文档已存在",
                    }
                )
                continue

            # Build extracted_data
            extracted_data = {
                "doc_type": item.doc_type,
                "tags": item.tags,
                "full_text_context": item.content[:100000],
            }

            # Resolve library_id
            library_id = library_map.get(item.library_code) if item.library_code else None

            record = {
                "name": item.title,
                "doc_type": item.doc_type,
                "version": 1,
                "extracted_data": extracted_data,
                "owner_id": user_id,
                "status": "ready",
                "progress": 100,
                "stage": "completed",
                "visibility": item.visibility,
                "content_hash": content_hash,
                "organization_id": org_id,
                "category": item.doc_type,
            }

            if library_id:
                record["library_id"] = library_id

            res = await client.table("documents").insert(record).execute()
            if res.data:
                doc_id = res.data[0]["id"]
                success_count += 1
                results.append(
                    {
                        "title": item.title,
                        "status": "created",
                        "document_id": doc_id,
                        "library_id": library_id,
                    }
                )
            else:
                error_count += 1
                results.append(
                    {
                        "title": item.title,
                        "status": "error",
                        "message": "数据库未返回记录",
                    }
                )

        except Exception as e:
            error_count += 1
            logger.error(f"Bulk import failed for '{item.title}': {e}")
            results.append(
                {
                    "title": item.title,
                    "status": "error",
                    "message": "文件处理失败",
                }
            )

    # Update library doc_count for affected libraries
    # 使用 admin client: knowledge_library 的 RLS 依赖 app.current_org_id session 变量
    from app.core.database import supabase as admin_client

    affected_codes = {item.library_code for item in payload.documents if item.library_code}
    for code in affected_codes:
        lib_id = library_map.get(code)
        if lib_id:
            try:
                count_res = await (admin_client or client).table("documents").select("id").eq("library_id", lib_id).execute()
                doc_count = len(count_res.data) if count_res.data else 0
                await (admin_client or client).table("knowledge_library").update({"doc_count": doc_count}).eq("id", lib_id).execute()
            except Exception as e:
                logger.warning(f"Failed to update doc_count for library {code}: {e}")

    logger.info(f"Bulk import by user {user_id}: {success_count} created, {skip_count} skipped, {error_count} errors")

    return api_success(
        data={
            "total": len(payload.documents),
            "success_count": success_count,
            "skip_count": skip_count,
            "error_count": error_count,
            "results": results,
        },
        message=f"批量导入完成: {success_count} 成功, {skip_count} 跳过, {error_count} 失败",
    )


@router.get("/libraries", response_model=StandardResponse)
async def list_knowledge_libraries(
    req: Request,
    _user_id: str = Depends(get_current_user_id),
):
    """获取所有知识库分类及其文档计数"""
    from app.core.database import supabase as global_supabase

    # knowledge_library 的 RLS 依赖 app.current_org_id，scoped client 无法读取
    client = global_supabase
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库服务不可用")

    try:
        res = (
            await client.table("knowledge_library")
            .select("id, library_code, library_name, description, access_level, doc_count, is_active")
            .eq("is_active", True)
            .order("id")
            .execute()
        )
        libraries = res.data if res.data else []
        return api_success(data=libraries, message=f"共 {len(libraries)} 个知识库")
    except Exception as e:
        logger.error(f"Failed to list knowledge libraries: {e}")
        raise api_error(ErrorCode.DB_QUERY_ERROR, "获取知识库列表失败")


@router.post("/admin/re-embed", response_model=StandardResponse)
async def trigger_re_embed(
    background_tasks: BackgroundTasks,
    req: Request,
    user_id: str = Depends(get_current_user_id),
    _=Depends(require_role("admin")),
):
    """
    Trigger incremental re-embedding for documents still using old embedding model.
    Runs in background — returns immediately with count of queued documents.
    """
    from app.core.database import supabase as global_supabase
    from app.services.vector_service import EMBEDDING_MODEL, vector_service

    client = getattr(req.state, "db", global_supabase)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库服务不可用")

    try:
        # Find documents with outdated embeddings
        res = (
            await client.table("document_embeddings")
            .select("document_id")
            .neq("embedding_model", EMBEDDING_MODEL)
            .limit(500)
            .execute()
        )
        doc_ids = list({row["document_id"] for row in (res.data or []) if row.get("document_id")})

        if not doc_ids:
            return api_success(data={"queued": 0}, message="所有文档已使用最新嵌入模型")

        async def _re_embed_docs(document_ids: list[str]):
            # Batch query: fetch all documents in one call instead of N+1
            try:
                docs_res = (
                    await global_supabase.table("documents")
                    .select("id, organization_id")
                    .in_("id", document_ids)
                    .execute()
                )
                doc_org_map = {d["id"]: d.get("organization_id", "default") for d in (docs_res.data or [])}
            except Exception as e:
                logger.error(f"Batch doc fetch failed: {e}")
                return

            # Batch query: fetch all chunks in one call
            try:
                chunks_res = (
                    await global_supabase.table("document_embeddings")
                    .select("document_id, content")
                    .in_("document_id", document_ids)
                    .execute()
                )
                chunks_by_doc: dict[str, list[str]] = {}
                for row in chunks_res.data or []:
                    if row.get("content") and row.get("document_id"):
                        chunks_by_doc.setdefault(row["document_id"], []).append(row["content"])
            except Exception as e:
                logger.error(f"Batch chunks fetch failed: {e}")
                return

            # Process each doc with pre-fetched data
            for doc_id in document_ids:
                try:
                    org_id = doc_org_map.get(doc_id)
                    if not org_id:
                        continue
                    chunks = chunks_by_doc.get(doc_id, [])
                    if chunks:
                        await vector_service.incremental_update(doc_id, chunks, org_id)
                except Exception as e:
                    logger.error(f"Re-embed failed for doc {doc_id}: {e}")

        background_tasks.add_task(_re_embed_docs, doc_ids)
        return api_success(data={"queued": len(doc_ids)}, message=f"已排队 {len(doc_ids)} 个文档进行重新嵌入")
    except Exception as e:
        logger.error(f"Failed to trigger re-embed: {e}")
        raise api_error(ErrorCode.DB_QUERY_ERROR, "触发重新嵌入失败")
