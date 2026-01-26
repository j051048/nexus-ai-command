from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends
from app.services.etl_service import etl_service
from app.core.database import supabase
from app.core.auth import get_current_user_id
from typing import List, Optional

router = APIRouter(prefix="/api/documents", tags=["Documents"])

@router.post("/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Upload files to the Knowledge Base (ETL Pipeline).
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
            result = await etl_service.process_file(file, api_key=api_key, base_url=base_url, user_id=user_id)
            results.append(result)
        except Exception as e:
            results.append({"filename": file.filename, "status": "error", "reason": str(e)})
            
    return {"summary": f"Processed {len(files)} files", "details": results}
