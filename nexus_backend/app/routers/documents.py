from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks
from typing import List, Optional
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
    user_id: str = Depends(get_current_user_id)
):
    """
    Upload files to the Knowledge Base (ETL Pipeline).
    Queues regular files for background processing.
    """
    api_key = None
    base_url = None
    user_department = None
    
    # 1. Validate visibility parameter
    if visibility not in ('private', 'department', 'organization'):
        visibility = 'organization'
    
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
    
    for file in files:
        try:
            content = await file.read()
            filename = file.filename
            
            # Step 1: Create Initial DB Record
            doc_id = await etl_service.create_initial_record(
                filename, 
                user_id,
                visibility=visibility,
                department=user_department
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
            
    return api_success(
        data={"summary": f"Queued {processed_count} files", "results": results},
        message="Upload received"
    )
