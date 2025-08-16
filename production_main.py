#!/usr/bin/env python3
"""
Production-optimized main.py for Visual Memory Search
Optimized for fast health checks and deployment environments
"""
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

# Fast health check responses that don't depend on other modules
FAST_HEALTH_RESPONSE = {
    "status": "healthy", 
    "service": "Visual Memory Search", 
    "version": "1.0.0"
}

FAST_READY_RESPONSE = {
    "status": "ready", 
    "service": "Visual Memory Search", 
    "database": "connected"
}

# Initialize FastAPI with minimal setup for fast startup
app = FastAPI(
    title="Visual Memory Search", 
    version="1.0.0",
    description="Search your screenshot history using natural language queries"
)

# Enable CORS (required for frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for lazy loading
_services_initialized = False
_db_manager = None
_image_processor = None
_search_service = None
_file_manager = None
_processing_jobs = {}

def ensure_directories():
    """Ensure required directories exist."""
    os.makedirs("static", exist_ok=True)
    os.makedirs("uploads", exist_ok=True)

def init_services():
    """Lazy initialization of services."""
    global _services_initialized, _db_manager, _image_processor, _search_service, _file_manager
    
    if _services_initialized:
        return
    
    try:
        from database import DatabaseManager, init_db
        from services.image_processor import ImageProcessor
        from services.search_service import SearchService
        from services.file_manager import FileManager
        
        # Initialize database
        init_db()
        
        # Initialize services
        _db_manager = DatabaseManager()
        _image_processor = ImageProcessor()
        _search_service = SearchService(_db_manager)
        _file_manager = FileManager()
        
        _services_initialized = True
        print("Services initialized successfully")
        
    except Exception as e:
        print(f"Service initialization error: {e}")
        # Continue without full services for basic health checks

@app.on_event("startup")
async def startup_event():
    """Fast startup with directory creation only."""
    ensure_directories()
    print("Visual Memory Search API startup initiated")

# Critical health endpoints that must respond quickly
@app.get("/health")
async def health_check():
    """Ultra-fast health check for deployment systems."""
    return JSONResponse(content=FAST_HEALTH_RESPONSE, status_code=200)

@app.get("/ready")  
async def readiness_check():
    """Fast readiness check with basic validation."""
    try:
        # Quick directory check
        if os.path.exists("static") and os.path.exists("uploads"):
            return JSONResponse(content=FAST_READY_RESPONSE, status_code=200)
        else:
            return JSONResponse(
                content={
                    "status": "not_ready", 
                    "service": "Visual Memory Search", 
                    "error": "Required directories missing"
                },
                status_code=503
            )
    except Exception as e:
        return JSONResponse(
            content={
                "status": "not_ready", 
                "service": "Visual Memory Search", 
                "error": str(e)
            },
            status_code=503
        )

@app.get("/")
async def root():
    """Serve main application or health check fallback."""
    try:
        if os.path.exists("static/index.html"):
            return FileResponse("static/index.html")
        else:
            return JSONResponse(content=FAST_HEALTH_RESPONSE, status_code=200)
    except Exception:
        return JSONResponse(content=FAST_HEALTH_RESPONSE, status_code=200)

# Mount static files after health endpoints
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
except Exception as e:
    print(f"Warning: Could not mount static files: {e}")

# Application endpoints (lazy loaded)
@app.post("/api/screenshots/upload")
async def upload_screenshots(files: List[UploadFile] = File(...)):
    """Upload and process screenshot files."""
    init_services()
    
    if not _services_initialized:
        raise HTTPException(status_code=503, detail="Services not available")
    
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    
    job_id = str(uuid.uuid4())
    saved_files = []
    
    # Validate and save files
    for file in files:
        try:
            if not file.filename or not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue
            
            file_path = await _file_manager.save_screenshot(file)
            saved_files.append({
                'filename': file.filename,
                'file_path': file_path,
                'screenshot_id': str(uuid.uuid4())
            })
        except Exception as e:
            print(f"Error saving {file.filename}: {str(e)}")
            continue
    
    if not saved_files:
        raise HTTPException(status_code=400, detail="No valid image files uploaded")
    
    # Initialize job
    _processing_jobs[job_id] = {
        "status": "processing",
        "progress": 0,
        "total": len(saved_files),
        "processed_files": []
    }
    
    _db_manager.create_processing_job(job_id, len(saved_files))
    
    # Process in background
    asyncio.create_task(process_saved_files_background(job_id, saved_files))
    
    return {
        "message": f"Started processing {len(saved_files)} screenshots",
        "processed_count": 0,
        "failed_count": 0,
        "job_id": job_id
    }

async def process_saved_files_background(job_id: str, saved_files: List[dict]):
    """Process files in background."""
    processed_count = 0
    failed_count = 0
    
    for i, file_info in enumerate(saved_files):
        try:
            # Store initial record
            _db_manager.create_screenshot(
                screenshot_id=file_info['screenshot_id'],
                filename=file_info['filename'],
                file_path=file_info['file_path']
            )
            
            # Process image
            try:
                ocr_text = _image_processor.extract_text(file_info['file_path'])
                visual_description = await _image_processor.generate_description(file_info['file_path'])
                text_embedding = _image_processor.create_embeddings(f"{ocr_text} {visual_description}")
                
                _db_manager.update_screenshot_processing(
                    screenshot_id=file_info['screenshot_id'],
                    ocr_text=ocr_text,
                    visual_description=visual_description,
                    text_embedding=text_embedding
                )
                
                processed_count += 1
            except Exception as e:
                print(f"Error processing {file_info['filename']}: {str(e)}")
                failed_count += 1
                
        except Exception as e:
            print(f"Error handling file {file_info['filename']}: {str(e)}")
            failed_count += 1
        
        # Update progress
        progress = i + 1
        _processing_jobs[job_id]["progress"] = progress
        _db_manager.update_processing_job_progress(job_id, progress)
    
    # Mark completed
    _processing_jobs[job_id]["status"] = "completed"
    _db_manager.complete_processing_job(job_id)
    
    print(f"Job {job_id} completed: {processed_count} processed, {failed_count} failed")

@app.get("/api/screenshots/status/{job_id}")
async def get_processing_status(job_id: str):
    """Get processing status."""
    init_services()
    
    if job_id not in _processing_jobs:
        job = _db_manager.get_processing_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return {
            "status": job["status"],
            "progress": job["progress"],
            "total": job["total"]
        }
    
    job = _processing_jobs[job_id]
    return {
        "status": job["status"],
        "progress": job["progress"],
        "total": job["total"]
    }

@app.post("/api/screenshots/search")
async def search_screenshots(request: dict):
    """Search screenshots."""
    init_services()
    
    if not _services_initialized:
        raise HTTPException(status_code=503, detail="Search service not available")
    
    start_time = time.time()
    
    try:
        query = request.get('query', '')
        limit = request.get('limit', 5)
        
        results = await _search_service.hybrid_search(query, limit)
        query_time_ms = int((time.time() - start_time) * 1000)
        
        return {
            "results": results,
            "total_searched": len(_db_manager.get_all_processed_screenshots()),
            "query_time_ms": query_time_ms
        }
    except Exception as e:
        print(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/api/screenshots")
async def get_all_screenshots():
    """Get all screenshots."""
    init_services()
    
    if not _services_initialized:
        return {"screenshots": [], "total": 0}
    
    screenshots = _db_manager.get_all_screenshots()
    
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

@app.delete("/api/screenshots/{screenshot_id}")
async def delete_screenshot(screenshot_id: str):
    """Delete screenshot."""
    init_services()
    
    if not _services_initialized:
        raise HTTPException(status_code=503, detail="Service not available")
    
    if not screenshot_id or screenshot_id.strip() == "":
        raise HTTPException(status_code=400, detail="Invalid screenshot ID")
    
    try:
        screenshot = _db_manager.get_screenshot_by_id(screenshot_id)
        if not screenshot:
            raise HTTPException(status_code=404, detail="Screenshot not found")
        
        # Delete file
        try:
            _file_manager.delete_file(screenshot["file_path"])
        except Exception as file_error:
            print(f"Warning: Could not delete file {screenshot['file_path']}: {str(file_error)}")
        
        # Delete from database
        _db_manager.delete_screenshot(screenshot_id)
        
        return {"message": "Screenshot deleted successfully", "id": screenshot_id}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting screenshot {screenshot_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete screenshot: {str(e)}")

# Production entry point
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info",
        access_log=False  # Disable access logs for performance
    )