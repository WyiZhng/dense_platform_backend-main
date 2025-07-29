"""
Test Admin Functionality

This script tests the admin functionality implementation to ensure all endpoints work correctly.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile
import json

# Import the FastAPI app and dependencies
from dense_platform_backend_main.main import app
from dense_platform_backend_main.database.table import Base
from dense_platform_backend_main.api.auth.session import get_db
from dense_platform_backend_main.services.rbac_service import RBACService

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_admin.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the get_db dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Create test client
client = TestClient(app)


def setup_test_database():
    """Set up test database with initial data"""
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Initialize RBAC system
    db = TestingSessionLocal()
    try:
        RBACService.initialize_default_permissions(db)
        RBACService.initialize_default_roles(db)
        
        # Create test admin user
        from dense_platform_backend_main.database.table import User, UserDetail, UserType
        import hashlib
        
        admin_user = User(
            id="admin_test",
            password=hashlib.sha256("admin123".encode()).hexdigest(),
            type=UserType.Doctor,
            is_active=True
        )
        db.add(admin_user)
        
        admin_detail = UserDetail(
            id="admin_test",
            name="Test Admin",
            email="admin@test.com"
        )
        db.add(admin_detail)
        
        # Assign admin role
        RBACService.assign_role(db, "admin_test", "admin")
        
        # Create test patient user
        patient_user = User(
            id="patient_test",
            password=hashlib.sha256("patient123".encode()).hexdigest(),
            type=UserType.Patient,
            is_active=True
        )
        db.add(patient_user)
        
        patient_detail = UserDetail(
            id="patient_test",
            name="Test Patient",
            email="patient@test.com"
        )
        db.add(patient_detail)
        
        db.commit()
        print("✓ Test database setup completed")
        
    except Exception as e:
        print(f"✗ Database setup failed: {e}")
        db.rollback()
    finally:
        db.close()


def get_admin_token():
    """Get admin authentication token"""
    login_data = {
        "id": "admin_test",
        "password": "admin123"
    }
    
    response = client.post("/auth/login", json=login_data)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            return data["data"]["token"]
    
    print(f"✗ Failed to get admin token: {response.text}")
    return None


def test_admin_user_management():
    """Test admin user management endpoints"""
    print("\n=== Testing Admin User Management ===")
    
    token = get_admin_token()
    if not token:
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test get all users
    response = client.get("/admin/users/", headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            print("✓ Get all users - SUCCESS")
            users = data["data"]["users"]
            print(f"  Found {len(users)} users")
        else:
            print(f"✗ Get all users - API Error: {data.get('message')}")
            return False
    else:
        print(f"✗ Get all users - HTTP Error: {response.status_code}")
        return False
    
    # Test get specific user
    response = client.get("/admin/users/admin_test", headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            print("✓ Get user details - SUCCESS")
            user_data = data["data"]
            print(f"  User: {user_data.get('name')} ({user_data.get('id')})")
        else:
            print(f"✗ Get user details - API Error: {data.get('message')}")
            return False
    else:
        print(f"✗ Get user details - HTTP Error: {response.status_code}")
        return False
    
    # Test create new user
    new_user_data = {
        "user_id": "test_doctor",
        "password": "doctor123",
        "user_type": 1,  # Doctor
        "name": "Test Doctor",
        "email": "doctor@test.com",
        "position": "Radiologist",
        "workplace": "Test Hospital"
    }
    
    response = client.post("/admin/users/", json=new_user_data, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            print("✓ Create user - SUCCESS")
            print(f"  Created user: {new_user_data['user_id']}")
        else:
            print(f"✗ Create user - API Error: {data.get('message')}")
            return False
    else:
        print(f"✗ Create user - HTTP Error: {response.status_code}")
        return False
    
    # Test update user
    update_data = {
        "name": "Updated Test Doctor",
        "email": "updated_doctor@test.com"
    }
    
    response = client.put("/admin/users/test_doctor", json=update_data, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            print("✓ Update user - SUCCESS")
        else:
            print(f"✗ Update user - API Error: {data.get('message')}")
            return False
    else:
        print(f"✗ Update user - HTTP Error: {response.status_code}")
        return False
    
    return True


def test_admin_dashboard():
    """Test admin dashboard endpoints"""
    print("\n=== Testing Admin Dashboard ===")
    
    token = get_admin_token()
    if not token:
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test system overview
    response = client.get("/admin/dashboard/stats/overview", headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            print("✓ System overview - SUCCESS")
            stats = data["data"]
            print(f"  Total users: {stats['users']['total']}")
            print(f"  Active users: {stats['users']['active']}")
            print(f"  Total reports: {stats['reports']['total']}")
        else:
            print(f"✗ System overview - API Error: {data.get('message')}")
            return False
    else:
        print(f"✗ System overview - HTTP Error: {response.status_code}")
        return False
    
    # Test user statistics
    response = client.get("/admin/dashboard/stats/users", headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            print("✓ User statistics - SUCCESS")
            stats = data["data"]
            print(f"  User type distribution: {len(stats['user_type_distribution'])} types")
        else:
            print(f"✗ User statistics - API Error: {data.get('message')}")
            return False
    else:
        print(f"✗ User statistics - HTTP Error: {response.status_code}")
        return False
    
    # Test system health
    response = client.get("/admin/dashboard/system/health", headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            print("✓ System health - SUCCESS")
            health = data["data"]
            print(f"  Overall status: {health['overall_status']}")
            print(f"  Database status: {health['database_status']}")
        else:
            print(f"✗ System health - API Error: {data.get('message')}")
            return False
    else:
        print(f"✗ System health - HTTP Error: {response.status_code}")
        return False
    
    return True


def test_admin_system_config():
    """Test admin system configuration endpoints"""
    print("\n=== Testing Admin System Configuration ===")
    
    token = get_admin_token()
    if not token:
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test get all configurations
    response = client.get("/admin/config/", headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            print("✓ Get all configurations - SUCCESS")
            configs = data["data"]["configurations"]
            print(f"  Found {len(configs)} configurations")
        else:
            print(f"✗ Get all configurations - API Error: {data.get('message')}")
            return False
    else:
        print(f"✗ Get all configurations - HTTP Error: {response.status_code}")
        return False
    
    # Test get specific configuration
    response = client.get("/admin/config/system.maintenance_mode", headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            print("✓ Get specific configuration - SUCCESS")
            config = data["data"]
            print(f"  Maintenance mode: {config['value']}")
        else:
            print(f"✗ Get specific configuration - API Error: {data.get('message')}")
            return False
    else:
        print(f"✗ Get specific configuration - HTTP Error: {response.status_code}")
        return False
    
    # Test update configuration
    update_data = {
        "value": True,
        "description": "Enable maintenance mode for testing"
    }
    
    response = client.put("/admin/config/system.maintenance_mode", json=update_data, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            print("✓ Update configuration - SUCCESS")
        else:
            print(f"✗ Update configuration - API Error: {data.get('message')}")
            return False
    else:
        print(f"✗ Update configuration - HTTP Error: {response.status_code}")
        return False
    
    # Test create new configuration
    new_config = {
        "key": "test.custom_setting",
        "value": "test_value",
        "description": "Test custom configuration",
        "category": "test",
        "is_sensitive": False
    }
    
    response = client.post("/admin/config/", json=new_config, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            print("✓ Create configuration - SUCCESS")
        else:
            print(f"✗ Create configuration - API Error: {data.get('message')}")
            return False
    else:
        print(f"✗ Create configuration - HTTP Error: {response.status_code}")
        return False
    
    return True


def test_admin_rbac():
    """Test admin RBAC endpoints"""
    print("\n=== Testing Admin RBAC ===")
    
    token = get_admin_token()
    if not token:
        return False
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test get all roles
    response = client.get("/admin/rbac/roles", headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            print("✓ Get all roles - SUCCESS")
            roles = data["data"]
            print(f"  Found {len(roles)} roles")
        else:
            print(f"✗ Get all roles - API Error: {data.get('message')}")
            return False
    else:
        print(f"✗ Get all roles - HTTP Error: {response.status_code}")
        return False
    
    # Test get user roles
    response = client.get("/admin/rbac/users/admin_test/roles", headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == 0:
            print("✓ Get user roles - SUCCESS")
            roles = data["data"]
            print(f"  Admin user has {len(roles)} roles")
        else:
            print(f"✗ Get user roles - API Error: {data.get('message')}")
            return False
    else:
        print(f"✗ Get user roles - HTTP Error: {response.status_code}")
        return False
    
    return True


def cleanup_test_database():
    """Clean up test database"""
    try:
        os.remove("test_admin.db")
        print("✓ Test database cleaned up")
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"✗ Failed to cleanup test database: {e}")


def main():
    """Run all admin functionality tests"""
    print("Starting Admin Functionality Tests...")
    
    # Setup
    setup_test_database()
    
    # Run tests
    tests_passed = 0
    total_tests = 4
    
    if test_admin_user_management():
        tests_passed += 1
    
    if test_admin_dashboard():
        tests_passed += 1
    
    if test_admin_system_config():
        tests_passed += 1
    
    if test_admin_rbac():
        tests_passed += 1
    
    # Cleanup
    cleanup_test_database()
    
    # Results
    print(f"\n=== Test Results ===")
    print(f"Tests passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("✓ All admin functionality tests PASSED!")
        return True
    else:
        print("✗ Some admin functionality tests FAILED!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)