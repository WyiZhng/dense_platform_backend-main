"""
Admin User Management API

This module provides API endpoints for administrators to manage users,
including user creation, updates, deactivation, and user information retrieval.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime, date

from dense_platform_backend_main.api.auth.session import get_db
from dense_platform_backend_main.services.rbac_middleware import RequirePermission
from dense_platform_backend_main.utils.response import success_response, error_response
from dense_platform_backend_main.database.table import (
    User, UserDetail, Doctor, UserType, UserSex, AuditLog
)
import hashlib
import json

router = APIRouter(prefix="/api/admin/users", tags=["Admin User Management"])


# Pydantic models for request/response
class CreateUserRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=20, description="User ID")
    password: str = Field(..., min_length=6, max_length=50, description="User password")
    user_type: UserType = Field(..., description="User type (Patient=0, Doctor=1)")
    name: Optional[str] = Field(None, max_length=20, description="User name")
    sex: Optional[UserSex] = Field(None, description="User sex (Female=0, Male=1)")
    birth: Optional[date] = Field(None, description="Birth date")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    email: Optional[str] = Field(None, max_length=100, description="Email address")
    address: Optional[str] = Field(None, max_length=100, description="Address")
    # Doctor specific fields
    position: Optional[str] = Field(None, max_length=20, description="Doctor position")
    workplace: Optional[str] = Field(None, max_length=20, description="Doctor workplace")


class UpdateUserRequest(BaseModel):
    password: Optional[str] = Field(None, min_length=6, max_length=50, description="New password")
    is_active: Optional[bool] = Field(None, description="User active status")
    name: Optional[str] = Field(None, max_length=20, description="User name")
    sex: Optional[UserSex] = Field(None, description="User sex")
    birth: Optional[date] = Field(None, description="Birth date")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    email: Optional[str] = Field(None, max_length=100, description="Email address")
    address: Optional[str] = Field(None, max_length=100, description="Address")
    # Doctor specific fields
    position: Optional[str] = Field(None, max_length=20, description="Doctor position")
    workplace: Optional[str] = Field(None, max_length=20, description="Doctor workplace")


class UserListResponse(BaseModel):
    id: str
    type: UserType
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


@router.get("/")
async def get_all_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    user_type: Optional[UserType] = Query(None, description="Filter by user type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by user ID, name, email, or phone"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "users")
):
    """
    Get all users with pagination and filtering
    
    Requires: admin:users permission
    """
    try:
        # Build query
        query = db.query(User).join(UserDetail, User.id == UserDetail.id, isouter=True)
        
        # Apply filters
        if user_type is not None:
            query = query.filter(User.type == user_type)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (User.id.like(search_term)) |
                (UserDetail.name.like(search_term)) |
                (UserDetail.email.like(search_term)) |
                (UserDetail.phone.like(search_term))
            )
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        users = query.offset(offset).limit(page_size).all()
        
        # Format response
        user_list = []
        for user in users:
            user_data = {
                "id": user.id,
                "type": user.type,
                "is_active": user.is_active,
                "last_login": user.last_login,
                "created_at": user.created_at,
                "name": user.user_detail.name if user.user_detail else None,
                "email": user.user_detail.email if user.user_detail else None,
                "phone": user.user_detail.phone if user.user_detail else None
            }
            user_list.append(user_data)
        
        return success_response(
            data={
                "users": user_list,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": (total_count + page_size - 1) // page_size
                }
            },
            message="Users retrieved successfully"
        )
        
    except Exception as e:
        return error_response(message=f"Failed to retrieve users: {str(e)}")


@router.get("/{user_id}")
async def get_user_details(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "users")
):
    """
    Get detailed information for a specific user
    
    Requires: admin:users permission
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return error_response(message="User not found")
        
        user_detail = db.query(UserDetail).filter(UserDetail.id == user_id).first()
        doctor_info = None
        
        if user.type == UserType.Doctor:
            doctor_info = db.query(Doctor).filter(Doctor.id == user_id).first()
        
        # Build response
        response_data = {
            "id": user.id,
            "type": user.type,
            "is_active": user.is_active,
            "last_login": user.last_login,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        }
        
        if user_detail:
            response_data.update({
                "name": user_detail.name,
                "sex": user_detail.sex,
                "birth": user_detail.birth,
                "phone": user_detail.phone,
                "email": user_detail.email,
                "address": user_detail.address
            })
        
        if doctor_info:
            response_data.update({
                "position": doctor_info.position,
                "workplace": doctor_info.workplace
            })
        
        return success_response(data=response_data, message="User details retrieved successfully")
        
    except Exception as e:
        return error_response(message=f"Failed to retrieve user details: {str(e)}")


@router.post("/")
async def create_user(
    request: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "users")
):
    """
    Create a new user
    
    Requires: admin:users permission
    """
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.id == request.user_id).first()
        if existing_user:
            return error_response(message="User ID already exists")
        
        # Hash password
        password_hash = hashlib.sha256(request.password.encode()).hexdigest()
        
        # Create user
        user = User(
            id=request.user_id,
            password=password_hash,
            type=request.user_type,
            is_active=True
        )
        db.add(user)
        db.flush()  # Get the user created
        
        # Create user detail if provided
        if any([request.name, request.sex, request.birth, request.phone, request.email, request.address]):
            user_detail = UserDetail(
                id=request.user_id,
                name=request.name,
                sex=request.sex,
                birth=request.birth,
                phone=request.phone,
                email=request.email,
                address=request.address
            )
            db.add(user_detail)
        
        # Create doctor info if user is a doctor
        if request.user_type == UserType.Doctor and (request.position or request.workplace):
            doctor = Doctor(
                id=request.user_id,
                position=request.position,
                workplace=request.workplace
            )
            db.add(doctor)
        
        # Create audit log
        audit_log = AuditLog(
            user_id=current_user["user_id"],
            action="create_user",
            resource_type="user",
            resource_id=request.user_id,
            new_values=json.dumps({
                "user_id": request.user_id,
                "user_type": request.user_type.value,
                "name": request.name,
                "email": request.email
            }),
            success=True
        )
        db.add(audit_log)
        
        db.commit()
        
        return success_response(
            data={"user_id": request.user_id},
            message="User created successfully"
        )
        
    except Exception as e:
        db.rollback()
        # Log error in audit log
        error_log = AuditLog(
            user_id=current_user["user_id"],
            action="create_user",
            resource_type="user",
            resource_id=request.user_id,
            success=False,
            error_message=str(e)
        )
        db.add(error_log)
        db.commit()
        return error_response(message=f"Failed to create user: {str(e)}")


@router.put("/{user_id}")
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "users")
):
    """
    Update user information
    
    Requires: admin:users permission
    """
    try:
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return error_response(message="User not found")
        
        # Store old values for audit
        old_values = {
            "is_active": user.is_active
        }
        
        # Update user fields
        if request.password is not None:
            user.password = hashlib.sha256(request.password.encode()).hexdigest()
            old_values["password_changed"] = True
        
        if request.is_active is not None:
            user.is_active = request.is_active
        
        # Update user detail
        user_detail = db.query(UserDetail).filter(UserDetail.id == user_id).first()
        if not user_detail and any([request.name, request.sex, request.birth, request.phone, request.email, request.address]):
            user_detail = UserDetail(id=user_id)
            db.add(user_detail)
        
        if user_detail:
            if request.name is not None:
                old_values["name"] = user_detail.name
                user_detail.name = request.name
            if request.sex is not None:
                old_values["sex"] = user_detail.sex
                user_detail.sex = request.sex
            if request.birth is not None:
                old_values["birth"] = user_detail.birth.isoformat() if user_detail.birth else None
                user_detail.birth = request.birth
            if request.phone is not None:
                old_values["phone"] = user_detail.phone
                user_detail.phone = request.phone
            if request.email is not None:
                old_values["email"] = user_detail.email
                user_detail.email = request.email
            if request.address is not None:
                old_values["address"] = user_detail.address
                user_detail.address = request.address
        
        # Update doctor info if applicable
        if user.type == UserType.Doctor and (request.position is not None or request.workplace is not None):
            doctor = db.query(Doctor).filter(Doctor.id == user_id).first()
            if not doctor:
                doctor = Doctor(id=user_id)
                db.add(doctor)
            
            if request.position is not None:
                old_values["position"] = doctor.position
                doctor.position = request.position
            if request.workplace is not None:
                old_values["workplace"] = doctor.workplace
                doctor.workplace = request.workplace
        
        # Create audit log
        new_values = {}
        if request.is_active is not None:
            new_values["is_active"] = request.is_active
        if request.name is not None:
            new_values["name"] = request.name
        if request.email is not None:
            new_values["email"] = request.email
        if request.password is not None:
            new_values["password_changed"] = True
        
        audit_log = AuditLog(
            user_id=current_user["user_id"],
            action="update_user",
            resource_type="user",
            resource_id=user_id,
            old_values=json.dumps(old_values),
            new_values=json.dumps(new_values),
            success=True
        )
        db.add(audit_log)
        
        db.commit()
        
        return success_response(message="User updated successfully")
        
    except Exception as e:
        db.rollback()
        # Log error in audit log
        error_log = AuditLog(
            user_id=current_user["user_id"],
            action="update_user",
            resource_type="user",
            resource_id=user_id,
            success=False,
            error_message=str(e)
        )
        db.add(error_log)
        db.commit()
        return error_response(message=f"Failed to update user: {str(e)}")


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "users")
):
    """
    Deactivate a user (soft delete)
    
    Requires: admin:users permission
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return error_response(message="User not found")
        
        if not user.is_active:
            return error_response(message="User is already deactivated")
        
        # Deactivate user
        user.is_active = False
        
        # Create audit log
        audit_log = AuditLog(
            user_id=current_user["user_id"],
            action="deactivate_user",
            resource_type="user",
            resource_id=user_id,
            old_values=json.dumps({"is_active": True}),
            new_values=json.dumps({"is_active": False}),
            success=True
        )
        db.add(audit_log)
        
        db.commit()
        
        return success_response(message="User deactivated successfully")
        
    except Exception as e:
        db.rollback()
        # Log error in audit log
        error_log = AuditLog(
            user_id=current_user["user_id"],
            action="deactivate_user",
            resource_type="user",
            resource_id=user_id,
            success=False,
            error_message=str(e)
        )
        db.add(error_log)
        db.commit()
        return error_response(message=f"Failed to deactivate user: {str(e)}")


@router.post("/{user_id}/activate")
async def activate_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "users")
):
    """
    Activate a deactivated user
    
    Requires: admin:users permission
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return error_response(message="User not found")
        
        if user.is_active:
            return error_response(message="User is already active")
        
        # Activate user
        user.is_active = True
        
        # Create audit log
        audit_log = AuditLog(
            user_id=current_user["user_id"],
            action="activate_user",
            resource_type="user",
            resource_id=user_id,
            old_values=json.dumps({"is_active": False}),
            new_values=json.dumps({"is_active": True}),
            success=True
        )
        db.add(audit_log)
        
        db.commit()
        
        return success_response(message="User activated successfully")
        
    except Exception as e:
        db.rollback()
        # Log error in audit log
        error_log = AuditLog(
            user_id=current_user["user_id"],
            action="activate_user",
            resource_type="user",
            resource_id=user_id,
            success=False,
            error_message=str(e)
        )
        db.add(error_log)
        db.commit()
        return error_response(message=f"Failed to activate user: {str(e)}")


@router.get("/{user_id}/audit-logs")
async def get_user_audit_logs(
    user_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = RequirePermission("admin", "audit")
):
    """
    Get audit logs for a specific user
    
    Requires: admin:audit permission
    """
    try:
        # Get total count
        total_count = db.query(AuditLog).filter(
            (AuditLog.user_id == user_id) | (AuditLog.resource_id == user_id)
        ).count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        audit_logs = db.query(AuditLog).filter(
            (AuditLog.user_id == user_id) | (AuditLog.resource_id == user_id)
        ).order_by(AuditLog.timestamp.desc()).offset(offset).limit(page_size).all()
        
        # Format response
        logs = []
        for log in audit_logs:
            log_data = {
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "timestamp": log.timestamp,
                "success": log.success,
                "error_message": log.error_message
            }
            logs.append(log_data)
        
        return success_response(
            data={
                "audit_logs": logs,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": (total_count + page_size - 1) // page_size
                }
            },
            message="Audit logs retrieved successfully"
        )
        
    except Exception as e:
        return error_response(message=f"Failed to retrieve audit logs: {str(e)}")