"""
Role-Based Access Control (RBAC) Service

This module provides comprehensive RBAC functionality including role management,
permission checking, and user authorization services.
"""

from typing import List, Optional, Dict, Any, Set
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime
import json

from dense_platform_backend_main.database.table import (
    User, Role, Permission, UserRole, RolePermission, AuditLog, UserType
)


class RBACService:
    """Service class for Role-Based Access Control operations"""
    
    @staticmethod
    def check_permission(
        db: Session, 
        user_id: str, 
        resource: str, 
        action: str
    ) -> bool:
        """
        Check if a user has permission to perform an action on a resource
        
        Args:
            db: Database session
            user_id: User ID to check permissions for
            resource: Resource name (e.g., 'user', 'report', 'admin')
            action: Action name (e.g., 'read', 'write', 'delete', 'manage')
            
        Returns:
            True if user has permission, False otherwise
        """
        # Get user's permissions through roles
        user_permissions = db.query(Permission).join(
            RolePermission, Permission.id == RolePermission.permission_id
        ).join(
            Role, RolePermission.role_id == Role.id
        ).join(
            UserRole, Role.id == UserRole.role_id
        ).filter(
            and_(
                UserRole.user_id == user_id,
                Permission.resource == resource,
                Permission.action == action,
                Permission.is_active == True,
                Role.is_active == True
            )
        ).first()
        
        return user_permissions is not None
    
    @staticmethod
    def get_user_permissions(db: Session, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all permissions for a user
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            List of permission dictionaries
        """
        permissions = db.query(Permission).join(
            RolePermission, Permission.id == RolePermission.permission_id
        ).join(
            Role, RolePermission.role_id == Role.id
        ).join(
            UserRole, Role.id == UserRole.role_id
        ).filter(
            and_(
                UserRole.user_id == user_id,
                Permission.is_active == True,
                Role.is_active == True
            )
        ).distinct().all()
        
        return [
            {
                "id": perm.id,
                "name": perm.name,
                "resource": perm.resource,
                "action": perm.action,
                "description": perm.description
            }
            for perm in permissions
        ]
    
    @staticmethod
    def get_user_roles(db: Session, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all roles for a user
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            List of role dictionaries
        """
        roles = db.query(Role).join(
            UserRole, Role.id == UserRole.role_id
        ).filter(
            and_(
                UserRole.user_id == user_id,
                Role.is_active == True
            )
        ).all()
        
        return [
            {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "created_at": role.created_at.isoformat() if role.created_at else None
            }
            for role in roles
        ]
    
    @staticmethod
    def assign_role(
        db: Session, 
        user_id: str, 
        role_name: str,
        assigned_by: Optional[str] = None
    ) -> bool:
        """
        Assign a role to a user
        
        Args:
            db: Database session
            user_id: User ID to assign role to
            role_name: Name of the role to assign
            assigned_by: User ID of who is assigning the role (for audit)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if user exists
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            
            # Check if role exists
            role = db.query(Role).filter(
                and_(Role.name == role_name, Role.is_active == True)
            ).first()
            if not role:
                return False
            
            # Check if user already has this role
            existing_assignment = db.query(UserRole).filter(
                and_(
                    UserRole.user_id == user_id,
                    UserRole.role_id == role.id
                )
            ).first()
            
            if existing_assignment:
                return True  # Already assigned
            
            # Create role assignment
            user_role = UserRole(user_id=user_id, role_id=role.id)
            db.add(user_role)
            
            # Create audit log
            if assigned_by:
                audit_log = AuditLog(
                    user_id=assigned_by,
                    action="assign_role",
                    resource_type="user_role",
                    resource_id=f"{user_id}:{role.id}",
                    new_values=json.dumps({
                        "user_id": user_id,
                        "role_name": role_name,
                        "role_id": role.id
                    }),
                    success=True
                )
                db.add(audit_log)
            
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            # Log error in audit log if assigned_by is provided
            if assigned_by:
                error_log = AuditLog(
                    user_id=assigned_by,
                    action="assign_role",
                    resource_type="user_role",
                    resource_id=f"{user_id}:{role_name}",
                    success=False,
                    error_message=str(e)
                )
                db.add(error_log)
                db.commit()
            return False
    
    @staticmethod
    def remove_role(
        db: Session, 
        user_id: str, 
        role_name: str,
        removed_by: Optional[str] = None
    ) -> bool:
        """
        Remove a role from a user
        
        Args:
            db: Database session
            user_id: User ID to remove role from
            role_name: Name of the role to remove
            removed_by: User ID of who is removing the role (for audit)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get role
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                return False
            
            # Find and remove user role assignment
            user_role = db.query(UserRole).filter(
                and_(
                    UserRole.user_id == user_id,
                    UserRole.role_id == role.id
                )
            ).first()
            
            if not user_role:
                return True  # Already removed
            
            db.delete(user_role)
            
            # Create audit log
            if removed_by:
                audit_log = AuditLog(
                    user_id=removed_by,
                    action="remove_role",
                    resource_type="user_role",
                    resource_id=f"{user_id}:{role.id}",
                    old_values=json.dumps({
                        "user_id": user_id,
                        "role_name": role_name,
                        "role_id": role.id
                    }),
                    success=True
                )
                db.add(audit_log)
            
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            # Log error in audit log if removed_by is provided
            if removed_by:
                error_log = AuditLog(
                    user_id=removed_by,
                    action="remove_role",
                    resource_type="user_role",
                    resource_id=f"{user_id}:{role_name}",
                    success=False,
                    error_message=str(e)
                )
                db.add(error_log)
                db.commit()
            return False
    
    @staticmethod
    def create_role(
        db: Session,
        name: str,
        description: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        created_by: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new role
        
        Args:
            db: Database session
            name: Role name
            description: Role description
            permissions: List of permission names to assign to role
            created_by: User ID of who is creating the role (for audit)
            
        Returns:
            Role dictionary if successful, None otherwise
        """
        try:
            # Check if role already exists
            existing_role = db.query(Role).filter(Role.name == name).first()
            if existing_role:
                return None
            
            # Create role
            role = Role(
                name=name,
                description=description,
                is_active=True
            )
            db.add(role)
            db.flush()  # Get the ID
            
            # Assign permissions if provided
            if permissions:
                for perm_name in permissions:
                    permission = db.query(Permission).filter(
                        Permission.name == perm_name
                    ).first()
                    if permission:
                        role_perm = RolePermission(
                            role_id=role.id,
                            permission_id=permission.id,
                            granted_by=created_by
                        )
                        db.add(role_perm)
            
            # Create audit log
            if created_by:
                audit_log = AuditLog(
                    user_id=created_by,
                    action="create_role",
                    resource_type="role",
                    resource_id=str(role.id),
                    new_values=json.dumps({
                        "name": name,
                        "description": description,
                        "permissions": permissions or []
                    }),
                    success=True
                )
                db.add(audit_log)
            
            db.commit()
            
            return {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "is_active": role.is_active,
                "created_at": role.created_at.isoformat() if role.created_at else None
            }
            
        except Exception as e:
            db.rollback()
            # Log error in audit log if created_by is provided
            if created_by:
                error_log = AuditLog(
                    user_id=created_by,
                    action="create_role",
                    resource_type="role",
                    resource_id=name,
                    success=False,
                    error_message=str(e)
                )
                db.add(error_log)
                db.commit()
            return None
    
    @staticmethod
    def create_permission(
        db: Session,
        name: str,
        resource: str,
        action: str,
        description: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new permission
        
        Args:
            db: Database session
            name: Permission name
            resource: Resource name
            action: Action name
            description: Permission description
            created_by: User ID of who is creating the permission (for audit)
            
        Returns:
            Permission dictionary if successful, None otherwise
        """
        try:
            # Check if permission already exists
            existing_perm = db.query(Permission).filter(
                and_(
                    Permission.resource == resource,
                    Permission.action == action
                )
            ).first()
            if existing_perm:
                return None
            
            # Create permission
            permission = Permission(
                name=name,
                resource=resource,
                action=action,
                description=description,
                is_active=True
            )
            db.add(permission)
            db.flush()  # Get the ID
            
            # Create audit log
            if created_by:
                audit_log = AuditLog(
                    user_id=created_by,
                    action="create_permission",
                    resource_type="permission",
                    resource_id=str(permission.id),
                    new_values=json.dumps({
                        "name": name,
                        "resource": resource,
                        "action": action,
                        "description": description
                    }),
                    success=True
                )
                db.add(audit_log)
            
            db.commit()
            
            return {
                "id": permission.id,
                "name": permission.name,
                "resource": permission.resource,
                "action": permission.action,
                "description": permission.description,
                "is_active": permission.is_active,
                "created_at": permission.created_at.isoformat() if permission.created_at else None
            }
            
        except Exception as e:
            db.rollback()
            # Log error in audit log if created_by is provided
            if created_by:
                error_log = AuditLog(
                    user_id=created_by,
                    action="create_permission",
                    resource_type="permission",
                    resource_id=f"{resource}:{action}",
                    success=False,
                    error_message=str(e)
                )
                db.add(error_log)
                db.commit()
            return None
    
    @staticmethod
    def get_all_roles(db: Session, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """
        Get all roles in the system
        
        Args:
            db: Database session
            include_inactive: Whether to include inactive roles
            
        Returns:
            List of role dictionaries
        """
        query = db.query(Role)
        if not include_inactive:
            query = query.filter(Role.is_active == True)
        
        roles = query.all()
        
        return [
            {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "is_active": role.is_active,
                "created_at": role.created_at.isoformat() if role.created_at else None,
                "updated_at": role.updated_at.isoformat() if role.updated_at else None
            }
            for role in roles
        ]
    
    @staticmethod
    def get_all_permissions(db: Session, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """
        Get all permissions in the system
        
        Args:
            db: Database session
            include_inactive: Whether to include inactive permissions
            
        Returns:
            List of permission dictionaries
        """
        query = db.query(Permission)
        if not include_inactive:
            query = query.filter(Permission.is_active == True)
        
        permissions = query.all()
        
        return [
            {
                "id": perm.id,
                "name": perm.name,
                "resource": perm.resource,
                "action": perm.action,
                "description": perm.description,
                "is_active": perm.is_active,
                "created_at": perm.created_at.isoformat() if perm.created_at else None,
                "updated_at": perm.updated_at.isoformat() if perm.updated_at else None
            }
            for perm in permissions
        ]
    
    @staticmethod
    def get_role_permissions(db: Session, role_id: int) -> List[Dict[str, Any]]:
        """
        Get all permissions for a specific role
        
        Args:
            db: Database session
            role_id: Role ID
            
        Returns:
            List of permission dictionaries
        """
        permissions = db.query(Permission).join(
            RolePermission, Permission.id == RolePermission.permission_id
        ).filter(
            and_(
                RolePermission.role_id == role_id,
                Permission.is_active == True
            )
        ).all()
        
        return [
            {
                "id": perm.id,
                "name": perm.name,
                "resource": perm.resource,
                "action": perm.action,
                "description": perm.description
            }
            for perm in permissions
        ]
    
    @staticmethod
    def assign_permission_to_role(
        db: Session,
        role_id: int,
        permission_id: int,
        granted_by: Optional[str] = None
    ) -> bool:
        """
        Assign a permission to a role
        
        Args:
            db: Database session
            role_id: Role ID
            permission_id: Permission ID
            granted_by: User ID of who is granting the permission (for audit)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if assignment already exists
            existing = db.query(RolePermission).filter(
                and_(
                    RolePermission.role_id == role_id,
                    RolePermission.permission_id == permission_id
                )
            ).first()
            
            if existing:
                return True  # Already assigned
            
            # Create assignment
            role_perm = RolePermission(
                role_id=role_id,
                permission_id=permission_id,
                granted_by=granted_by
            )
            db.add(role_perm)
            
            # Create audit log
            if granted_by:
                audit_log = AuditLog(
                    user_id=granted_by,
                    action="assign_permission_to_role",
                    resource_type="role_permission",
                    resource_id=f"{role_id}:{permission_id}",
                    new_values=json.dumps({
                        "role_id": role_id,
                        "permission_id": permission_id
                    }),
                    success=True
                )
                db.add(audit_log)
            
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            # Log error in audit log if granted_by is provided
            if granted_by:
                error_log = AuditLog(
                    user_id=granted_by,
                    action="assign_permission_to_role",
                    resource_type="role_permission",
                    resource_id=f"{role_id}:{permission_id}",
                    success=False,
                    error_message=str(e)
                )
                db.add(error_log)
                db.commit()
            return False
    
    @staticmethod
    def has_admin_role(db: Session, user_id: str) -> bool:
        """
        Check if user has admin role
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            True if user has admin role, False otherwise
        """
        admin_role = db.query(Role).join(
            UserRole, Role.id == UserRole.role_id
        ).filter(
            and_(
                UserRole.user_id == user_id,
                Role.name == "admin",
                Role.is_active == True
            )
        ).first()
        
        return admin_role is not None
    
    @staticmethod
    def initialize_default_permissions(db: Session) -> None:
        """
        Initialize default permissions in the system
        
        Args:
            db: Database session
        """
        default_permissions = [
            # User management permissions
            ("user.read", "user", "read", "Read user information"),
            ("user.write", "user", "write", "Create and update user information"),
            ("user.delete", "user", "delete", "Delete user accounts"),
            ("user.manage", "user", "manage", "Full user management access"),
            
            # Report permissions
            ("report.read", "report", "read", "Read medical reports"),
            ("report.write", "report", "write", "Create and update medical reports"),
            ("report.delete", "report", "delete", "Delete medical reports"),
            ("report.manage", "report", "manage", "Full report management access"),
            
            # Admin permissions
            ("admin.system", "admin", "system", "System administration access"),
            ("admin.users", "admin", "users", "User administration access"),
            ("admin.roles", "admin", "roles", "Role and permission management"),
            ("admin.audit", "admin", "audit", "Access to audit logs"),
            
            # Doctor specific permissions
            ("doctor.diagnose", "doctor", "diagnose", "Create medical diagnoses"),
            ("doctor.review", "doctor", "review", "Review patient reports"),
            ("doctor.comment", "doctor", "comment", "Add comments to reports"),
            
            # Patient specific permissions
            ("patient.profile", "patient", "profile", "Manage own profile"),
            ("patient.reports", "patient", "reports", "View own reports"),
        ]
        
        for name, resource, action, description in default_permissions:
            existing = db.query(Permission).filter(
                and_(
                    Permission.resource == resource,
                    Permission.action == action
                )
            ).first()
            
            if not existing:
                permission = Permission(
                    name=name,
                    resource=resource,
                    action=action,
                    description=description,
                    is_active=True
                )
                db.add(permission)
        
        db.commit()
    
    @staticmethod
    def initialize_default_roles(db: Session) -> None:
        """
        Initialize default roles in the system
        
        Args:
            db: Database session
        """
        # Ensure permissions exist first
        RBACService.initialize_default_permissions(db)
        
        default_roles = [
            ("admin", "System Administrator", [
                "user.read", "user.write", "user.delete", "user.manage",
                "report.read", "report.write", "report.delete", "report.manage",
                "admin.system", "admin.users", "admin.roles", "admin.audit",
                "doctor.diagnose", "doctor.review", "doctor.comment"
            ]),
            ("doctor", "Medical Doctor", [
                "user.read", "report.read", "report.write", "report.manage",
                "doctor.diagnose", "doctor.review", "doctor.comment"
            ]),
            ("patient", "Patient", [
                "patient.profile", "patient.reports"
            ])
        ]
        
        for role_name, description, permission_names in default_roles:
            existing_role = db.query(Role).filter(Role.name == role_name).first()
            
            if not existing_role:
                role = Role(
                    name=role_name,
                    description=description,
                    is_active=True
                )
                db.add(role)
                db.flush()  # Get the ID
                
                # Assign permissions to role
                for perm_name in permission_names:
                    permission = db.query(Permission).filter(
                        Permission.name == perm_name
                    ).first()
                    if permission:
                        role_perm = RolePermission(
                            role_id=role.id,
                            permission_id=permission.id
                        )
                        db.add(role_perm)
        
        db.commit()