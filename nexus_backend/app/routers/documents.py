from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.etl_service import etl_service
from typing import List

router = APIRouter(prefix="/api/documents", tags=["Documents"])

@router.post("/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    """
    Upload files to the Knowledge Base (ETL Pipeline).
    Supports PDF, CSV, Excel, TXT, MD.
    Currently runs Extraction & Chunking, but Vector Loading is mocked.
    """
    results = []
    for file in files:
        try:
            result = await etl_service.process_file(file)
            results.append(result)
        except Exception as e:
            results.append({"filename": file.filename, "status": "error", "message": str(e)})
            
    return {"summary": f"Processed {len(files)} files", "details": results}
