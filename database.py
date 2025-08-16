import sqlite3
import json
import pickle
from typing import List, Dict, Any, Optional
from datetime import datetime

DATABASE_PATH = "visual_memory_search.db"

class DatabaseManager:
    def __init__(self):
        self.db_path = DATABASE_PATH
    
    def get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        return conn
    
    def create_screenshot(self, screenshot_id: str, filename: str, file_path: str):
        """Create a new screenshot record."""
        conn = self.get_connection()
        try:
            conn.execute("""
                INSERT INTO screenshots (id, filename, file_path, upload_date)
                VALUES (?, ?, ?, ?)
            """, (screenshot_id, filename, file_path, datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()
    
    def update_screenshot_processing(self, screenshot_id: str, ocr_text: str, 
                                   visual_description: str, text_embedding: List[float]):
        """Update screenshot with processing results."""
        conn = self.get_connection()
        try:
            # Convert embedding to binary format for storage
            embedding_blob = pickle.dumps(text_embedding)
            
            conn.execute("""
                UPDATE screenshots 
                SET processed = TRUE, ocr_text = ?, visual_description = ?, 
                    text_embedding = ?
                WHERE id = ?
            """, (ocr_text, visual_description, embedding_blob, screenshot_id))
            conn.commit()
        finally:
            conn.close()
    
    def get_all_screenshots(self) -> List[Dict[str, Any]]:
        """Get all screenshots."""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT id, filename, file_path, upload_date, processed
                FROM screenshots
                ORDER BY upload_date DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_all_processed_screenshots(self) -> List[Dict[str, Any]]:
        """Get all processed screenshots with embeddings."""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT id, filename, file_path, ocr_text, visual_description, 
                       text_embedding, upload_date
                FROM screenshots
                WHERE processed = TRUE
            """)
            
            results = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                # Deserialize embedding
                if row_dict['text_embedding']:
                    row_dict['text_embedding'] = pickle.loads(row_dict['text_embedding'])
                results.append(row_dict)
            
            return results
        finally:
            conn.close()
    
    def create_processing_job(self, job_id: str, total: int):
        """Create a new processing job."""
        conn = self.get_connection()
        try:
            conn.execute("""
                INSERT INTO processing_jobs (job_id, status, total, created_at)
                VALUES (?, 'processing', ?, ?)
            """, (job_id, total, datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()
    
    def update_processing_job_progress(self, job_id: str, progress: int):
        """Update job progress."""
        conn = self.get_connection()
        try:
            conn.execute("""
                UPDATE processing_jobs 
                SET progress = ?
                WHERE job_id = ?
            """, (progress, job_id))
            conn.commit()
        finally:
            conn.close()
    
    def complete_processing_job(self, job_id: str):
        """Mark job as completed."""
        conn = self.get_connection()
        try:
            conn.execute("""
                UPDATE processing_jobs 
                SET status = 'completed', completed_at = ?
                WHERE job_id = ?
            """, (datetime.now().isoformat(), job_id))
            conn.commit()
        finally:
            conn.close()
    
    def get_processing_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get processing job by ID."""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT job_id, status, progress, total, created_at, completed_at
                FROM processing_jobs
                WHERE job_id = ?
            """, (job_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def get_screenshot_by_id(self, screenshot_id: str) -> Optional[Dict[str, Any]]:
        """Get screenshot by ID."""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT id, filename, file_path, upload_date, processed, ocr_text, visual_description
                FROM screenshots
                WHERE id = ?
            """, (screenshot_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def delete_screenshot(self, screenshot_id: str) -> bool:
        """Delete a screenshot by ID."""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                DELETE FROM screenshots WHERE id = ?
            """, (screenshot_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

def init_db():
    """Initialize the database with required tables."""
    conn = sqlite3.connect(DATABASE_PATH)
    
    try:
        # Create screenshots table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS screenshots (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed BOOLEAN DEFAULT FALSE,
                ocr_text TEXT,
                visual_description TEXT,
                text_embedding BLOB,
                file_size INTEGER,
                image_width INTEGER,
                image_height INTEGER
            )
        """)
        
        # Create processing_jobs table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processing_jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT CHECK(status IN ('processing', 'completed', 'failed')),
                progress INTEGER DEFAULT 0,
                total INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        
        # Create indexes for better search performance
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_screenshots_processed 
            ON screenshots(processed)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_screenshots_upload_date 
            ON screenshots(upload_date)
        """)
        
        conn.commit()
        print("Database initialized successfully")
        
    finally:
        conn.close()
