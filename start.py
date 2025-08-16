#!/usr/bin/env python3
"""
Production startup script for Visual Memory Search API
"""
import uvicorn
import os

if __name__ == "__main__":
    # Production configuration
    port = int(os.environ.get("PORT", 5000))
    host = "0.0.0.0"
    
    print(f"Starting Visual Memory Search API on {host}:{port}")
    
    # Run with production settings
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=1,  # Single worker for simplicity
        access_log=True,
        log_level="info"
    )