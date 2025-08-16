#!/usr/bin/env python3
"""
Comprehensive health check script for production deployment
"""
import sys
import os
import time
import requests
import json
from typing import Dict, List, Tuple

def check_environment_variables() -> Tuple[bool, List[str]]:
    """Check required environment variables for production."""
    required_vars = [
        'ANTHROPIC_API_KEY'  # Required for visual descriptions
    ]
    
    optional_vars = [
        'PORT',  # Default to 5000
        'HOST',  # Default to 0.0.0.0
    ]
    
    missing = []
    for var in required_vars:
        if not os.environ.get(var):
            missing.append(f"Required: {var}")
    
    present_optional = []
    for var in optional_vars:
        if os.environ.get(var):
            present_optional.append(f"Optional: {var} = {os.environ.get(var)}")
    
    if present_optional:
        print(f"✓ Optional environment variables: {', '.join(present_optional)}")
    
    return len(missing) == 0, missing

def check_dependencies() -> Tuple[bool, List[str]]:
    """Check if all required dependencies are available."""
    dependencies = [
        ('fastapi', 'FastAPI'),
        ('uvicorn', 'Uvicorn'),
        ('anthropic', 'Anthropic API client'),
        ('pytesseract', 'Tesseract OCR'),
        ('PIL', 'Pillow'),
        ('numpy', 'NumPy'),
        ('pydantic', 'Pydantic'),
    ]
    
    missing = []
    for module, description in dependencies:
        try:
            __import__(module)
            print(f"✓ {description} available")
        except ImportError:
            missing.append(f"{description} ({module})")
    
    # Check optional sentence-transformers
    try:
        __import__('sentence_transformers')
        print("✓ Sentence Transformers available (optimal embeddings)")
    except ImportError:
        print("⚠ Sentence Transformers not available (using fallback embeddings)")
    
    return len(missing) == 0, missing

def check_file_structure() -> Tuple[bool, List[str]]:
    """Check required files and directories exist."""
    required_files = [
        'main.py',
        'database.py',
        'models.py',
        'static/index.html',
        'static/app.js',
        'static/style.css',
        'services/image_processor.py',
        'services/search_service.py',
        'services/file_manager.py',
    ]
    
    required_dirs = [
        'static',
        'uploads',
        'services',
    ]
    
    missing = []
    
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing.append(f"File: {file_path}")
        else:
            print(f"✓ {file_path}")
    
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            missing.append(f"Directory: {dir_path}")
        else:
            print(f"✓ {dir_path}/")
    
    return len(missing) == 0, missing

def check_database_connectivity() -> Tuple[bool, List[str]]:
    """Check database initialization and connectivity."""
    try:
        from database import DatabaseManager, init_db
        
        # Initialize database
        init_db()
        print("✓ Database initialization successful")
        
        # Test database operations
        db_manager = DatabaseManager()
        screenshots = db_manager.get_all_screenshots()
        print(f"✓ Database connectivity verified ({len(screenshots)} screenshots)")
        
        return True, []
    except Exception as e:
        return False, [f"Database error: {str(e)}"]

def check_api_endpoints(base_url: str = "http://localhost:5000") -> Tuple[bool, List[str]]:
    """Check API endpoints respond correctly."""
    endpoints = [
        ("/", "GET", "Main page"),
        ("/health", "GET", "Health check"),
        ("/ready", "GET", "Readiness check"),
        ("/api/screenshots", "GET", "Screenshots list"),
    ]
    
    issues = []
    
    for endpoint, method, description in endpoints:
        try:
            url = f"{base_url}{endpoint}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                print(f"✓ {description} ({endpoint}): {response.status_code}")
            else:
                issues.append(f"{description} ({endpoint}): HTTP {response.status_code}")
        except requests.exceptions.RequestException as e:
            issues.append(f"{description} ({endpoint}): Connection error - {str(e)}")
    
    return len(issues) == 0, issues

def check_performance_metrics(base_url: str = "http://localhost:5000") -> Tuple[bool, List[str]]:
    """Check response times for critical endpoints."""
    critical_endpoints = [
        ("/health", "Health check"),
        ("/ready", "Readiness check"),
    ]
    
    issues = []
    max_response_time = 2.0  # seconds
    
    for endpoint, description in critical_endpoints:
        try:
            url = f"{base_url}{endpoint}"
            start_time = time.time()
            response = requests.get(url, timeout=10)
            response_time = time.time() - start_time
            
            if response.status_code == 200 and response_time < max_response_time:
                print(f"✓ {description} response time: {response_time:.3f}s")
            elif response_time >= max_response_time:
                issues.append(f"{description} too slow: {response_time:.3f}s (max: {max_response_time}s)")
            else:
                issues.append(f"{description} failed: HTTP {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            issues.append(f"{description} connection error: {str(e)}")
    
    return len(issues) == 0, issues

def check_anthropic_api() -> Tuple[bool, List[str]]:
    """Check Anthropic API connectivity."""
    try:
        from services.image_processor import ImageProcessor
        
        processor = ImageProcessor()
        if processor.anthropic_client is None:
            return False, ["Anthropic API client not initialized (check ANTHROPIC_API_KEY)"]
        
        print("✓ Anthropic API client initialized")
        return True, []
        
    except Exception as e:
        return False, [f"Anthropic API check failed: {str(e)}"]

def main():
    """Run comprehensive health checks."""
    print("🔍 Visual Memory Search - Production Health Check")
    print("=" * 60)
    
    checks = [
        ("Environment Variables", check_environment_variables),
        ("Dependencies", check_dependencies),
        ("File Structure", check_file_structure),
        ("Database Connectivity", check_database_connectivity),
        ("API Endpoints", check_api_endpoints),
        ("Performance Metrics", check_performance_metrics),
        ("Anthropic API", check_anthropic_api),
    ]
    
    all_passed = True
    total_issues = []
    
    for check_name, check_function in checks:
        print(f"\n🔍 {check_name}")
        print("-" * 40)
        
        try:
            passed, issues = check_function()
            if passed:
                print(f"✅ {check_name}: PASSED")
            else:
                print(f"❌ {check_name}: FAILED")
                all_passed = False
                total_issues.extend(issues)
                for issue in issues:
                    print(f"   - {issue}")
        except Exception as e:
            print(f"💥 {check_name}: ERROR - {str(e)}")
            all_passed = False
            total_issues.append(f"{check_name}: {str(e)}")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL HEALTH CHECKS PASSED - READY FOR DEPLOYMENT")
        sys.exit(0)
    else:
        print(f"💥 HEALTH CHECK FAILED - {len(total_issues)} issues found:")
        for issue in total_issues:
            print(f"   - {issue}")
        print("\n🚨 APPLICATION NOT READY FOR PRODUCTION DEPLOYMENT")
        sys.exit(1)

if __name__ == "__main__":
    main()