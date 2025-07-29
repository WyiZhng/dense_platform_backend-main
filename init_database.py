#!/usr/bin/env python3
"""
Database initialization script
Creates default roles, permissions, and initial data
"""

from sqlalchemy.orm import sessionmaker
from database.table import Base, Role, Permission, RolePermission, User, UserType
from database.db import engine
import hashlib

# Create session
Session = sessionmaker(bind=engine)

def create_default_permissions():
    """Create default permissions for the system"""
    session = Session()
    
    try:
        # Define default permissions
        default_permissions = [
            # User management permissions
            {'name': 'user.create', 'resource': 'user', 'action': 'create', 'description': 'Create new users'},
            {'name': 'user.read', 'resource': 'user', 'action': 'read', 'description': 'View user information'},
            {'name': 'user.update', 'resource': 'user', 'action': 'update', 'description': 'Update user information'},
            {'name': 'user.delete', 'resource': 'user', 'action': 'delete', 'description': 'Delete users'},
            
            # Report management permissions
            {'name': 'report.create', 'resource': 'report', 'action': 'create', 'description': 'Create new reports'},
            {'name': 'report.read', 'resource': 'report', 'action': 'read', 'description': 'View reports'},
            {'name': 'report.update', 'resource': 'report', 'action': 'update', 'description': 'Update reports'},
            {'name': 'report.delete', 'resource': 'report', 'action': 'delete', 'description': 'Delete reports'},
            {'name': 'report.diagnose', 'resource': 'report', 'action': 'diagnose', 'description': 'Add diagnosis to reports'},
            
            # Image management permissions
            {'name': 'image.upload', 'resource': 'image', 'action': 'upload', 'description': 'Upload images'},
            {'name': 'image.view', 'resource': 'image', 'action': 'view', 'description': 'View images'},
            {'name': 'image.delete', 'resource': 'image', 'action': 'delete', 'description': 'Delete images'},
            
            # System administration permissions
            {'name': 'admin.users', 'resource': 'admin', 'action': 'users', 'description': 'Manage all users'},
            {'name': 'admin.roles', 'resource': 'admin', 'action': 'roles', 'description': 'Manage roles and permissions'},
            {'name': 'admin.audit', 'resource': 'admin', 'action': 'audit', 'description': 'View audit logs'},
        ]
        
        created_permissions = []
        for perm_data in default_permissions:
            # Check if permission already exists
            existing = session.query(Permission).filter_by(name=perm_data['name']).first()
            if not existing:
                permission = Permission(**perm_data)
                session.add(permission)
                created_permissions.append(perm_data['name'])
        
        session.commit()
        print(f"[SUCCESS] Created {len(created_permissions)} permissions: {created_permissions}")
        return True
        
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Error creating permissions: {e}")
        return False
    finally:
        session.close()

def create_default_roles():
    """Create default roles for the system"""
    session = Session()
    
    try:
        # Define default roles
        default_roles = [
            {'name': 'admin', 'description': 'System administrator with full access'},
            {'name': 'doctor', 'description': 'Medical doctor with diagnostic capabilities'},
            {'name': 'patient', 'description': 'Patient with limited access to own data'},
        ]
        
        created_roles = []
        for role_data in default_roles:
            # Check if role already exists
            existing = session.query(Role).filter_by(name=role_data['name']).first()
            if not existing:
                role = Role(**role_data)
                session.add(role)
                created_roles.append(role_data['name'])
        
        session.commit()
        print(f"[SUCCESS] Created {len(created_roles)} roles: {created_roles}")
        return True
        
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Error creating roles: {e}")
        return False
    finally:
        session.close()

def assign_role_permissions():
    """Assign permissions to roles"""
    session = Session()
    
    try:
        # Get roles
        admin_role = session.query(Role).filter_by(name='admin').first()
        doctor_role = session.query(Role).filter_by(name='doctor').first()
        patient_role = session.query(Role).filter_by(name='patient').first()
        
        if not all([admin_role, doctor_role, patient_role]):
            print("[ERROR] Required roles not found")
            return False
        
        # Admin gets all permissions
        admin_permissions = session.query(Permission).all()
        for perm in admin_permissions:
            existing = session.query(RolePermission).filter_by(
                role_id=admin_role.id, 
                permission_id=perm.id
            ).first()
            if not existing:
                role_perm = RolePermission(role_id=admin_role.id, permission_id=perm.id)
                session.add(role_perm)
        
        # Doctor permissions
        doctor_permission_names = [
            'user.read', 'user.update',  # Can view and update own profile
            'report.read', 'report.update', 'report.diagnose',  # Can manage reports and diagnose
            'image.view', 'image.upload'  # Can view and upload images
        ]
        
        for perm_name in doctor_permission_names:
            perm = session.query(Permission).filter_by(name=perm_name).first()
            if perm:
                existing = session.query(RolePermission).filter_by(
                    role_id=doctor_role.id, 
                    permission_id=perm.id
                ).first()
                if not existing:
                    role_perm = RolePermission(role_id=doctor_role.id, permission_id=perm.id)
                    session.add(role_perm)
        
        # Patient permissions
        patient_permission_names = [
            'user.read', 'user.update',  # Can view and update own profile
            'report.read', 'report.create',  # Can view own reports and create new ones
            'image.view', 'image.upload'  # Can view and upload own images
        ]
        
        for perm_name in patient_permission_names:
            perm = session.query(Permission).filter_by(name=perm_name).first()
            if perm:
                existing = session.query(RolePermission).filter_by(
                    role_id=patient_role.id, 
                    permission_id=perm.id
                ).first()
                if not existing:
                    role_perm = RolePermission(role_id=patient_role.id, permission_id=perm.id)
                    session.add(role_perm)
        
        session.commit()
        print("[SUCCESS] Role permissions assigned successfully")
        return True
        
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Error assigning role permissions: {e}")
        return False
    finally:
        session.close()

def create_admin_user():
    """Create default admin user"""
    session = Session()
    
    try:
        # Check if admin user already exists
        existing_admin = session.query(User).filter_by(id='admin').first()
        if existing_admin:
            print("[INFO] Admin user already exists")
            return True
        
        # Create admin user
        admin_password = hashlib.sha256('admin123'.encode()).hexdigest()
        admin_user = User(
            id='admin',
            password=admin_password,
            type=UserType.Doctor,
            is_active=True
        )
        
        session.add(admin_user)
        session.commit()
        
        # Assign admin role to admin user
        admin_role = session.query(Role).filter_by(name='admin').first()
        if admin_role:
            from database.table import UserRole
            user_role = UserRole(user_id='admin', role_id=admin_role.id)
            session.add(user_role)
            session.commit()
        
        print("[SUCCESS] Admin user created successfully (username: admin, password: admin123)")
        return True
        
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Error creating admin user: {e}")
        return False
    finally:
        session.close()

def initialize_database():
    """Initialize database with default data"""
    print("=== Database Initialization ===")
    
    success = True
    success &= create_default_permissions()
    success &= create_default_roles()
    success &= assign_role_permissions()
    success &= create_admin_user()
    
    if success:
        print("\n[SUCCESS] Database initialization completed successfully!")
    else:
        print("\n[ERROR] Database initialization failed!")
    
    return success

if __name__ == "__main__":
    initialize_database()