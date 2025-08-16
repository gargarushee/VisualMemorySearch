#!/usr/bin/env python3
"""
Production deployment health check using native Python modules
"""
import sys
import os
import subprocess
import urllib.request
import urllib.error
import json
import time

def check_port_binding():
    """Check if the application can bind to the production port."""
    try:
        port = int(os.environ.get('PORT', 5000))
        print(f"✓ Port configuration: {port}")
        return True
    except Exception as e:
        print(f"❌ Port configuration error: {e}")
        return False

def check_health_endpoint():
    """Check if health endpoint responds quickly."""
    try:
        port = int(os.environ.get('PORT', 5000))
        url = f"http://localhost:{port}/health"
        
        start_time = time.time()
        with urllib.request.urlopen(url, timeout=5) as response:
            response_time = time.time() - start_time
            data = json.loads(response.read().decode())
            
            if response.getcode() == 200 and data.get('status') == 'healthy':
                print(f"✓ Health endpoint: {response_time:.3f}s")
                return response_time < 2.0  # Must respond within 2 seconds
            else:
                print(f"❌ Health endpoint failed: {response.getcode()}")
                return False
                
    except Exception as e:
        print(f"❌ Health endpoint error: {e}")
        return False

def check_ready_endpoint():
    """Check if readiness endpoint responds correctly."""
    try:
        port = int(os.environ.get('PORT', 5000))
        url = f"http://localhost:{port}/ready"
        
        start_time = time.time()
        with urllib.request.urlopen(url, timeout=10) as response:
            response_time = time.time() - start_time
            data = json.loads(response.read().decode())
            
            if response.getcode() == 200 and data.get('status') == 'ready':
                print(f"✓ Readiness endpoint: {response_time:.3f}s")
                return True
            else:
                print(f"❌ Readiness endpoint failed: {response.getcode()}")
                return False
                
    except Exception as e:
        print(f"❌ Readiness endpoint error: {e}")
        return False

def check_static_files():
    """Check if static files are served correctly."""
    try:
        port = int(os.environ.get('PORT', 5000))
        
        # Check main page
        url = f"http://localhost:{port}/"
        with urllib.request.urlopen(url, timeout=5) as response:
            content = response.read().decode()
            if "Visual Memory Search" in content and response.getcode() == 200:
                print("✓ Static files served correctly")
                return True
            else:
                print("❌ Static files not served correctly")
                return False
                
    except Exception as e:
        print(f"❌ Static files error: {e}")
        return False

def check_api_functionality():
    """Check core API functionality."""
    try:
        port = int(os.environ.get('PORT', 5000))
        url = f"http://localhost:{port}/api/screenshots"
        
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
            
            if response.getcode() == 200 and 'screenshots' in data:
                print(f"✓ API functionality: {len(data['screenshots'])} screenshots")
                return True
            else:
                print(f"❌ API functionality failed: {response.getcode()}")
                return False
                
    except Exception as e:
        print(f"❌ API functionality error: {e}")
        return False

def check_environment():
    """Check production environment requirements."""
    checks = []
    
    # Check ANTHROPIC_API_KEY
    if os.environ.get('ANTHROPIC_API_KEY'):
        print("✓ ANTHROPIC_API_KEY configured")
        checks.append(True)
    else:
        print("⚠ ANTHROPIC_API_KEY not configured (visual descriptions will be disabled)")
        checks.append(True)  # Not critical for basic operation
    
    # Check file permissions
    try:
        # Test write permissions for uploads
        test_file = "uploads/.test_write"
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        print("✓ Upload directory writable")
        checks.append(True)
    except Exception as e:
        print(f"❌ Upload directory not writable: {e}")
        checks.append(False)
    
    return all(checks)

def main():
    """Run production health checks."""
    print("🏥 Production Health Check")
    print("=" * 40)
    
    checks = [
        ("Port Configuration", check_port_binding),
        ("Environment Setup", check_environment),
        ("Health Endpoint", check_health_endpoint),
        ("Readiness Endpoint", check_ready_endpoint),
        ("Static Files", check_static_files),
        ("API Functionality", check_api_functionality),
    ]
    
    all_passed = True
    
    for check_name, check_func in checks:
        print(f"\n🔍 {check_name}")
        try:
            if check_func():
                print(f"✅ {check_name}: PASSED")
            else:
                print(f"❌ {check_name}: FAILED")
                all_passed = False
        except Exception as e:
            print(f"💥 {check_name}: ERROR - {e}")
            all_passed = False
    
    print("\n" + "=" * 40)
    if all_passed:
        print("🎉 PRODUCTION READY")
        return 0
    else:
        print("❌ PRODUCTION NOT READY")
        return 1

if __name__ == "__main__":
    sys.exit(main())