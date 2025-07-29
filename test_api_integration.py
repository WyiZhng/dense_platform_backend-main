"""
API Integration Tests

This module provides comprehensive integration tests for all API endpoints including:
- Authentication endpoints
- User management endpoints
- Admin endpoints
- Doctor endpoints
- RBAC endpoints
"""

import pytest
import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from dense_platform_backend_main.main import app
from dense_platform_backend_main.database.table import Base, User, UserDetail, Role, Permission, UserRole, RolePermission, UserType, UserSex
from dense_platform_backend_main.database.db import get_db

# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="function")
def setup_database():
    """Setup test database"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(setup_database):
    """Create a test user"""
    db = TestingSessionLocal()
    try:
        user = User(
            id="testuser",
            password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6QJb8.vLhO",  # "password123"
            type=UserType.Patient,
            is_active=True
        )
        db.add(user)
        
        user_detail = UserDetail(
            id="testuser",
            name="Test User",
            sex=UserSex.Male,
            phone="1234567890",
            email="test@example.com",
            address="Test Address"
        )
        db.add(user_detail)
        db.commit()
        return user
    finally:
        db.close()


@pytest.fixture
def test_doctor(setup_database):
    """Create a test doctor"""
    db = TestingSessionLocal()
    try:
        user = User(
            id="testdoctor",
            password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6QJb8.vLhO",  # "password123"
            type=UserType.Doctor,
            is_active=True
        )
        db.add(user)
        
        user_detail = UserDetail(
            id="testdoctor",
            name="Test Doctor",
            sex=UserSex.Female,
            phone="0987654321",
            email="doctor@example.com",
            address="Doctor Address"
        )
        db.add(user_detail)
        db.commit()
        return user
    finally:
        db.close()


@pytest.fixture
def test_admin(setup_database):
    """Create a test admin user"""
    db = TestingSessionLocal()
    try:
        # Create admin user
        user = User(
            id="testadmin",
            password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6QJb8.vLhO",  # "password123"
            type=UserType.Doctor,
            is_active=True
        )
        db.add(user)
        
        # Create admin role
        admin_role = Role(
            name="admin",
            description="Administrator",
            is_active=True
        )
        db.add(admin_role)
        db.flush()
        
        # Assign admin role to user
        user_role = UserRole(user_id="testadmin", role_id=admin_role.id)
        db.add(user_role)
        
        user_detail = UserDetail(
            id="testadmin",
            name="Test Admin",
            sex=UserSex.Male,
            phone="1111111111",
            email="admin@example.com",
            address="Admin Address"
        )
        db.add(user_detail)
        db.commit()
        return user
    finally:
        db.close()


class TestAuthenticationEndpoints:
    """Test authentication API endpoints"""
    
    def test_register_success(self, setup_database):
        """Test successful user registration"""
        response = client.post("/api/register", json={
            "username": "newuser",
            "password": "NewPassword123!",
            "type": "Patient"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "注册成功" in data["message"]
    
    def test_register_duplicate_user(self, test_user):
        """Test registration with duplicate username"""
        response = client.post("/api/register", json={
            "username": "testuser",
            "password": "Password123!",
            "type": "Patient"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 21  # User already exists
    
    def test_register_weak_password(self, setup_database):
        """Test registration with weak password"""
        response = client.post("/api/register", json={
            "username": "weakuser",
            "password": "123",
            "type": "Patient"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 400  # Validation error
    
    def test_login_success(self, test_user):
        """Test successful login"""
        response = client.post("/api/login", json={
            "username": "testuser",
            "password": "password123"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "token" in data["data"]
        assert data["data"]["user"]["id"] == "testuser"
    
    def test_login_invalid_credentials(self, test_user):
        """Test login with invalid credentials"""
        response = client.post("/api/login", json={
            "username": "testuser",
            "password": "wrongpassword"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 31  # Invalid credentials
    
    def test_login_nonexistent_user(self, setup_database):
        """Test login with nonexistent user"""
        response = client.post("/api/login", json={
            "username": "nonexistent",
            "password": "password123"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 31  # Invalid credentials
    
    def test_logout_success(self, test_user):
        """Test successful logout"""
        # First login to get token
        login_response = client.post("/api/login", json={
            "username": "testuser",
            "password": "password123"
        })
        token = login_response.json()["data"]["token"]
        
        # Then logout
        response = client.post("/api/logout", headers={
            "Authorization": f"Bearer {token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0


class TestUserEndpoints:
    """Test user management API endpoints"""
    
    def test_get_user_info(self, test_user):
        """Test getting user information"""
        # Login first
        login_response = client.post("/api/login", json={
            "username": "testuser",
            "password": "password123"
        })
        token = login_response.json()["data"]["token"]
        
        # Get user info
        response = client.get("/api/user/info", headers={
            "Authorization": f"Bearer {token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["id"] == "testuser"
        assert data["data"]["name"] == "Test User"
    
    def test_update_user_info(self, test_user):
        """Test updating user information"""
        # Login first
        login_response = client.post("/api/login", json={
            "username": "testuser",
            "password": "password123"
        })
        token = login_response.json()["data"]["token"]
        
        # Update user info
        response = client.post("/api/user/info", 
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Updated Name",
                "phone": "9876543210",
                "email": "updated@example.com"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
    
    def test_get_user_reports(self, test_user):
        """Test getting user reports"""
        # Login first
        login_response = client.post("/api/login", json={
            "username": "testuser",
            "password": "password123"
        })
        token = login_response.json()["data"]["token"]
        
        # Get user reports
        response = client.get("/api/user/report", headers={
            "Authorization": f"Bearer {token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)


class TestDoctorEndpoints:
    """Test doctor API endpoints"""
    
    def test_get_doctor_info(self, test_doctor):
        """Test getting doctor information"""
        # Login first
        login_response = client.post("/api/login", json={
            "username": "testdoctor",
            "password": "password123"
        })
        token = login_response.json()["data"]["token"]
        
        # Get doctor info
        response = client.get("/api/doctor/info", headers={
            "Authorization": f"Bearer {token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
    
    def test_update_doctor_info(self, test_doctor):
        """Test updating doctor information"""
        # Login first
        login_response = client.post("/api/login", json={
            "username": "testdoctor",
            "password": "password123"
        })
        token = login_response.json()["data"]["token"]
        
        # Update doctor info
        response = client.post("/api/doctor/info",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "position": "Senior Doctor",
                "workplace": "Test Hospital"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0


class TestAdminEndpoints:
    """Test admin API endpoints"""
    
    def test_get_all_users(self, test_admin, test_user):
        """Test getting all users (admin only)"""
        # Login as admin
        login_response = client.post("/api/login", json={
            "username": "testadmin",
            "password": "password123"
        })
        token = login_response.json()["data"]["token"]
        
        # Get all users
        response = client.get("/api/admin/users", headers={
            "Authorization": f"Bearer {token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 2  # admin and test user
    
    def test_get_system_stats(self, test_admin):
        """Test getting system statistics"""
        # Login as admin
        login_response = client.post("/api/login", json={
            "username": "testadmin",
            "password": "password123"
        })
        token = login_response.json()["data"]["token"]
        
        # Get system stats
        response = client.get("/api/admin/dashboard/stats", headers={
            "Authorization": f"Bearer {token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "total_users" in data["data"]
        assert "total_reports" in data["data"]
    
    def test_admin_access_denied_for_regular_user(self, test_user):
        """Test that regular users cannot access admin endpoints"""
        # Login as regular user
        login_response = client.post("/api/login", json={
            "username": "testuser",
            "password": "password123"
        })
        token = login_response.json()["data"]["token"]
        
        # Try to access admin endpoint
        response = client.get("/api/admin/users", headers={
            "Authorization": f"Bearer {token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 403  # Forbidden


class TestRBACEndpoints:
    """Test RBAC API endpoints"""
    
    def test_get_user_roles(self, test_admin):
        """Test getting user roles"""
        # Login as admin
        login_response = client.post("/api/login", json={
            "username": "testadmin",
            "password": "password123"
        })
        token = login_response.json()["data"]["token"]
        
        # Get user roles
        response = client.get("/api/admin/rbac/users/testadmin/roles", headers={
            "Authorization": f"Bearer {token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)
    
    def test_assign_role(self, test_admin, test_user):
        """Test assigning role to user"""
        # Login as admin
        login_response = client.post("/api/login", json={
            "username": "testadmin",
            "password": "password123"
        })
        token = login_response.json()["data"]["token"]
        
        # Create a test role first
        db = TestingSessionLocal()
        try:
            role = Role(name="test_role", description="Test Role", is_active=True)
            db.add(role)
            db.commit()
        finally:
            db.close()
        
        # Assign role to user
        response = client.post("/api/admin/rbac/users/testuser/roles",
            headers={"Authorization": f"Bearer {token}"},
            json={"role_name": "test_role"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
    
    def test_get_all_roles(self, test_admin):
        """Test getting all roles"""
        # Login as admin
        login_response = client.post("/api/login", json={
            "username": "testadmin",
            "password": "password123"
        })
        token = login_response.json()["data"]["token"]
        
        # Get all roles
        response = client.get("/api/admin/rbac/roles", headers={
            "Authorization": f"Bearer {token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)
    
    def test_create_role(self, test_admin):
        """Test creating a new role"""
        # Login as admin
        login_response = client.post("/api/login", json={
            "username": "testadmin",
            "password": "password123"
        })
        token = login_response.json()["data"]["token"]
        
        # Create new role
        response = client.post("/api/admin/rbac/roles",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "new_test_role",
                "description": "New Test Role"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
    
    def test_get_all_permissions(self, test_admin):
        """Test getting all permissions"""
        # Login as admin
        login_response = client.post("/api/login", json={
            "username": "testadmin",
            "password": "password123"
        })
        token = login_response.json()["data"]["token"]
        
        # Get all permissions
        response = client.get("/api/admin/rbac/permissions", headers={
            "Authorization": f"Bearer {token}"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)


class TestPasswordResetEndpoints:
    """Test password reset API endpoints"""
    
    def test_request_password_reset(self, test_user):
        """Test requesting password reset"""
        response = client.post("/api/auth/password-reset/request", json={
            "username": "testuser"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
    
    def test_request_password_reset_nonexistent_user(self, setup_database):
        """Test requesting password reset for nonexistent user"""
        response = client.post("/api/auth/password-reset/request", json={
            "username": "nonexistent"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 404  # User not found


class TestErrorHandling:
    """Test API error handling"""
    
    def test_unauthorized_access(self, setup_database):
        """Test unauthorized access to protected endpoints"""
        response = client.get("/api/user/info")
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 401  # Unauthorized
    
    def test_invalid_token(self, setup_database):
        """Test access with invalid token"""
        response = client.get("/api/user/info", headers={
            "Authorization": "Bearer invalid_token"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 401  # Unauthorized
    
    def test_malformed_request(self, setup_database):
        """Test malformed request handling"""
        response = client.post("/api/login", json={
            "invalid_field": "value"
        })
        
        assert response.status_code == 422  # Validation error


class TestRateLimiting:
    """Test rate limiting functionality"""
    
    def test_login_rate_limiting(self, test_user):
        """Test login rate limiting"""
        # Make multiple failed login attempts
        for i in range(6):
            response = client.post("/api/login", json={
                "username": "testuser",
                "password": "wrongpassword"
            })
            
            if i < 5:  # First 5 attempts should get authentication error
                assert response.status_code == 200
                assert response.json()["code"] == 31  # Invalid credentials
            else:  # 6th attempt should be rate limited
                assert response.status_code == 200
                assert response.json()["code"] == 429  # Rate limited


if __name__ == "__main__":
    # Run integration tests
    print("Running API integration tests...")
    
    # Test Authentication
    print("Testing Authentication endpoints...")
    pytest.main(["-v", "test_api_integration.py::TestAuthenticationEndpoints"])
    
    # Test User endpoints
    print("Testing User endpoints...")
    pytest.main(["-v", "test_api_integration.py::TestUserEndpoints"])
    
    # Test Doctor endpoints
    print("Testing Doctor endpoints...")
    pytest.main(["-v", "test_api_integration.py::TestDoctorEndpoints"])
    
    # Test Admin endpoints
    print("Testing Admin endpoints...")
    pytest.main(["-v", "test_api_integration.py::TestAdminEndpoints"])
    
    # Test RBAC endpoints
    print("Testing RBAC endpoints...")
    pytest.main(["-v", "test_api_integration.py::TestRBACEndpoints"])
    
    print("✅ All API integration tests completed!")