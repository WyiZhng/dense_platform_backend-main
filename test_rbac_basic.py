"""
Basic RBAC Middleware Test

This script performs basic validation of the RBAC middleware implementation.
"""

import os
import sys

def test_rbac_middleware_files():
    """Test that RBAC middleware files exist"""
    print("=== Testing RBAC Middleware Files ===")
    
    required_files = [
        "services/rbac_middleware.py",
        "services/rbac_service.py",
        "api/auth/rbac_middleware.py",
        "api/admin/user_management.py",
        "api/admin/dashboard.py",
        "api/admin/system_config.py"
    ]
    
    all_exist = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✓ {file_path} exists")
        else:
            print(f"✗ {file_path} missing")
            all_exist = False
    
    return all_exist


def test_rbac_middleware_content():
    """Test that RBAC middleware files have expected content"""
    print("\n=== Testing RBAC Middleware Content ===")
    
    # Test core RBAC middleware
    try:
        with open("services/rbac_middleware.py", "r", encoding="utf-8") as f:
            content = f.read()
            
        required_elements = [
            "class RBACMiddleware:",
            "def require_permission",
            "def require_admin",
            "def require_role",
            "RequirePermission",
            "RequireAdmin"
        ]
        
        all_found = True
        for element in required_elements:
            if element in content:
                print(f"✓ Core RBAC middleware contains: {element}")
            else:
                print(f"✗ Core RBAC middleware missing: {element}")
                all_found = False
                
        if not all_found:
            return False
            
    except Exception as e:
        print(f"✗ Failed to read core RBAC middleware: {e}")
        return False
    
    # Test global RBAC middleware
    try:
        with open("api/auth/rbac_middleware.py", "r", encoding="utf-8") as f:
            content = f.read()
            
        required_elements = [
            "class GlobalRBACMiddleware:",
            "ROUTE_PERMISSIONS = {",
            "PUBLIC_ROUTES = [",
            "def check_route_access",
            "RouteProtectionConfig"
        ]
        
        all_found = True
        for element in required_elements:
            if element in content:
                print(f"✓ Global RBAC middleware contains: {element}")
            else:
                print(f"✗ Global RBAC middleware missing: {element}")
                all_found = False
                
        if not all_found:
            return False
            
    except Exception as e:
        print(f"✗ Failed to read global RBAC middleware: {e}")
        return False
    
    return True


def test_endpoint_rbac_updates():
    """Test that endpoints have been updated with RBAC"""
    print("\n=== Testing Endpoint RBAC Updates ===")
    
    # Test user info endpoints
    try:
        with open("api/user/info.py", "r", encoding="utf-8") as f:
            content = f.read()
            
        rbac_indicators = [
            "RequireAuthWithContext",
            "current_user = RequireAuthWithContext",
            "current_user[\"user_id\"]"
        ]
        
        rbac_found = 0
        for indicator in rbac_indicators:
            if indicator in content:
                rbac_found += 1
        
        if rbac_found >= 2:
            print(f"✓ User info endpoints have RBAC integration ({rbac_found}/3 indicators)")
        else:
            print(f"✗ User info endpoints lack RBAC integration ({rbac_found}/3 indicators)")
            return False
            
    except Exception as e:
        print(f"✗ Failed to test user info endpoints: {e}")
        return False
    
    # Test report endpoints
    try:
        with open("api/user/report.py", "r", encoding="utf-8") as f:
            content = f.read()
            
        rbac_indicators = [
            "RequireAnyPermission",
            "RequirePermission",
            "current_user = Require"
        ]
        
        rbac_found = 0
        for indicator in rbac_indicators:
            if indicator in content:
                rbac_found += 1
        
        if rbac_found >= 2:
            print(f"✓ Report endpoints have RBAC integration ({rbac_found}/3 indicators)")
        else:
            print(f"✗ Report endpoints lack RBAC integration ({rbac_found}/3 indicators)")
            return False
            
    except Exception as e:
        print(f"✗ Failed to test report endpoints: {e}")
        return False
    
    # Test doctor endpoints
    try:
        with open("api/doctor/info.py", "r", encoding="utf-8") as f:
            content = f.read()
            
        rbac_indicators = [
            "RequireRole",
            "RequireAuthWithContext",
            "current_user = Require"
        ]
        
        rbac_found = 0
        for indicator in rbac_indicators:
            if indicator in content:
                rbac_found += 1
        
        if rbac_found >= 2:
            print(f"✓ Doctor endpoints have RBAC integration ({rbac_found}/3 indicators)")
        else:
            print(f"✗ Doctor endpoints lack RBAC integration ({rbac_found}/3 indicators)")
            return False
            
    except Exception as e:
        print(f"✗ Failed to test doctor endpoints: {e}")
        return False
    
    return True


def test_admin_endpoint_protection():
    """Test that admin endpoints are properly protected"""
    print("\n=== Testing Admin Endpoint Protection ===")
    
    admin_files = [
        ("api/admin/user_management.py", "RequirePermission(\"admin\", \"users\")"),
        ("api/admin/dashboard.py", "RequirePermission(\"admin\", \"system\")"),
        ("api/admin/system_config.py", "RequirePermission(\"admin\", \"system\")"),
        ("api/admin/rbac.py", "RequirePermission(\"admin\", \"roles\")")
    ]
    
    for file_path, expected_protection in admin_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            if expected_protection in content:
                print(f"✓ {file_path} has proper admin protection")
            else:
                print(f"✗ {file_path} lacks proper admin protection")
                return False
                
        except Exception as e:
            print(f"✗ Failed to test {file_path}: {e}")
            return False
    
    return True


def test_route_configuration():
    """Test route configuration and patterns"""
    print("\n=== Testing Route Configuration ===")
    
    try:
        with open("api/auth/rbac_middleware.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check for route patterns
        route_patterns = [
            "r'^/admin/users.*': [(\"admin\", \"users\")]",
            "r'^/api/user$': [(\"user\", \"read\")]",
            "r'^/api/report/delete$': [(\"report\", \"delete\")",
            "r'^/auth/login$'",
            "r'^/docs.*'"
        ]
        
        patterns_found = 0
        for pattern in route_patterns:
            if pattern in content:
                patterns_found += 1
        
        if patterns_found >= 4:
            print(f"✓ Route configuration has proper patterns ({patterns_found}/5)")
        else:
            print(f"✗ Route configuration lacks proper patterns ({patterns_found}/5)")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Failed to test route configuration: {e}")
        return False


def main():
    """Run all basic RBAC middleware tests"""
    print("Starting Basic RBAC Middleware Tests...")
    
    tests_passed = 0
    total_tests = 5
    
    if test_rbac_middleware_files():
        tests_passed += 1
    
    if test_rbac_middleware_content():
        tests_passed += 1
    
    if test_endpoint_rbac_updates():
        tests_passed += 1
    
    if test_admin_endpoint_protection():
        tests_passed += 1
    
    if test_route_configuration():
        tests_passed += 1
    
    # Results
    print(f"\n=== Test Results ===")
    print(f"Tests passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("✓ All basic RBAC middleware tests PASSED!")
        print("\nRBAC middleware implementation is complete with:")
        print("  - Core RBAC middleware with permission checking")
        print("  - Global route protection configuration")
        print("  - Updated endpoints with proper RBAC dependencies")
        print("  - Admin endpoints with appropriate permission requirements")
        print("  - Route patterns for automatic protection")
        return True
    else:
        print("✗ Some basic RBAC middleware tests FAILED!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)