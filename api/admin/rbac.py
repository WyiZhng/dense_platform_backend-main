"""
RBAC Management API

This module provides API endpoints for managing roles, permissions, and user assignments.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from dense_platform_backend_main.api.auth.session import get_db
from dense_platform_backend_main.services.rbac_service import RBACService
from dense_platform_backend_main.services.rbac_middleware import RequireAdmin, RequirePermission
from dense_platform_backend_main.utils.response import success_response, error_response

router = APIRouter(prefix="/api/admin/rbac", tags=["Admin RBAC"])


# Pydantic models for request/response
class CreateRoleRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Role name")
    description: Optional[str] = Field(None, max_length=255, description="Role description")
    permissions: Optional[List[str]] = Field(default=[], description="List of permission names to assign")


class CreatePermissionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Permission name")
    resource: str = Field(..., min_length=1, max_length=100, description="Resource name")
    action: str = Field(..., min_length=1, max_length=50, description="Action name")
    description: Optional[str] = Field(None, max_length=255, description="Permission description")


class AssignRoleRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=20, description="User ID")
    role_name: str = Field(..., min_length=1, max_length=50, description="Role name")


class AssignPermissionToRoleRequest(BaseModel):
    role_id: int = Field(..., gt=0, description="Role ID")
    permission_id: int = Field(..., gt=0, description="Permission ID")


@router.get("/roles")
async def get_all_roles(
    include_inactive: bool = Query(False, description="Include inactive roles"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "roles")
):
    """
    Get all roles in the system
    
    Requires: admin:roles permission
    """
    try:
        roles = RBACService.get_all_roles(db, include_inactive)
        return success_response(data=roles, message="Roles retrieved successfully")
    except Exception as e:
        return error_response(message=f"Failed to retrieve roles: {str(e)}")


@router.get("/permissions")
async def get_all_permissions(
    include_inactive: bool = Query(False, description="Include inactive permissions"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "roles")
):
    """
    Get all permissions in the system
    
    Requires: admin:roles permission
    """
    try:
        permissions = RBACService.get_all_permissions(db, include_inactive)
        return success_response(data=permissions, message="Permissions retrieved successfully")
    except Exception as e:
        return error_response(message=f"Failed to retrieve permissions: {str(e)}")


@router.post("/roles")
async def create_role(
    request: CreateRoleRequest,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "roles")
):
    """
    Create a new role
    
    Requires: admin:roles permission
    """
    try:
        role = RBACService.create_role(
            db=db,
            name=request.name,
            description=request.description,
            permissions=request.permissions,
            created_by=current_user["user_id"]
        )
        
        if not role:
            return error_response(message="Failed to create role - role may already exist")
        
        return success_response(data=role, message="Role created successfully")
    except Exception as e:
        return error_response(message=f"Failed to create role: {str(e)}")


@router.post("/permissions")
async def create_permission(
    request: CreatePermissionRequest,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "roles")
):
    """
    Create a new permission
    
    Requires: admin:roles permission
    """
    try:
        permission = RBACService.create_permission(
            db=db,
            name=request.name,
            resource=request.resource,
            action=request.action,
            description=request.description,
            created_by=current_user["user_id"]
        )
        
        if not permission:
            return error_response(message="Failed to create permission - permission may already exist")
        
        return success_response(data=permission, message="Permission created successfully")
    except Exception as e:
        return error_response(message=f"Failed to create permission: {str(e)}")


@router.get("/roles/{role_id}/permissions")
async def get_role_permissions(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "roles")
):
    """
    Get all permissions for a specific role
    
    Requires: admin:roles permission
    """
    try:
        permissions = RBACService.get_role_permissions(db, role_id)
        return success_response(data=permissions, message="Role permissions retrieved successfully")
    except Exception as e:
        return error_response(message=f"Failed to retrieve role permissions: {str(e)}")


@router.post("/roles/assign-permission")
async def assign_permission_to_role(
    request: AssignPermissionToRoleRequest,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "roles")
):
    """
    Assign a permission to a role
    
    Requires: admin:roles permission
    """
    try:
        success = RBACService.assign_permission_to_role(
            db=db,
            role_id=request.role_id,
            permission_id=request.permission_id,
            granted_by=current_user["user_id"]
        )
        
        if not success:
            return error_response(message="Failed to assign permission to role")
        
        return success_response(message="Permission assigned to role successfully")
    except Exception as e:
        return error_response(message=f"Failed to assign permission to role: {str(e)}")


@router.post("/users/assign-role")
async def assign_role_to_user(
    request: AssignRoleRequest,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "users")
):
    """
    Assign a role to a user
    
    Requires: admin:users permission
    """
    try:
        success = RBACService.assign_role(
            db=db,
            user_id=request.user_id,
            role_name=request.role_name,
            assigned_by=current_user["user_id"]
        )
        
        if not success:
            return error_response(message="Failed to assign role to user - user or role may not exist")
        
        return success_response(message="Role assigned to user successfully")
    except Exception as e:
        return error_response(message=f"Failed to assign role to user: {str(e)}")


@router.delete("/users/{user_id}/roles/{role_name}")
async def remove_role_from_user(
    user_id: str,
    role_name: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "users")
):
    """
    Remove a role from a user
    
    Requires: admin:users permission
    """
    try:
        success = RBACService.remove_role(
            db=db,
            user_id=user_id,
            role_name=role_name,
            removed_by=current_user["user_id"]
        )
        
        if not success:
            return error_response(message="Failed to remove role from user")
        
        return success_response(message="Role removed from user successfully")
    except Exception as e:
        return error_response(message=f"Failed to remove role from user: {str(e)}")


@router.get("/users/{user_id}/roles")
async def get_user_roles(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "users")
):
    """
    Get all roles for a specific user
    
    Requires: admin:users permission
    """
    try:
        roles = RBACService.get_user_roles(db, user_id)
        return success_response(data=roles, message="User roles retrieved successfully")
    except Exception as e:
        return error_response(message=f"Failed to retrieve user roles: {str(e)}")


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "users")
):
    """
    Get all permissions for a specific user
    
    Requires: admin:users permission
    """
    try:
        permissions = RBACService.get_user_permissions(db, user_id)
        return success_response(data=permissions, message="User permissions retrieved successfully")
    except Exception as e:
        return error_response(message=f"Failed to retrieve user permissions: {str(e)}")


@router.post("/initialize")
async def initialize_rbac_system(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequireAdmin
):
    """
    Initialize the RBAC system with default roles and permissions
    
    Requires: admin role
    """
    try:
        RBACService.initialize_default_permissions(db)
        RBACService.initialize_default_roles(db)
        
        return success_response(message="RBAC system initialized successfully")
    except Exception as e:
        return error_response(message=f"Failed to initialize RBAC system: {str(e)}")


@router.get("/check-permission/{user_id}")
async def check_user_permission(
    user_id: str,
    resource: str = Query(..., description="Resource name"),
    action: str = Query(..., description="Action name"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "users")
):
    """
    Check if a user has a specific permission
    
    Requires: admin:users permission
    """
    try:
        has_permission = RBACService.check_permission(db, user_id, resource, action)
        
        return success_response(
            data={"has_permission": has_permission},
            message=f"Permission check completed for {resource}:{action}"
        )
    except Exception as e:
        return error_response(message=f"Failed to check permission: {str(e)}")