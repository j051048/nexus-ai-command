from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from app.services.etl_service import etl_service
from app.core.database import supabase
from typing import List, Optional

router = APIRouter(prefix="/api/documents", tags=["Documents"])

@router.post("/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    userId: Optional[str] = Form(None)
):
    """
    Upload files to the Knowledge Base (ETL Pipeline).
    """
    # Fetch user specific AI settings if userId is provided
    api_key = None
    base_url = None
    
    if userId:
        try:
            user_settings = supabase.table("ai_settings").select("*").eq("user_id", userId).maybe_single().execute()
            if user_settings.data:
                api_key = user_settings.data.get("api_key")
                base_url = user_settings.data.get("base_url")
        except Exception as e:
            print(f"Failed to fetch user settings for upload: {e}")

    results = []
    for file in files:
        try:
            result = await etl_service.process_file(file, api_key=api_key, base_url=base_url)
            results.append(result)
        except Exception as e:
            results.append({"filename": file.filename, "status": "error", "reason": str(e)})
            
    return {"summary": f"Processed {len(files)} files", "details": results}
