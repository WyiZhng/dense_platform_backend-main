"""
Simple unit tests for RBAC system functionality
"""

import pytest
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

# Simple test models for RBAC testing
TestBase = declarative_base()


class TestUserType(enum.IntEnum):
    Patient = 0
    Doctor = 1


class TestUser(TestBase):
    __tablename__ = 'test_user'
    
    id = Column(String(20), primary_key=True)
    password = Column(String(64), nullable=False)
    type = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    roles = relationship('TestRole', secondary='test_user_role', back_populates='users')


class TestRole(TestBase):
    __tablename__ = 'test_role'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    users = relationship('TestUser', secondary='test_user_role', back_populates='roles')
    permissions = relationship('TestPermission', secondary='test_role_permission', back_populates='roles')


class TestUserRole(TestBase):
    __tablename__ = 'test_user_role'
    
    user_id = Column(String(20), ForeignKey('test_user.id', ondelete='CASCADE'), primary_key=True)
    role_id = Column(Integer, ForeignKey('test_role.id', ondelete='CASCADE'), primary_key=True)


class TestPermission(TestBase):
    __tablename__ = 'test_permission'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    resource = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    roles = relationship('TestRole', secondary='test_role_permission', back_populates='permissions')


class TestRolePermission(TestBase):
    __tablename__ = 'test_role_permission'
    
    role_id = Column(Integer, ForeignKey('test_role.id', ondelete='CASCADE'), primary_key=True)
    permission_id = Column(Integer, ForeignKey('test_permission.id', ondelete='CASCADE'), primary_key=True)
    granted_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_rbac_simple.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    """Create a test database session"""
    TestBase.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        TestBase.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing"""
    user = TestUser(
        id="test_user",
        password="hashed_password",
        type=TestUserType.Doctor,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_create_permission(db_session):
    """Test creating a new permission"""
    permission = TestPermission(
        name="test.permission",
        resource="test",
        action="permission",
        description="Test permission",
        is_active=True
    )
    db_session.add(permission)
    db_session.commit()
    
    # Verify permission was created
    saved_permission = db_session.query(TestPermission).filter(
        TestPermission.name == "test.permission"
    ).first()
    
    assert saved_permission is not None
    assert saved_permission.name == "test.permission"
    assert saved_permission.resource == "test"
    assert saved_permission.action == "permission"


def test_create_role(db_session):
    """Test creating a new role"""
    role = TestRole(
        name="test_role",
        description="Test role",
        is_active=True
    )
    db_session.add(role)
    db_session.commit()
    
    # Verify role was created
    saved_role = db_session.query(TestRole).filter(
        TestRole.name == "test_role"
    ).first()
    
    assert saved_role is not None
    assert saved_role.name == "test_role"
    assert saved_role.description == "Test role"


def test_assign_role_to_user(db_session, sample_user):
    """Test assigning a role to a user"""
    # Create a role
    role = TestRole(
        name="doctor",
        description="Medical doctor",
        is_active=True
    )
    db_session.add(role)
    db_session.commit()
    
    # Assign role to user
    user_role = TestUserRole(
        user_id=sample_user.id,
        role_id=role.id
    )
    db_session.add(user_role)
    db_session.commit()
    
    # Verify assignment
    assignment = db_session.query(TestUserRole).filter(
        TestUserRole.user_id == sample_user.id,
        TestUserRole.role_id == role.id
    ).first()
    
    assert assignment is not None


def test_assign_permission_to_role(db_session):
    """Test assigning a permission to a role"""
    # Create role and permission
    role = TestRole(name="test_role", is_active=True)
    permission = TestPermission(
        name="test.permission",
        resource="test",
        action="permission",
        is_active=True
    )
    
    db_session.add(role)
    db_session.add(permission)
    db_session.commit()
    
    # Assign permission to role
    role_permission = TestRolePermission(
        role_id=role.id,
        permission_id=permission.id
    )
    db_session.add(role_permission)
    db_session.commit()
    
    # Verify assignment
    assignment = db_session.query(TestRolePermission).filter(
        TestRolePermission.role_id == role.id,
        TestRolePermission.permission_id == permission.id
    ).first()
    
    assert assignment is not None


def test_user_has_permission_through_role(db_session, sample_user):
    """Test checking if user has permission through role assignment"""
    # Create role and permission
    role = TestRole(name="doctor", is_active=True)
    permission = TestPermission(
        name="doctor.diagnose",
        resource="doctor",
        action="diagnose",
        is_active=True
    )
    
    db_session.add(role)
    db_session.add(permission)
    db_session.commit()
    
    # Assign permission to role
    role_permission = TestRolePermission(
        role_id=role.id,
        permission_id=permission.id
    )
    db_session.add(role_permission)
    
    # Assign role to user
    user_role = TestUserRole(
        user_id=sample_user.id,
        role_id=role.id
    )
    db_session.add(user_role)
    db_session.commit()
    
    # Check if user has permission through role
    user_permission = db_session.query(TestPermission).join(
        TestRolePermission, TestPermission.id == TestRolePermission.permission_id
    ).join(
        TestRole, TestRolePermission.role_id == TestRole.id
    ).join(
        TestUserRole, TestRole.id == TestUserRole.role_id
    ).filter(
        TestUserRole.user_id == sample_user.id,
        TestPermission.resource == "doctor",
        TestPermission.action == "diagnose",
        TestPermission.is_active == True,
        TestRole.is_active == True
    ).first()
    
    assert user_permission is not None
    assert user_permission.name == "doctor.diagnose"


def test_get_user_roles(db_session, sample_user):
    """Test getting all roles for a user"""
    # Create multiple roles
    role1 = TestRole(name="doctor", description="Medical doctor", is_active=True)
    role2 = TestRole(name="admin", description="Administrator", is_active=True)
    
    db_session.add(role1)
    db_session.add(role2)
    db_session.commit()
    
    # Assign roles to user
    user_role1 = TestUserRole(user_id=sample_user.id, role_id=role1.id)
    user_role2 = TestUserRole(user_id=sample_user.id, role_id=role2.id)
    
    db_session.add(user_role1)
    db_session.add(user_role2)
    db_session.commit()
    
    # Get user roles
    user_roles = db_session.query(TestRole).join(
        TestUserRole, TestRole.id == TestUserRole.role_id
    ).filter(
        TestUserRole.user_id == sample_user.id,
        TestRole.is_active == True
    ).all()
    
    assert len(user_roles) == 2
    role_names = [role.name for role in user_roles]
    assert "doctor" in role_names
    assert "admin" in role_names


def test_get_user_permissions(db_session, sample_user):
    """Test getting all permissions for a user"""
    # Create role and permissions
    role = TestRole(name="doctor", is_active=True)
    perm1 = TestPermission(name="doctor.diagnose", resource="doctor", action="diagnose", is_active=True)
    perm2 = TestPermission(name="report.read", resource="report", action="read", is_active=True)
    
    db_session.add(role)
    db_session.add(perm1)
    db_session.add(perm2)
    db_session.commit()
    
    # Assign permissions to role
    role_perm1 = TestRolePermission(role_id=role.id, permission_id=perm1.id)
    role_perm2 = TestRolePermission(role_id=role.id, permission_id=perm2.id)
    
    db_session.add(role_perm1)
    db_session.add(role_perm2)
    
    # Assign role to user
    user_role = TestUserRole(user_id=sample_user.id, role_id=role.id)
    db_session.add(user_role)
    db_session.commit()
    
    # Get user permissions
    user_permissions = db_session.query(TestPermission).join(
        TestRolePermission, TestPermission.id == TestRolePermission.permission_id
    ).join(
        TestRole, TestRolePermission.role_id == TestRole.id
    ).join(
        TestUserRole, TestRole.id == TestUserRole.role_id
    ).filter(
        TestUserRole.user_id == sample_user.id,
        TestPermission.is_active == True,
        TestRole.is_active == True
    ).distinct().all()
    
    assert len(user_permissions) == 2
    permission_names = [perm.name for perm in user_permissions]
    assert "doctor.diagnose" in permission_names
    assert "report.read" in permission_names


if __name__ == "__main__":
    pytest.main([__file__])