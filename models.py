from pydantic import BaseModel
from typing import List, Optional

class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 5

class SearchResult(BaseModel):
    id: str
    filename: str
    confidence_score: float
    preview_url: str
    ocr_text: str
    visual_description: str
    matched_elements: List[str]

class UploadResponse(BaseModel):
    message: str
    processed_count: int
    failed_count: int
    job_id: str

class ProcessingStatus(BaseModel):
    status: str  # "processing" | "completed" | "failed"
    progress: int
    total: int

class Screenshot(BaseModel):
    id: str
    filename: str
    upload_date: str
    processed: bool
    preview_url: str
