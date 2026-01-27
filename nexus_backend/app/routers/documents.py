from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends, BackgroundTasks
from app.services.etl_service import etl_service
from app.core.database import supabase
from app.core.auth import get_current_user_id
from typing import List, Optional

router = APIRouter(prefix="/api/documents", tags=["Documents"])

@router.post("/upload")
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Upload files to the Knowledge Base (ETL Pipeline).
    Now returns immediately with a task ID for progress tracking.
    """
    api_key = None
    base_url = None
    
    if user_id:
        try:
            user_settings = await supabase.table("ai_settings").select("*").eq("user_id", user_id).maybe_single().execute()
            if user_settings.data:
                api_key = user_settings.data.get("api_key")
                base_url = user_settings.data.get("base_url")
        except Exception as e:
            print(f"Failed to fetch user settings for upload: {e}")

    results = []
    for file in files:
        try:
            # P1: Read file content immediately as UploadFile is closed after request context
            content = await file.read()
            filename = file.filename
            
            # Step 1: Create Initial DB Record
            doc_id = await etl_service.create_initial_record(filename, user_id)
            
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
                "message": "Processing started in background"
            })
            
        except Exception as e:
            print(f"Upload Setup Failed: {e}")
            results.append({"filename": file.filename, "status": "error", "reason": str(e)})
            
    return {"summary": f"Queued {len(files)} files", "results": results}
