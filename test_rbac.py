"""
Unit tests for RBAC system
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dense_platform_backend_main.database.table import Base, User, Role, Permission, UserType
from dense_platform_backend_main.services.rbac_service import RBACService

# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_rbac.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
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


def test_initialize_default_permissions(db_session):
    """Test initialization of default permissions"""
    RBACService.initialize_default_permissions(db_session)
    
    permissions = RBACService.get_all_permissions(db_session)
    assert len(permissions) > 0
    
    # Check for specific permissions
    permission_names = [p["name"] for p in permissions]
    assert "user.read" in permission_names
    assert "admin.system" in permission_names
    assert "doctor.diagnose" in permission_names


def test_initialize_default_roles(db_session):
    """Test initialization of default roles"""
    RBACService.initialize_default_roles(db_session)
    
    roles = RBACService.get_all_roles(db_session)
    assert len(roles) >= 3
    
    # Check for specific roles
    role_names = [r["name"] for r in roles]
    assert "admin" in role_names
    assert "doctor" in role_names
    assert "patient" in role_names


def test_create_permission(db_session):
    """Test creating a new permission"""
    permission = RBACService.create_permission(
        db=db_session,
        name="test.permission",
        resource="test",
        action="permission",
        description="Test permission",
        created_by="admin"
    )
    
    assert permission is not None
    assert permission["name"] == "test.permission"
    assert permission["resource"] == "test"
    assert permission["action"] == "permission"


def test_create_role(db_session):
    """Test creating a new role"""
    # First create some permissions
    RBACService.initialize_default_permissions(db_session)
    
    role = RBACService.create_role(
        db=db_session,
        name="test_role",
        description="Test role",
        permissions=["user.read", "user.write"],
        created_by="admin"
    )
    
    assert role is not None
    assert role["name"] == "test_role"
    assert role["description"] == "Test role"


def test_assign_role_to_user(db_session, sample_user):
    """Test assigning a role to a user"""
    # Initialize default roles
    RBACService.initialize_default_roles(db_session)
    
    # Assign doctor role to user
    success = RBACService.assign_role(
        db=db_session,
        user_id=sample_user.id,
        role_name="doctor",
        assigned_by="admin"
    )
    
    assert success is True
    
    # Check user has the role
    user_roles = RBACService.get_user_roles(db_session, sample_user.id)
    role_names = [r["name"] for r in user_roles]
    assert "doctor" in role_names


def test_check_permission(db_session, sample_user):
    """Test checking user permissions"""
    # Initialize system
    RBACService.initialize_default_roles(db_session)
    
    # Assign doctor role
    RBACService.assign_role(
        db=db_session,
        user_id=sample_user.id,
        role_name="doctor",
        assigned_by="admin"
    )
    
    # Check doctor permissions
    has_diagnose = RBACService.check_permission(
        db_session, sample_user.id, "doctor", "diagnose"
    )
    assert has_diagnose is True
    
    # Check permission user doesn't have
    has_admin = RBACService.check_permission(
        db_session, sample_user.id, "admin", "system"
    )
    assert has_admin is False


def test_remove_role_from_user(db_session, sample_user):
    """Test removing a role from a user"""
    # Initialize and assign role
    RBACService.initialize_default_roles(db_session)
    RBACService.assign_role(
        db=db_session,
        user_id=sample_user.id,
        role_name="doctor",
        assigned_by="admin"
    )
    
    # Remove role
    success = RBACService.remove_role(
        db=db_session,
        user_id=sample_user.id,
        role_name="doctor",
        removed_by="admin"
    )
    
    assert success is True
    
    # Check role is removed
    user_roles = RBACService.get_user_roles(db_session, sample_user.id)
    role_names = [r["name"] for r in user_roles]
    assert "doctor" not in role_names


def test_get_user_permissions(db_session, sample_user):
    """Test getting all permissions for a user"""
    # Initialize system and assign role
    RBACService.initialize_default_roles(db_session)
    RBACService.assign_role(
        db=db_session,
        user_id=sample_user.id,
        role_name="doctor",
        assigned_by="admin"
    )
    
    # Get user permissions
    permissions = RBACService.get_user_permissions(db_session, sample_user.id)
    
    assert len(permissions) > 0
    permission_names = [p["name"] for p in permissions]
    assert "doctor.diagnose" in permission_names
    assert "report.read" in permission_names


def test_has_admin_role(db_session, sample_user):
    """Test checking if user has admin role"""
    # Initialize system
    RBACService.initialize_default_roles(db_session)
    
    # User should not have admin role initially
    assert RBACService.has_admin_role(db_session, sample_user.id) is False
    
    # Assign admin role
    RBACService.assign_role(
        db=db_session,
        user_id=sample_user.id,
        role_name="admin",
        assigned_by="system"
    )
    
    # User should now have admin role
    assert RBACService.has_admin_role(db_session, sample_user.id) is True


def test_assign_permission_to_role(db_session):
    """Test assigning a permission to a role"""
    # Initialize system
    RBACService.initialize_default_roles(db_session)
    
    # Get a role and permission
    roles = RBACService.get_all_roles(db_session)
    permissions = RBACService.get_all_permissions(db_session)
    
    test_role = next(r for r in roles if r["name"] == "patient")
    test_permission = next(p for p in permissions if p["name"] == "user.read")
    
    # Assign permission to role
    success = RBACService.assign_permission_to_role(
        db=db_session,
        role_id=test_role["id"],
        permission_id=test_permission["id"],
        granted_by="admin"
    )
    
    assert success is True
    
    # Check role has the permission
    role_permissions = RBACService.get_role_permissions(db_session, test_role["id"])
    permission_names = [p["name"] for p in role_permissions]
    assert "user.read" in permission_names


if __name__ == "__main__":
    pytest.main([__file__])