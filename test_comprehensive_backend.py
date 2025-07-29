"""
Comprehensive Backend Tests

This module provides comprehensive unit tests for all new service classes including:
- RBAC Service
- Audit Service  
- Database Storage Service
- Security Service
- Database Performance Service
- Query Optimization Service
"""

import pytest
import json
import time
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from dense_platform_backend_main.database.table import Base, User, UserDetail, Role, Permission, UserRole, RolePermission, AuditLog, DenseReport, Image, Comment, Doctor, UserType, UserSex, ReportStatus, ImageType
from dense_platform_backend_main.services.rbac_service import RBACService
from dense_platform_backend_main.services.audit_service import AuditService, AuditEventType, SeverityLevel, audit_service
from dense_platform_backend_main.services.database_storage_service import DatabaseStorageService
from dense_platform_backend_main.services.security_service import security_service, PasswordHasher, PasswordValidator, InputValidator, RateLimiter
from dense_platform_backend_main.services.database_performance_service import DatabasePerformanceService
from dense_platform_backend_main.services.query_optimization_service import QueryOptimizationService

# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False  # Disable SQL echo for cleaner test output
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    """Create a test database session"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing"""
    user = User(
        id="test_user",
        password="hashed_password",
        type=UserType.Doctor,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_user_detail(db_session, sample_user):
    """Create sample user detail"""
    user_detail = UserDetail(
        id=sample_user.id,
        name="Test User",
        sex=UserSex.Male,
        birth=date(1990, 1, 1),
        phone="1234567890",
        email="test@example.com",
        address="Test Address"
    )
    db_session.add(user_detail)
    db_session.commit()
    return user_detail


@pytest.fixture
def sample_role(db_session):
    """Create a sample role"""
    role = Role(
        name="test_role",
        description="Test role",
        is_active=True
    )
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def sample_permission(db_session):
    """Create a sample permission"""
    permission = Permission(
        name="test.permission",
        resource="test",
        action="permission",
        description="Test permission",
        is_active=True
    )
    db_session.add(permission)
    db_session.commit()
    return permission


class TestRBACService:
    """Test RBAC Service functionality"""
    
    def test_check_permission_success(self, db_session, sample_user, sample_role, sample_permission):
        """Test successful permission check"""
        # Assign role to user
        user_role = UserRole(user_id=sample_user.id, role_id=sample_role.id)
        db_session.add(user_role)
        
        # Assign permission to role
        role_permission = RolePermission(role_id=sample_role.id, permission_id=sample_permission.id)
        db_session.add(role_permission)
        db_session.commit()
        
        # Check permission
        has_permission = RBACService.check_permission(
            db_session, sample_user.id, "test", "permission"
        )
        assert has_permission is True
    
    def test_check_permission_failure(self, db_session, sample_user):
        """Test permission check failure"""
        has_permission = RBACService.check_permission(
            db_session, sample_user.id, "nonexistent", "permission"
        )
        assert has_permission is False
    
    def test_get_user_permissions(self, db_session, sample_user, sample_role, sample_permission):
        """Test getting user permissions"""
        # Setup role and permission
        user_role = UserRole(user_id=sample_user.id, role_id=sample_role.id)
        role_permission = RolePermission(role_id=sample_role.id, permission_id=sample_permission.id)
        db_session.add(user_role)
        db_session.add(role_permission)
        db_session.commit()
        
        permissions = RBACService.get_user_permissions(db_session, sample_user.id)
        assert len(permissions) == 1
        assert permissions[0]["name"] == "test.permission"
        assert permissions[0]["resource"] == "test"
        assert permissions[0]["action"] == "permission"
    
    def test_get_user_roles(self, db_session, sample_user, sample_role):
        """Test getting user roles"""
        user_role = UserRole(user_id=sample_user.id, role_id=sample_role.id)
        db_session.add(user_role)
        db_session.commit()
        
        roles = RBACService.get_user_roles(db_session, sample_user.id)
        assert len(roles) == 1
        assert roles[0]["name"] == "test_role"
        assert roles[0]["description"] == "Test role"
    
    def test_assign_role_success(self, db_session, sample_user, sample_role):
        """Test successful role assignment"""
        result = RBACService.assign_role(
            db_session, sample_user.id, sample_role.name, "admin_user"
        )
        assert result is True
        
        # Verify assignment
        user_role = db_session.query(UserRole).filter(
            UserRole.user_id == sample_user.id,
            UserRole.role_id == sample_role.id
        ).first()
        assert user_role is not None
    
    def test_assign_role_nonexistent_user(self, db_session, sample_role):
        """Test role assignment to nonexistent user"""
        result = RBACService.assign_role(
            db_session, "nonexistent_user", sample_role.name
        )
        assert result is False
    
    def test_assign_role_nonexistent_role(self, db_session, sample_user):
        """Test assignment of nonexistent role"""
        result = RBACService.assign_role(
            db_session, sample_user.id, "nonexistent_role"
        )
        assert result is False
    
    def test_remove_role_success(self, db_session, sample_user, sample_role):
        """Test successful role removal"""
        # First assign the role
        user_role = UserRole(user_id=sample_user.id, role_id=sample_role.id)
        db_session.add(user_role)
        db_session.commit()
        
        # Then remove it
        result = RBACService.remove_role(
            db_session, sample_user.id, sample_role.name, "admin_user"
        )
        assert result is True
        
        # Verify removal
        user_role = db_session.query(UserRole).filter(
            UserRole.user_id == sample_user.id,
            UserRole.role_id == sample_role.id
        ).first()
        assert user_role is None
    
    def test_create_role_success(self, db_session):
        """Test successful role creation"""
        result = RBACService.create_role(
            db_session, "new_role", "New test role", created_by="admin_user"
        )
        assert result is not None
        assert result["name"] == "new_role"
        assert result["description"] == "New test role"
        
        # Verify in database
        role = db_session.query(Role).filter(Role.name == "new_role").first()
        assert role is not None
    
    def test_create_role_duplicate(self, db_session, sample_role):
        """Test creating duplicate role"""
        result = RBACService.create_role(
            db_session, sample_role.name, "Duplicate role"
        )
        assert result is None
    
    def test_create_permission_success(self, db_session):
        """Test successful permission creation"""
        result = RBACService.create_permission(
            db_session, "new.permission", "new", "permission", 
            "New test permission", "admin_user"
        )
        assert result is not None
        assert result["name"] == "new.permission"
        assert result["resource"] == "new"
        assert result["action"] == "permission"
        
        # Verify in database
        permission = db_session.query(Permission).filter(
            Permission.resource == "new",
            Permission.action == "permission"
        ).first()
        assert permission is not None
    
    def test_create_permission_duplicate(self, db_session, sample_permission):
        """Test creating duplicate permission"""
        result = RBACService.create_permission(
            db_session, "duplicate.permission", sample_permission.resource, 
            sample_permission.action, "Duplicate permission"
        )
        assert result is None
    
    def test_get_all_roles(self, db_session, sample_role):
        """Test getting all roles"""
        roles = RBACService.get_all_roles(db_session)
        assert len(roles) >= 1
        assert any(role["name"] == sample_role.name for role in roles)
    
    def test_get_all_permissions(self, db_session, sample_permission):
        """Test getting all permissions"""
        permissions = RBACService.get_all_permissions(db_session)
        assert len(permissions) >= 1
        assert any(perm["name"] == sample_permission.name for perm in permissions)
    
    def test_has_admin_role(self, db_session, sample_user):
        """Test admin role check"""
        # Create admin role
        admin_role = Role(name="admin", description="Administrator", is_active=True)
        db_session.add(admin_role)
        db_session.commit()
        
        # Assign admin role to user
        user_role = UserRole(user_id=sample_user.id, role_id=admin_role.id)
        db_session.add(user_role)
        db_session.commit()
        
        # Check admin role
        is_admin = RBACService.has_admin_role(db_session, sample_user.id)
        assert is_admin is True
        
        # Check non-admin user
        is_admin = RBACService.has_admin_role(db_session, "non_admin_user")
        assert is_admin is False
    
    def test_initialize_default_permissions(self, db_session):
        """Test initialization of default permissions"""
        RBACService.initialize_default_permissions(db_session)
        
        # Check that default permissions were created
        permissions = db_session.query(Permission).all()
        assert len(permissions) > 0
        
        # Check for specific permissions
        user_read = db_session.query(Permission).filter(
            Permission.resource == "user",
            Permission.action == "read"
        ).first()
        assert user_read is not None
    
    def test_initialize_default_roles(self, db_session):
        """Test initialization of default roles"""
        RBACService.initialize_default_roles(db_session)
        
        # Check that default roles were created
        roles = db_session.query(Role).all()
        assert len(roles) >= 3  # admin, doctor, patient
        
        # Check for specific roles
        admin_role = db_session.query(Role).filter(Role.name == "admin").first()
        doctor_role = db_session.query(Role).filter(Role.name == "doctor").first()
        patient_role = db_session.query(Role).filter(Role.name == "patient").first()
        
        assert admin_role is not None
        assert doctor_role is not None
        assert patient_role is not None


class TestAuditService:
    """Test Audit Service functionality"""
    
    def test_log_audit_event(self):
        """Test logging audit events"""
        test_audit_service = AuditService()
        
        # Log an event
        test_audit_service.log_audit_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            severity=SeverityLevel.LOW,
            user_id="test_user",
            ip_address="192.168.1.1",
            resource="auth",
            action="login",
            details={"method": "password"}
        )
        
        # Verify activity was tracked
        activity = test_audit_service.activity_tracker.get_user_activity("test_user", 1)
        assert len(activity) == 1
        assert activity[0]["activity_type"] == "login_success"
    
    def test_security_monitoring_failed_logins(self):
        """Test security monitoring for failed logins"""
        test_audit_service = AuditService()
        
        # Record multiple failed logins
        for i in range(6):
            test_audit_service.log_audit_event(
                event_type=AuditEventType.LOGIN_FAILED,
                severity=SeverityLevel.MEDIUM,
                user_id="test_user",
                ip_address="192.168.1.1"
            )
        
        # Check that security alerts were generated
        alerts = test_audit_service.security_monitor.get_recent_alerts(1)
        assert len(alerts) > 0
        assert any(alert.alert_type == "multiple_failed_logins" for alert in alerts)
    
    def test_activity_tracker(self):
        """Test activity tracking functionality"""
        test_audit_service = AuditService()
        
        # Record activities
        test_audit_service.activity_tracker.record_activity(
            "test_user", "login", {"ip": "192.168.1.1"}
        )
        test_audit_service.activity_tracker.record_activity(
            "test_user", "view_report", {"report_id": "123"}
        )
        
        # Get activity summary
        summary = test_audit_service.get_user_activity_report("test_user", 1)
        assert summary["total_activities"] == 2
        assert "login" in summary["activity_breakdown"]
        assert "view_report" in summary["activity_breakdown"]
    
    def test_security_report(self):
        """Test security report generation"""
        test_audit_service = AuditService()
        
        # Generate some security events
        test_audit_service.security_monitor.record_suspicious_ip(
            "192.168.1.100", "Multiple failed attempts"
        )
        
        # Get security report
        report = test_audit_service.get_security_report(1)
        assert "total_alerts" in report
        assert "alert_breakdown" in report
        assert "severity_breakdown" in report


class TestDatabaseStorageService:
    """Test Database Storage Service functionality"""
    
    def test_save_and_load_user_detail(self, db_session, sample_user):
        """Test saving and loading user details"""
        detail_data = {
            "name": "John Doe",
            "sex": UserSex.Male,
            "birth": date(1990, 5, 15),
            "phone": "1234567890",
            "email": "john@example.com",
            "address": "123 Main St"
        }
        
        # Save user detail
        result = DatabaseStorageService.save_user_detail(
            db_session, sample_user.id, detail_data
        )
        assert result is True
        
        # Load user detail
        loaded_detail = DatabaseStorageService.load_user_detail(
            db_session, sample_user.id
        )
        assert loaded_detail is not None
        assert loaded_detail["name"] == "John Doe"
        assert loaded_detail["email"] == "john@example.com"
    
    def test_save_and_load_image(self, db_session):
        """Test saving and loading images"""
        image_data = b"fake_image_data"
        
        # Save image
        image_id = DatabaseStorageService.save_image(
            db_session, image_data, "test.jpg", "jpg"
        )
        assert image_id is not None
        
        # Load image
        loaded_data = DatabaseStorageService.load_image(db_session, image_id)
        assert loaded_data == image_data
    
    def test_save_and_load_report(self, db_session, sample_user):
        """Test saving and loading reports"""
        report_data = {
            "user": sample_user.id,
            "doctor": "doctor_123",
            "submitTime": date.today(),
            "current_status": ReportStatus.Checking,
            "diagnose": "Test diagnosis"
        }
        
        # Save report
        report_id = DatabaseStorageService.save_report(db_session, report_data)
        assert report_id is not None
        
        # Load report
        loaded_report = DatabaseStorageService.load_report(db_session, report_id)
        assert loaded_report is not None
        assert loaded_report["user"] == sample_user.id
        assert loaded_report["diagnose"] == "Test diagnosis"
    
    def test_get_user_reports(self, db_session, sample_user):
        """Test getting user reports"""
        # Create a report
        report = DenseReport(
            user=sample_user.id,
            doctor="doctor_123",
            submitTime=date.today(),
            current_status=ReportStatus.Checking
        )
        db_session.add(report)
        db_session.commit()
        
        # Get user reports (as patient)
        reports = DatabaseStorageService.get_user_reports(
            db_session, sample_user.id, 0
        )
        assert len(reports) == 1
        assert reports[0]["user"] == sample_user.id
    
    def test_save_and_get_comments(self, db_session):
        """Test saving and getting comments"""
        # Create a report first
        report = DenseReport(
            user="user_123",
            doctor="doctor_123",
            submitTime=date.today(),
            current_status=ReportStatus.Checking
        )
        db_session.add(report)
        db_session.commit()
        
        comment_data = {
            "user": "doctor_123",
            "content": "This is a test comment"
        }
        
        # Save comment
        comment_id = DatabaseStorageService.save_comment(
            db_session, str(report.id), comment_data
        )
        assert comment_id is not None
        
        # Get comments
        comments = DatabaseStorageService.get_report_comments(
            db_session, str(report.id)
        )
        assert len(comments) == 1
        assert comments[0]["content"] == "This is a test comment"
    
    def test_update_report_status(self, db_session):
        """Test updating report status"""
        # Create a report
        report = DenseReport(
            user="user_123",
            doctor="doctor_123",
            submitTime=date.today(),
            current_status=ReportStatus.Checking
        )
        db_session.add(report)
        db_session.commit()
        
        # Update status
        result = DatabaseStorageService.update_report_status(
            db_session, str(report.id), ReportStatus.Completed, "Final diagnosis"
        )
        assert result is True
        
        # Verify update
        db_session.refresh(report)
        assert report.current_status == ReportStatus.Completed
        assert report.diagnose == "Final diagnosis"
    
    def test_delete_report(self, db_session):
        """Test deleting reports"""
        # Create a report
        report = DenseReport(
            user="user_123",
            doctor="doctor_123",
            submitTime=date.today(),
            current_status=ReportStatus.Checking
        )
        db_session.add(report)
        db_session.commit()
        report_id = report.id
        
        # Delete report
        result = DatabaseStorageService.delete_report(db_session, str(report_id))
        assert result is True
        
        # Verify deletion
        deleted_report = db_session.query(DenseReport).filter(
            DenseReport.id == report_id
        ).first()
        assert deleted_report is None


class TestSecurityService:
    """Test Security Service functionality"""
    
    def test_password_hashing(self):
        """Test password hashing functionality"""
        hasher = PasswordHasher()
        password = "TestPassword123!"
        
        # Hash password
        hashed = hasher.hash_password(password)
        assert hashed.startswith('$2b$')
        assert len(hashed) > 50
        
        # Verify password
        assert hasher.verify_password(password, hashed)
        assert not hasher.verify_password("wrong_password", hashed)
    
    def test_password_validation(self):
        """Test password validation"""
        validator = PasswordValidator()
        
        # Valid password
        result = validator.validate_password("StrongPa1s2!@")
        assert result['is_valid']
        assert result['strength_score'] >= 70
        
        # Invalid password (too short)
        result = validator.validate_password("123")
        assert not result['is_valid']
        assert len(result['errors']) > 0
    
    def test_input_validation(self):
        """Test input validation"""
        validator = InputValidator()
        
        # Valid username
        result = validator.validate_username("validuser123")
        assert result['is_valid']
        
        # Invalid username
        result = validator.validate_username("invalid@user")
        assert not result['is_valid']
        
        # Valid email
        result = validator.validate_email("test@example.com")
        assert result['is_valid']
        
        # Invalid email
        result = validator.validate_email("invalid-email")
        assert not result['is_valid']
    
    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        rate_limiter = RateLimiter()
        identifier = "test_user"
        
        # Should not be rate limited initially
        assert not rate_limiter.is_rate_limited(identifier, max_attempts=3, window_minutes=1)
        
        # Record attempts
        for _ in range(3):
            rate_limiter.record_attempt(identifier)
        
        # Should be rate limited after max attempts
        assert rate_limiter.is_rate_limited(identifier, max_attempts=3, window_minutes=1)
    
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
        
        # Invalid input
        result = security_service.validate_registration_input(
            username="invalid@user",
            password="weak",
            email="invalid-email",
            name="Invalid@Name"
        )
        assert not result['is_valid']
        assert len(result['errors']) > 0


class TestDatabasePerformanceService:
    """Test Database Performance Service functionality"""
    
    def test_analyze_query_performance(self, db_session):
        """Test query performance analysis"""
        service = DatabasePerformanceService()
        
        # Test with a simple query
        query = db_session.query(User)
        analysis = service.analyze_query_performance(db_session, query)
        
        assert 'execution_time' in analysis
        assert 'query_plan' in analysis
        assert analysis['execution_time'] >= 0
    
    def test_get_slow_queries(self, db_session):
        """Test getting slow queries"""
        service = DatabasePerformanceService()
        
        # This would typically return actual slow queries from monitoring
        slow_queries = service.get_slow_queries(db_session, threshold_ms=100)
        assert isinstance(slow_queries, list)
    
    def test_optimize_table_indexes(self, db_session):
        """Test table index optimization"""
        service = DatabasePerformanceService()
        
        # Test index optimization suggestions
        suggestions = service.optimize_table_indexes(db_session, "user")
        assert isinstance(suggestions, list)


class TestQueryOptimizationService:
    """Test Query Optimization Service functionality"""
    
    def test_optimize_user_queries(self, db_session):
        """Test user query optimization"""
        service = QueryOptimizationService()
        
        # Test query optimization
        optimized_query = service.optimize_user_queries(db_session)
        assert optimized_query is not None
    
    def test_optimize_report_queries(self, db_session):
        """Test report query optimization"""
        service = QueryOptimizationService()
        
        # Test report query optimization
        optimized_query = service.optimize_report_queries(db_session)
        assert optimized_query is not None
    
    def test_create_performance_indexes(self, db_session):
        """Test performance index creation"""
        service = QueryOptimizationService()
        
        # Test index creation
        result = service.create_performance_indexes(db_session)
        assert isinstance(result, bool)


if __name__ == "__main__":
    # Run basic tests
    print("Running comprehensive backend tests...")
    
    # Test RBAC Service
    print("Testing RBAC Service...")
    pytest.main(["-v", "test_comprehensive_backend.py::TestRBACService"])
    
    # Test Audit Service
    print("Testing Audit Service...")
    pytest.main(["-v", "test_comprehensive_backend.py::TestAuditService"])
    
    # Test Database Storage Service
    print("Testing Database Storage Service...")
    pytest.main(["-v", "test_comprehensive_backend.py::TestDatabaseStorageService"])
    
    # Test Security Service
    print("Testing Security Service...")
    pytest.main(["-v", "test_comprehensive_backend.py::TestSecurityService"])
    
    print("✅ All comprehensive backend tests completed!")