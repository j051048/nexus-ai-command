import io
import pandas as pd
from pypdf import PdfReader
from fastapi import UploadFile
from typing import List, Dict, Any

class ETLService:
    """
    Service for Extracting, Transforming, and Loading (ETL) document data.
    Designed for the 'Phase 1' data pipeline.
    """

    @staticmethod
    async def process_file(file: UploadFile) -> Dict[str, Any]:
        """
        Main entry point: Detects file type, extracts text, chunks it,
        and prepares it for vector storage.
        """
        filename = file.filename
        content_type = file.content_type
        
        # 1. EXTRACT (提取)
        text_content = ""
        metadata = {"filename": filename, "type": content_type}
        
        file_bytes = await file.read()
        file_stream = io.BytesIO(file_bytes)

        if filename.endswith(".pdf"):
            text_content = ETLService._extract_pdf(file_stream)
        elif filename.endswith(".csv"):
            text_content = ETLService._extract_csv(file_stream)
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            text_content = ETLService._extract_excel(file_stream)
        elif filename.endswith(".txt") or filename.endswith(".md"):
            text_content = file_bytes.decode("utf-8")
        else:
            return {"status": "skipped", "message": f"Unsupported file type: {filename}"}

        # 2. TRANSFORM (清洗与切分 - Chunking)
        chunks = ETLService._chunk_text(text_content)
        
        # 3. LOAD (加载)
        # In a real scenario, this is where we call Embedding Model + Milvus Insert.
        # Since Milvus is deferred, we will return the processed chunks 
        # so the frontend or log can see them.
        
        return {
            "status": "success_mock_loaded",
            "filename": filename,
            "extracted_chars": len(text_content),
            "chunks_created": len(chunks),
            "preview_chunk": chunks[0] if chunks else "",
            "message": "File processed and chunked. Ready for Vector DB ingestion."
        }

    @staticmethod
    def _extract_pdf(file_stream) -> str:
        try:
            reader = PdfReader(file_stream)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            return f"[Error extracting PDF: {str(e)}]"

    @staticmethod
    def _extract_csv(file_stream) -> str:
        try:
            df = pd.read_csv(file_stream)
            # Convert to Markdown for better LLM readability
            return df.to_markdown(index=False)
        except Exception as e:
            return f"[Error extracting CSV: {str(e)}]"

    @staticmethod
    def _extract_excel(file_stream) -> str:
        try:
            df = pd.read_excel(file_stream)
            return df.to_markdown(index=False)
        except Exception as e:
            return f"[Error extracting Excel: {str(e)}]"

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Simple overlapping sliding window chunking.
        In production, use LangChain's RecursiveCharacterTextSplitter for smarter splits.
        """
        if not text:
            return []
            
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + chunk_size
            chunk = text[start:end]
            
            # If we cut a word in half, maybe extend a bit? (Simple implementation skips this)
            chunks.append(chunk)
            
            # Move window, respecting overlap
            start += (chunk_size - overlap)
            
        return chunks

etl_service = ETLService()
