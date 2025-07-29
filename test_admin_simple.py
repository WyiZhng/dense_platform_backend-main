"""
Simple Admin Functionality Test

This script performs basic import and structure tests for the admin functionality.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all admin modules can be imported"""
    print("=== Testing Admin Module Imports ===")
    
    try:
        from dense_platform_backend_main.api.admin import user_management
        print("✓ Admin user management module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import user management module: {e}")
        return False
    
    try:
        from dense_platform_backend_main.api.admin import dashboard
        print("✓ Admin dashboard module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import dashboard module: {e}")
        return False
    
    try:
        from dense_platform_backend_main.api.admin import system_config
        print("✓ Admin system config module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import system config module: {e}")
        return False
    
    try:
        from dense_platform_backend_main.api.admin import rbac
        print("✓ Admin RBAC module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import RBAC module: {e}")
        return False
    
    return True


def test_router_structure():
    """Test that routers are properly structured"""
    print("\n=== Testing Router Structure ===")
    
    try:
        from dense_platform_backend_main.api.admin.user_management import router as user_router
        print(f"✓ User management router has {len(user_router.routes)} routes")
        
        # Check some key routes
        route_paths = [route.path for route in user_router.routes]
        expected_paths = ["/admin/users/", "/admin/users/{user_id}"]
        
        for path in expected_paths:
            if any(path in route_path for route_path in route_paths):
                print(f"  ✓ Found route: {path}")
            else:
                print(f"  ✗ Missing route: {path}")
                return False
                
    except Exception as e:
        print(f"✗ Failed to test user management router: {e}")
        return False
    
    try:
        from dense_platform_backend_main.api.admin.dashboard import router as dashboard_router
        print(f"✓ Dashboard router has {len(dashboard_router.routes)} routes")
        
        # Check some key routes
        route_paths = [route.path for route in dashboard_router.routes]
        expected_paths = ["/admin/dashboard/stats/overview", "/admin/dashboard/system/health"]
        
        for path in expected_paths:
            if any(path in route_path for route_path in route_paths):
                print(f"  ✓ Found route: {path}")
            else:
                print(f"  ✗ Missing route: {path}")
                return False
                
    except Exception as e:
        print(f"✗ Failed to test dashboard router: {e}")
        return False
    
    try:
        from dense_platform_backend_main.api.admin.system_config import router as config_router
        print(f"✓ System config router has {len(config_router.routes)} routes")
        
        # Check some key routes
        route_paths = [route.path for route in config_router.routes]
        expected_paths = ["/admin/config/", "/admin/config/{config_key}"]
        
        for path in expected_paths:
            if any(path in route_path for route_path in route_paths):
                print(f"  ✓ Found route: {path}")
            else:
                print(f"  ✗ Missing route: {path}")
                return False
                
    except Exception as e:
        print(f"✗ Failed to test system config router: {e}")
        return False
    
    return True


def test_main_router_integration():
    """Test that admin routers are integrated into main router"""
    print("\n=== Testing Main Router Integration ===")
    
    try:
        from dense_platform_backend_main.api import router as main_router
        print(f"✓ Main router has {len(main_router.routes)} routes")
        
        # Check that admin routes are included
        all_paths = []
        for route in main_router.routes:
            if hasattr(route, 'path'):
                all_paths.append(route.path)
            elif hasattr(route, 'routes'):  # Sub-router
                for sub_route in route.routes:
                    if hasattr(sub_route, 'path'):
                        all_paths.append(sub_route.path)
        
        admin_paths_found = [path for path in all_paths if '/admin/' in path]
        print(f"✓ Found {len(admin_paths_found)} admin routes in main router")
        
        if len(admin_paths_found) > 0:
            print("  Sample admin routes:")
            for path in admin_paths_found[:5]:  # Show first 5
                print(f"    - {path}")
        
        return len(admin_paths_found) > 0
        
    except Exception as e:
        print(f"✗ Failed to test main router integration: {e}")
        return False


def test_pydantic_models():
    """Test that Pydantic models are properly defined"""
    print("\n=== Testing Pydantic Models ===")
    
    try:
        from dense_platform_backend_main.api.admin.user_management import CreateUserRequest, UpdateUserRequest
        print("✓ User management Pydantic models imported successfully")
        
        # Test model creation
        create_request = CreateUserRequest(
            user_id="test_user",
            password="test123",
            user_type=0,  # Patient
            name="Test User"
        )
        print("✓ CreateUserRequest model can be instantiated")
        
    except Exception as e:
        print(f"✗ Failed to test user management models: {e}")
        return False
    
    try:
        from dense_platform_backend_main.api.admin.system_config import ConfigurationItem, UpdateConfigRequest
        print("✓ System config Pydantic models imported successfully")
        
        # Test model creation
        config_item = ConfigurationItem(
            key="test.setting",
            value="test_value",
            description="Test configuration"
        )
        print("✓ ConfigurationItem model can be instantiated")
        
    except Exception as e:
        print(f"✗ Failed to test system config models: {e}")
        return False
    
    return True


def test_utility_functions():
    """Test utility functions"""
    print("\n=== Testing Utility Functions ===")
    
    try:
        from dense_platform_backend_main.api.admin.system_config import get_config_value, is_maintenance_mode
        print("✓ System config utility functions imported successfully")
        
        # Test utility functions
        session_timeout = get_config_value("auth.session_timeout_hours", 24)
        print(f"✓ Session timeout: {session_timeout} hours")
        
        maintenance_mode = is_maintenance_mode()
        print(f"✓ Maintenance mode: {maintenance_mode}")
        
    except Exception as e:
        print(f"✗ Failed to test utility functions: {e}")
        return False
    
    return True


def main():
    """Run all simple tests"""
    print("Starting Simple Admin Functionality Tests...")
    
    tests_passed = 0
    total_tests = 5
    
    if test_imports():
        tests_passed += 1
    
    if test_router_structure():
        tests_passed += 1
    
    if test_main_router_integration():
        tests_passed += 1
    
    if test_pydantic_models():
        tests_passed += 1
    
    if test_utility_functions():
        tests_passed += 1
    
    # Results
    print(f"\n=== Test Results ===")
    print(f"Tests passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("✓ All simple admin functionality tests PASSED!")
        return True
    else:
        print("✗ Some simple admin functionality tests FAILED!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)