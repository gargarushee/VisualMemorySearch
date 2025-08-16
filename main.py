import os
import sys
import uuid
import time
import asyncio
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from database import DatabaseManager, init_db
from models import SearchRequest, SearchResult, UploadResponse, ProcessingStatus
from services.image_processor import ImageProcessor
from services.search_service import SearchService
from services.file_manager import FileManager

app = FastAPI(title="Visual Memory Search", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Initialize services
db_manager = DatabaseManager()
image_processor = ImageProcessor()
search_service = SearchService(db_manager)
file_manager = FileManager()

# Background processing jobs
processing_jobs = {}

@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup."""
    init_db()
    print("Visual Memory Search API started successfully")

@app.get("/")
async def root():
    """Serve the main application."""
    return FileResponse("static/index.html")

@app.post("/api/screenshots/upload", response_model=UploadResponse)
async def upload_screenshots(files: List[UploadFile] = File(...)):
    """Upload and process screenshot files."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    
    job_id = str(uuid.uuid4())
    processed_count = 0
    failed_count = 0
    
    # Initialize job status
    processing_jobs[job_id] = {
        "status": "processing",
        "progress": 0,
        "total": len(files),
        "processed_files": []
    }
    
    # Store job in database
    db_manager.create_processing_job(job_id, len(files))
    
    # Process files in background
    asyncio.create_task(process_files_background(job_id, files))
    
    return UploadResponse(
        message=f"Started processing {len(files)} screenshots",
        processed_count=0,
        failed_count=0,
        job_id=job_id
    )

async def process_files_background(job_id: str, files: List[UploadFile]):
    """Process uploaded files in the background."""
    processed_count = 0
    failed_count = 0
    
    for i, file in enumerate(files):
        try:
            # Validate file type
            if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                failed_count += 1
                continue
            
            # Save file
            file_path = await file_manager.save_screenshot(file)
            screenshot_id = str(uuid.uuid4())
            
            # Store initial record
            db_manager.create_screenshot(
                screenshot_id=screenshot_id,
                filename=file.filename,
                file_path=file_path
            )
            
            # Process image (OCR + visual description)
            try:
                ocr_text = image_processor.extract_text(file_path)
                visual_description = await image_processor.generate_description(file_path)
                
                # Create embeddings
                text_embedding = image_processor.create_embeddings(f"{ocr_text} {visual_description}")
                
                # Update record with processed data
                db_manager.update_screenshot_processing(
                    screenshot_id=screenshot_id,
                    ocr_text=ocr_text,
                    visual_description=visual_description,
                    text_embedding=text_embedding
                )
                
                processed_count += 1
                
            except Exception as e:
                print(f"Error processing {file.filename}: {str(e)}")
                failed_count += 1
                
        except Exception as e:
            print(f"Error handling file {file.filename}: {str(e)}")
            failed_count += 1
        
        # Update progress
        progress = i + 1
        processing_jobs[job_id]["progress"] = progress
        db_manager.update_processing_job_progress(job_id, progress)
    
    # Mark job as completed
    processing_jobs[job_id]["status"] = "completed"
    db_manager.complete_processing_job(job_id)
    
    print(f"Job {job_id} completed: {processed_count} processed, {failed_count} failed")

@app.get("/api/screenshots/status/{job_id}", response_model=ProcessingStatus)
async def get_processing_status(job_id: str):
    """Get processing status for a job."""
    if job_id not in processing_jobs:
        # Try to get from database
        job = db_manager.get_processing_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return ProcessingStatus(
            status=job["status"],
            progress=job["progress"],
            total=job["total"]
        )
    
    job = processing_jobs[job_id]
    return ProcessingStatus(
        status=job["status"],
        progress=job["progress"],
        total=job["total"]
    )

@app.post("/api/screenshots/search")
async def search_screenshots(request: SearchRequest):
    """Search screenshots using natural language query."""
    start_time = time.time()
    
    try:
        results = await search_service.hybrid_search(request.query, request.limit or 5)
        query_time_ms = int((time.time() - start_time) * 1000)
        
        return {
            "results": results,
            "total_searched": len(db_manager.get_all_processed_screenshots()),
            "query_time_ms": query_time_ms
        }
    except Exception as e:
        print(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/api/screenshots")
async def get_all_screenshots():
    """Get all uploaded screenshots."""
    screenshots = db_manager.get_all_screenshots()
    
    return {
        "screenshots": [
            {
                "id": s["id"],
                "filename": s["filename"],
                "upload_date": s["upload_date"],
                "processed": bool(s["processed"]),
                "preview_url": f"/uploads/{os.path.basename(s['file_path'])}"
            }
            for s in screenshots
        ],
        "total": len(screenshots)
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
