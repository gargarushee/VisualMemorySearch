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
    # Fast directory creation
    os.makedirs("static", exist_ok=True)
    os.makedirs("uploads", exist_ok=True)
    
    # Initialize database in background to not block health checks
    asyncio.create_task(initialize_database_async())
    print("Visual Memory Search API startup initiated")

async def initialize_database_async():
    """Initialize database asynchronously."""
    try:
        # Run database initialization in thread to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, init_db)
        print("Database initialized successfully")
        print("Visual Memory Search API started successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")
        # Continue running even if database init fails

@app.get("/")
async def root():
    """Serve the main application with fast health check fallback."""
    try:
        # Check if static/index.html exists and serve it
        if os.path.exists("static/index.html"):
            return FileResponse("static/index.html")
        else:
            # Fallback to health response if static files missing
            return JSONResponse(
                content={
                    "status": "healthy", 
                    "service": "Visual Memory Search", 
                    "version": "1.0.0",
                    "message": "Frontend files not found"
                },
                status_code=200
            )
    except Exception as e:
        print(f"Error serving root: {str(e)}")
        # Return health response on any error
        return JSONResponse(
            content={
                "status": "healthy", 
                "service": "Visual Memory Search", 
                "version": "1.0.0",
                "message": "Service running with fallback response"
            },
            status_code=200
        )

@app.get("/app")
async def serve_app():
    """Serve the main application."""
    try:
        # Check if static/index.html exists
        if os.path.exists("static/index.html"):
            return FileResponse("static/index.html")
        else:
            print("Warning: static/index.html not found, returning health check response")
            # Return a simple health check response if static file doesn't exist
            return JSONResponse(
                content={
                    "status": "healthy", 
                    "service": "Visual Memory Search", 
                    "version": "1.0.0",
                    "message": "API is running. Frontend static files not available."
                },
                status_code=200
            )
    except Exception as e:
        print(f"Error serving index.html: {str(e)}")
        # Return a simple health check response if static file fails
        return JSONResponse(
            content={
                "status": "healthy", 
                "service": "Visual Memory Search", 
                "version": "1.0.0",
                "message": "API is running. Error accessing static files."
            },
            status_code=200
        )

@app.get("/health")
async def health_check():
    """Health check endpoint for deployment systems."""
    return JSONResponse(
        content={"status": "healthy", "service": "Visual Memory Search", "version": "1.0.0"},
        status_code=200
    )

@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint for deployment systems."""
    try:
        # Quick database connectivity check
        db_manager.get_all_processed_screenshots()
        return JSONResponse(
            content={"status": "ready", "service": "Visual Memory Search", "database": "connected"},
            status_code=200
        )
    except Exception as e:
        return JSONResponse(
            content={"status": "not_ready", "service": "Visual Memory Search", "error": str(e)},
            status_code=503
        )

@app.post("/api/screenshots/upload", response_model=UploadResponse)
async def upload_screenshots(files: List[UploadFile] = File(...)):
    """Upload and process screenshot files."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    
    job_id = str(uuid.uuid4())
    processed_count = 0
    failed_count = 0
    
    # Validate and save files first
    saved_files = []
    for file in files:
        try:
            # Validate file type
            if not file.filename or not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue
            
            # Save file immediately
            file_path = await file_manager.save_screenshot(file)
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
    
    # Initialize job status
    processing_jobs[job_id] = {
        "status": "processing",
        "progress": 0,
        "total": len(saved_files),
        "processed_files": []
    }
    
    # Store job in database
    db_manager.create_processing_job(job_id, len(saved_files))
    
    # Process saved files in background
    asyncio.create_task(process_saved_files_background(job_id, saved_files))
    
    return UploadResponse(
        message=f"Started processing {len(saved_files)} screenshots",
        processed_count=0,
        failed_count=0,
        job_id=job_id
    )

async def process_saved_files_background(job_id: str, saved_files: List[dict]):
    """Process already saved files in the background."""
    processed_count = 0
    failed_count = 0
    
    for i, file_info in enumerate(saved_files):
        try:
            # Store initial record
            db_manager.create_screenshot(
                screenshot_id=file_info['screenshot_id'],
                filename=file_info['filename'],
                file_path=file_info['file_path']
            )
            
            # Process image (OCR + visual description)
            try:
                ocr_text = image_processor.extract_text(file_info['file_path'])
                visual_description = await image_processor.generate_description(file_info['file_path'])
                
                # Create embeddings
                text_embedding = image_processor.create_embeddings(f"{ocr_text} {visual_description}")
                
                # Update record with processed data
                db_manager.update_screenshot_processing(
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

@app.delete("/api/screenshots/{screenshot_id}")
async def delete_screenshot(screenshot_id: str):
    """Delete a screenshot by ID."""
    # Validate screenshot_id format
    if not screenshot_id or screenshot_id.strip() == "":
        raise HTTPException(status_code=400, detail="Invalid screenshot ID")
    
    try:
        # Get screenshot info before deletion
        screenshot = db_manager.get_screenshot_by_id(screenshot_id)
        if not screenshot:
            raise HTTPException(status_code=404, detail="Screenshot not found")
        
        # Delete file from filesystem (with error handling)
        try:
            file_manager.delete_file(screenshot["file_path"])
        except Exception as file_error:
            print(f"Warning: Could not delete file {screenshot['file_path']}: {str(file_error)}")
            # Continue with database deletion even if file deletion fails
        
        # Delete from database
        db_manager.delete_screenshot(screenshot_id)
        
        return {"message": "Screenshot deleted successfully", "id": screenshot_id}
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        print(f"Error deleting screenshot {screenshot_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete screenshot: {str(e)}")

# Application is started via uvicorn command in workflow configuration
