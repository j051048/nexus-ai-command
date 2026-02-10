from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks
from typing import List
from app.services.etl_service import etl_service
from app.core.database import supabase
from app.core.auth import get_current_user_id
from app.models.schemas import BatchDeleteRequest, StandardResponse
from app.core.errors import api_success, api_error, ErrorCode
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documents"])

@router.post("/batch-delete", response_model=StandardResponse)
async def batch_delete_documents(
    payload: BatchDeleteRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Batch delete documents and their associated embeddings.
    """
    if not payload.document_ids:
        return api_success(data={"deleted_count": 0})

    try:
        # 1. Delete Embeddings (Explicit cleanup, though Cascade should usually handle it)
        await supabase.table("document_embeddings").delete().in_("document_id", payload.document_ids).execute()
        
        # 2. Delete Documents
        res = await supabase.table("documents").delete().in_("id", payload.document_ids).execute()
        
        count = len(res.data) if res.data else 0
        logger.info(f"User {user_id} deleted {count} documents.")
        
        return api_success(data={"deleted_count": count})
    except Exception as e:
        logger.error(f"Batch Delete Failed for user {user_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, f"删除失败: {str(e)}")

@router.post("/upload", response_model=StandardResponse)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    visibility: str = Form(default="organization"),
    category: str = Form(default="other"),
    user_id: str = Depends(get_current_user_id)
):
    """
    Upload files to the Knowledge Base (ETL Pipeline).
    Queues regular files for background processing.
    """
    api_key = None
    base_url = None
    user_department = None
    
    # 1. Validate visibility and category parameters
    if visibility not in ('private', 'department', 'organization'):
        visibility = 'organization'
    
    if category not in ('regulation', 'manual', 'contract', 'training', 'other'):
        category = 'other'
    
    if user_id:
        try:
            # Fetch user settings and department
            user_settings = await supabase.table("ai_settings").select("*").eq("user_id", user_id).maybe_single().execute()
            if user_settings.data:
                api_key = user_settings.data.get("api_key")
                base_url = user_settings.data.get("base_url")
            
            user_data = await supabase.table("users").select("department").eq("id", user_id).maybe_single().execute()
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
                results.append({
                    "filename": filename,
                    "status": "duplicate",
                    "existing_document_id": existing_doc["id"],
                    "existing_document_name": existing_doc.get("name", ""),
                    "message": f"文件内容与已有文档重复（{existing_doc.get('name', '未知')}），已跳过。"
                })
                continue
            
            # Step 1: Create Initial DB Record (with content hash)
            doc_id = await etl_service.create_initial_record(
                filename, 
                user_id,
                visibility=visibility,
                department=user_department,
                content_hash=content_hash
            )
            
            # Step 2: Trigger Background Processing
            background_tasks.add_task(
                etl_service.process_file,
                content=content,
                filename=filename,
                doc_id=doc_id,
                api_key=api_key,
                base_url=base_url,
                user_id=user_id
            )
            
            results.append({
                "filename": filename,
                "status": "pending",
                "document_id": doc_id,
                "visibility": visibility,
                "message": "Processing started in background"
            })
            processed_count += 1
            
        except Exception as e:
            logger.error(f"Upload Setup Failed for {file.filename}: {e}")
            results.append({"filename": file.filename, "status": "error", "reason": str(e)})
    
    summary = f"Queued {processed_count} files"
    if skipped_count > 0:
        summary += f", skipped {skipped_count} duplicates"
    
    return api_success(
        data={"summary": summary, "results": results},
        message="Upload received"
    )

@router.post("/batch-upload", response_model=StandardResponse)
async def batch_upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    visibility: str = Form(default="organization"),
    user_id: str = Depends(get_current_user_id)
):
    """Upload multiple documents at once (max 10 files)"""
    if len(files) > 10:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "一次最多上传 10 个文件")
    
    api_key = None
    base_url = None
    user_department = None
    
    if user_id:
        try:
            user_settings = await supabase.table("ai_settings").select("*").eq("user_id", user_id).maybe_single().execute()
            if user_settings.data:
                api_key = user_settings.data.get("api_key")
                base_url = user_settings.data.get("base_url")
            
            user_data = await supabase.table("users").select("department").eq("id", user_id).maybe_single().execute()
            if user_data.data:
                user_department = user_data.data.get("department")
        except Exception as e:
            logger.warning(f"Failed to fetch user context: {e}")
    
    results = []
    for file in files:
        try:
            # Validate file type
            allowed_extensions = ['.pdf', '.docx', '.txt', '.md', '.csv']
            ext = '.' + file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            if ext not in allowed_extensions:
                results.append({"filename": file.filename, "status": "error", "reason": f"不支持的文件类型: {ext}"})
                continue
            
            # Read content
            content = await file.read()
            if len(content) > 50 * 1024 * 1024:  # 50MB limit per file
                results.append({"filename": file.filename, "status": "error", "reason": "文件超过 50MB 限制"})
                continue
            
            # Check for duplicates
            content_hash = etl_service.compute_content_hash(content)
            existing_doc = await etl_service.check_duplicate(content_hash, user_id)
            
            if existing_doc:
                results.append({
                    "filename": file.filename,
                    "status": "duplicate",
                    "existing_document_id": existing_doc["id"],
                    "message": f"文件与已有文档重复：{existing_doc.get('name', '未知')}"
                })
                continue
            
            # Create document record
            doc_id = await etl_service.create_initial_record(
                file.filename,
                user_id,
                visibility=visibility,
                department=user_department,
                content_hash=content_hash
            )
            
            # Queue background processing
            background_tasks.add_task(
                etl_service.process_file,
                content=content,
                filename=file.filename,
                doc_id=doc_id,
                api_key=api_key,
                base_url=base_url,
                user_id=user_id
            )
            
            results.append({
                "filename": file.filename,
                "status": "uploaded",
                "document_id": doc_id,
                "size": len(content)
            })
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
            "results": results
        },
        message="批量上传完成"
    )

@router.put("/{document_id}/update", response_model=StandardResponse)
async def update_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id)
):
    """Update an existing document (creates new version, replaces old embeddings)"""
    
    # 1. Verify document ownership
    doc_res = await supabase.table("documents").select("*").eq("id", document_id).eq("owner_id", user_id).maybe_single().execute()
    if not doc_res.data:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "文档不存在或无权限")
    
    # 2. Delete old embeddings
    try:
        await supabase.table("document_embeddings").delete().eq("document_id", document_id).execute()
    except Exception as e:
        logger.warning(f"Failed to delete old embeddings: {e}")
    
    # 3. Read new content
    content = await file.read()
    
    # 4. Update document metadata
    version = (doc_res.data.get("version", 1) or 1) + 1
    await supabase.table("documents").update({
        "name": file.filename,
        "file_size": len(content),
        "version": version,
        "status": "processing",
        "updated_at": "now()"
    }).eq("id", document_id).execute()
    
    # 5. Fetch user settings for reprocessing
    api_key = None
    base_url = None
    try:
        user_settings = await supabase.table("ai_settings").select("*").eq("user_id", user_id).maybe_single().execute()
        if user_settings.data:
            api_key = user_settings.data.get("api_key")
            base_url = user_settings.data.get("base_url")
    except Exception as e:
        logger.warning(f"Failed to fetch user settings: {e}")
    
    # 6. Queue reprocessing
    background_tasks.add_task(
        etl_service.process_file,
        content=content,
        filename=file.filename,
        doc_id=document_id,
        api_key=api_key,
        base_url=base_url,
        user_id=user_id
    )
    
    return api_success(
        data={
            "document_id": document_id,
            "version": version,
            "status": "processing",
            "message": f"文档已更新至第 {version} 版，正在重新处理..."
        },
        message="文档更新中"
    )
