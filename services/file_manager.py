import os
import uuid
import shutil
from typing import Optional
from fastapi import UploadFile
from PIL import Image

UPLOAD_DIR = "uploads"

class FileManager:
    def __init__(self):
        # Ensure upload directory exists
        os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    async def save_screenshot(self, file: UploadFile) -> str:
        """Save uploaded screenshot and return file path."""
        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1].lower()
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save file
        try:
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            # Validate and potentially convert image
            self._validate_and_process_image(file_path)
            
            return file_path
        
        except Exception as e:
            # Clean up on error
            if os.path.exists(file_path):
                os.remove(file_path)
            raise e
    
    def _validate_and_process_image(self, file_path: str) -> None:
        """Validate image file and process if needed."""
        try:
            # Open image to validate
            with Image.open(file_path) as img:
                # Check if image is valid
                img.verify()
            
            # Reopen for processing (verify() invalidates the image)
            with Image.open(file_path) as img:
                # Convert to RGB if needed (for JPEG compatibility)
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                    img.save(file_path, 'JPEG', quality=85)
                
                # Optional: Resize very large images to save space
                max_dimension = 2048
                if img.width > max_dimension or img.height > max_dimension:
                    img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                    img.save(file_path, quality=85)
        
        except Exception as e:
            raise Exception(f"Invalid image file: {str(e)}")
    
    def get_preview_url(self, file_path: str) -> str:
        """Get preview URL for a file."""
        filename = os.path.basename(file_path)
        return f"/uploads/{filename}"
    
    def delete_file(self, file_path: str) -> bool:
        """Delete a file."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            print(f"Error deleting file {file_path}: {str(e)}")
            return False
    
    def cleanup_old_files(self, max_age_days: int = 30) -> None:
        """Clean up old files (for future use)."""
        # Implementation for cleaning up old files
        # This could be called periodically to manage storage
        pass
    
    def get_file_info(self, file_path: str) -> Optional[dict]:
        """Get file information."""
        try:
            if not os.path.exists(file_path):
                return None
            
            stat = os.stat(file_path)
            
            # Get image dimensions
            try:
                with Image.open(file_path) as img:
                    width, height = img.size
            except:
                width = height = 0
            
            return {
                "file_size": stat.st_size,
                "image_width": width,
                "image_height": height,
                "created_at": stat.st_ctime
            }
        
        except Exception as e:
            print(f"Error getting file info for {file_path}: {str(e)}")
            return None
