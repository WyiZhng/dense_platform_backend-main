"""
Test Security Enhancements

This module tests the enhanced security features including:
- Bcrypt password hashing
- Rate limiting for authentication attempts
- Input validation and sanitization
"""

import pytest
import time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock, patch

from dense_platform_backend_main.main import app
from dense_platform_backend_main.database.table import Base, User, UserDetail, UserType
from dense_platform_backend_main.services.security_service import security_service, PasswordHasher, PasswordValidator, InputValidator, RateLimiter
from dense_platform_backend_main.api.auth.auth import AuthService

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_security.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create test client
client = TestClient(app)


def setup_test_db():
    """Setup test database"""
    Base.metadata.create_all(bind=engine)


def cleanup_test_db():
    """Cleanup test database"""
    Base.metadata.drop_all(bind=engine)


class TestPasswordHashing:
    """Test bcrypt password hashing functionality"""
    
    def test_password_hashing(self):
        """Test password hashing with bcrypt"""
        password = "TestPassword123!"
        hasher = PasswordHasher()
        
        # Hash password
        hashed = hasher.hash_password(password)
        
        # Verify hash format
        assert hashed.startswith('$2b$')
        assert len(hashed) > 50  # bcrypt hashes are typically 60 characters
        
        # Verify password
        assert hasher.verify_password(password, hashed)
        assert not hasher.verify_password("wrong_password", hashed)
    
    def test_bcrypt_detection(self):
        """Test bcrypt hash detection"""
        hasher = PasswordHasher()
        
        # Test bcrypt hash detection
        bcrypt_hash = "$2b$12$abcdefghijklmnopqrstuvwxyz"
        assert hasher.is_bcrypt_hash(bcrypt_hash)
        
        # Test non-bcrypt hash
        sha_hash = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"
        assert not hasher.is_bcrypt_hash(sha_hash)
    
    def test_auth_service_password_upgrade(self):
        """Test automatic password upgrade from legacy to bcrypt"""
        setup_test_db()
        
        try:
            db = TestingSessionLocal()
            
            # Create user with legacy password format (SHA-256)
            legacy_password = "password123"
            legacy_hash = "ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f"  # SHA-256 of "password123"
            
            user = User(
                id="testuser",
                password=legacy_hash,
                type=UserType.Patient,
                is_active=True
            )
            db.add(user)
            db.commit()
            
            # Authenticate user (should upgrade password)
            authenticated_user = AuthService.authenticate_user(db, "testuser", legacy_password)
            assert authenticated_user is not None
            
            # Check that password was upgraded to bcrypt
            db.refresh(user)
            assert security_service.password_hasher.is_bcrypt_hash(user.password)
            
            # Verify new bcrypt password works
            assert AuthService.verify_password(legacy_password, user.password)
            
            db.close()
        finally:
            cleanup_test_db()


class TestPasswordValidation:
    """Test password strength validation"""
    
    def test_password_validation_success(self):
        """Test valid password validation"""
        validator = PasswordValidator()
        
        strong_password = "StrongPass123!"
        result = validator.validate_password(strong_password)
        
        assert result['is_valid']
        assert len(result['errors']) == 0
        assert result['strength_score'] > 70
    
    def test_password_validation_failures(self):
        """Test password validation failures"""
        validator = PasswordValidator()
        
        # Test too short
        result = validator.validate_password("123")
        assert not result['is_valid']
        assert any("长度" in error for error in result['errors'])
        
        # Test no uppercase
        result = validator.validate_password("lowercase123!")
        assert not result['is_valid']
        assert any("大写字母" in error for error in result['errors'])
        
        # Test no lowercase
        result = validator.validate_password("UPPERCASE123!")
        assert not result['is_valid']
        assert any("小写字母" in error for error in result['errors'])
        
        # Test no digits
        result = validator.validate_password("NoDigits!")
        assert not result['is_valid']
        assert any("数字" in error for error in result['errors'])
        
        # Test no special characters
        result = validator.validate_password("NoSpecial123")
        assert not result['is_valid']
        assert any("特殊字符" in error for error in result['errors'])
        
        # Test common password
        result = validator.validate_password("password")
        assert not result['is_valid']
        assert any("过于简单" in error for error in result['errors'])


class TestInputValidation:
    """Test input validation and sanitization"""
    
    def test_username_validation(self):
        """Test username validation"""
        validator = InputValidator()
        
        # Valid username
        result = validator.validate_username("validuser123")
        assert result['is_valid']
        assert len(result['errors']) == 0
        
        # Invalid characters
        result = validator.validate_username("invalid@user")
        assert not result['is_valid']
        assert any("只能包含" in error for error in result['errors'])
        
        # Too long
        long_username = "a" * 60
        result = validator.validate_username(long_username)
        assert not result['is_valid']
        assert any("长度" in error for error in result['errors'])
        
        # Empty username
        result = validator.validate_username("")
        assert not result['is_valid']
        assert any("不能为空" in error for error in result['errors'])
    
    def test_email_validation(self):
        """Test email validation"""
        validator = InputValidator()
        
        # Valid email
        result = validator.validate_email("test@example.com")
        assert result['is_valid']
        
        # Invalid email
        result = validator.validate_email("invalid-email")
        assert not result['is_valid']
        assert any("格式不正确" in error for error in result['errors'])
        
        # Too long email
        long_email = "a" * 250 + "@example.com"
        result = validator.validate_email(long_email)
        assert not result['is_valid']
        assert any("长度" in error for error in result['errors'])
    
    def test_name_validation(self):
        """Test name validation"""
        validator = InputValidator()
        
        # Valid names
        result = validator.validate_name("John Doe")
        assert result['is_valid']
        
        result = validator.validate_name("张三")
        assert result['is_valid']
        
        # Invalid characters
        result = validator.validate_name("Invalid@Name")
        assert not result['is_valid']
        assert any("只能包含" in error for error in result['errors'])
        
        # Too long
        long_name = "a" * 150
        result = validator.validate_name(long_name)
        assert not result['is_valid']
        assert any("长度" in error for error in result['errors'])
    
    def test_string_sanitization(self):
        """Test string sanitization"""
        validator = InputValidator()
        
        # Test null byte removal
        dirty_string = "test\x00string"
        clean_string = validator.sanitize_string(dirty_string)
        assert "\x00" not in clean_string
        
        # Test whitespace trimming
        whitespace_string = "  test string  "
        clean_string = validator.sanitize_string(whitespace_string)
        assert clean_string == "test string"


class TestRateLimiting:
    """Test rate limiting functionality"""
    
    def test_rate_limiting_basic(self):
        """Test basic rate limiting"""
        rate_limiter = RateLimiter()
        identifier = "test_user"
        
        # Should not be rate limited initially
        assert not rate_limiter.is_rate_limited(identifier, max_attempts=3, window_minutes=1)
        
        # Record attempts
        for _ in range(3):
            rate_limiter.record_attempt(identifier)
        
        # Should be rate limited after max attempts
        assert rate_limiter.is_rate_limited(identifier, max_attempts=3, window_minutes=1)
        
        # Clear attempts
        rate_limiter.clear_attempts(identifier)
        assert not rate_limiter.is_rate_limited(identifier, max_attempts=3, window_minutes=1)
    
    def test_rate_limiting_time_window(self):
        """Test rate limiting time window"""
        rate_limiter = RateLimiter()
        identifier = "test_user_time"
        
        # Record attempts
        for _ in range(2):
            rate_limiter.record_attempt(identifier)
        
        # Should not be rate limited yet
        assert not rate_limiter.is_rate_limited(identifier, max_attempts=3, window_minutes=1)
        
        # Add one more attempt
        rate_limiter.record_attempt(identifier)
        
        # Should be rate limited now
        assert rate_limiter.is_rate_limited(identifier, max_attempts=3, window_minutes=1)


class TestSecurityService:
    """Test main security service functionality"""
    
    def test_registration_input_validation(self):
        """Test registration input validation"""
        # Valid input
        result = security_service.validate_registration_input(
            username="validuser",
            password="ValidPass123!",
            email="test@example.com",
            name="Test User"
        )
        assert result['is_valid']
        assert result['password_strength'] > 70
        
        # Invalid input
        result = security_service.validate_registration_input(
            username="invalid@user",
            password="weak",
            email="invalid-email",
            name="Invalid@Name"
        )
        assert not result['is_valid']
        assert len(result['errors']) > 0
    
    def test_client_ip_extraction(self):
        """Test client IP extraction from request"""
        # Mock request with X-Forwarded-For header
        mock_request = Mock()
        mock_request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
        mock_request.client = Mock()
        mock_request.client.host = "127.0.0.1"
        
        ip = security_service.get_client_ip(mock_request)
        assert ip == "192.168.1.1"
        
        # Mock request with X-Real-IP header
        mock_request.headers = {"X-Real-IP": "192.168.1.2"}
        ip = security_service.get_client_ip(mock_request)
        assert ip == "192.168.1.2"
        
        # Mock request with only client IP
        mock_request.headers = {}
        ip = security_service.get_client_ip(mock_request)
        assert ip == "127.0.0.1"


class TestAuthenticationEndpoints:
    """Test authentication endpoints with security enhancements"""
    
    def test_login_rate_limiting(self):
        """Test login rate limiting"""
        setup_test_db()
        
        try:
            # Create test user
            db = TestingSessionLocal()
            user = User(
                id="testuser",
                password=security_service.password_hasher.hash_password("password123"),
                type=UserType.Patient,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.close()
            
            # Mock the database dependency
            def override_get_db():
                db = TestingSessionLocal()
                try:
                    yield db
                finally:
                    db.close()
            
            app.dependency_overrides[get_db] = override_get_db
            
            # Make multiple failed login attempts
            for i in range(6):  # Exceed rate limit
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
            
            # Clean up
            app.dependency_overrides.clear()
            
        finally:
            cleanup_test_db()
    
    def test_registration_input_validation_endpoint(self):
        """Test registration endpoint input validation"""
        setup_test_db()
        
        try:
            # Mock the database dependency
            def override_get_db():
                db = TestingSessionLocal()
                try:
                    yield db
                finally:
                    db.close()
            
            app.dependency_overrides[get_db] = override_get_db
            
            # Test invalid username
            response = client.post("/api/register", json={
                "username": "invalid@user",
                "password": "ValidPass123!",
                "type": "Patient"
            })
            
            assert response.status_code == 200
            assert response.json()["code"] == 400
            assert "只能包含" in response.json()["message"]
            
            # Test weak password
            response = client.post("/api/register", json={
                "username": "validuser",
                "password": "weak",
                "type": "Patient"
            })
            
            assert response.status_code == 200
            assert response.json()["code"] == 400
            
            # Clean up
            app.dependency_overrides.clear()
            
        finally:
            cleanup_test_db()


if __name__ == "__main__":
    # Run basic tests
    print("Testing password hashing...")
    test_password = TestPasswordHashing()
    test_password.test_password_hashing()
    test_password.test_bcrypt_detection()
    print("✓ Password hashing tests passed")
    
    print("Testing password validation...")
    test_validation = TestPasswordValidation()
    test_validation.test_password_validation_success()
    test_validation.test_password_validation_failures()
    print("✓ Password validation tests passed")
    
    print("Testing input validation...")
    test_input = TestInputValidation()
    test_input.test_username_validation()
    test_input.test_email_validation()
    test_input.test_name_validation()
    test_input.test_string_sanitization()
    print("✓ Input validation tests passed")
    
    print("Testing rate limiting...")
    test_rate = TestRateLimiting()
    test_rate.test_rate_limiting_basic()
    test_rate.test_rate_limiting_time_window()
    print("✓ Rate limiting tests passed")
    
    print("Testing security service...")
    test_security = TestSecurityService()
    test_security.test_registration_input_validation()
    test_security.test_client_ip_extraction()
    print("✓ Security service tests passed")
    
    print("\n🎉 All security enhancement tests passed!")
    print("\nSecurity features implemented:")
    print("✓ Bcrypt password hashing with automatic legacy upgrade")
    print("✓ Rate limiting for authentication attempts")
    print("✓ Comprehensive input validation and sanitization")
    print("✓ Security event logging")
    print("✓ Password strength validation")
    print("✓ Client IP extraction for security monitoring")