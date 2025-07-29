"""
Enhanced Authentication API

This module provides enhanced authentication functionality with secure session management.
"""

import hashlib
import secrets
from typing import Any, Optional, Tuple
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session, sessionmaker
from pydantic import BaseModel, EmailStr

from dense_platform_backend_main.database.db import engine
from dense_platform_backend_main.database.table import User, UserDetail, UserType, UserSex
from dense_platform_backend_main.utils.response import Response
from dense_platform_backend_main.services.security_service import security_service
from dense_platform_backend_main.services.audit_service import audit_service, AuditEventType, SeverityLevel
from .session import SessionService, get_db

router = APIRouter()


class AuthService:
    """Service for authentication operations"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt (new method)
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password string
        """
        return security_service.password_hasher.hash_password(password)
    
    @staticmethod
    def hash_password_legacy(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """
        Hash a password with salt (legacy method for backward compatibility)
        
        Args:
            password: Plain text password
            salt: Optional salt (will generate if not provided)
            
        Returns:
            Tuple of (hashed_password, salt)
        """
        if salt is None:
            salt = secrets.token_hex(16)
        
        # Combine password and salt
        password_salt = f"{password}{salt}"
        
        # Hash with SHA-256
        hashed = hashlib.sha256(password_salt.encode()).hexdigest()
        
        return hashed, salt
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash (supports both bcrypt and legacy formats)
        
        Args:
            password: Plain text password
            hashed_password: Stored hash
            
        Returns:
            True if password matches, False otherwise
        """
        # Check if it's a bcrypt hash
        if security_service.password_hasher.is_bcrypt_hash(hashed_password):
            return security_service.password_hasher.verify_password(password, hashed_password)
        
        # Legacy format handling
        if len(hashed_password) == 64:  # SHA-256 hash length (old format)
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            return password_hash == hashed_password
        else:
            # Legacy format with salt (format: hash:salt)
            try:
                stored_hash, salt = hashed_password.split(':')
                computed_hash, _ = AuthService.hash_password_legacy(password, salt)
                return computed_hash == stored_hash
            except ValueError:
                return False
    
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """
        Authenticate a user with username and password
        
        Args:
            db: Database session
            username: Username
            password: Plain text password
            
        Returns:
            User object if authentication successful, None otherwise
        """
        # Find user
        user = db.query(User).filter(User.id == username).first()
        if not user:
            return None
        
        # Verify password using enhanced method
        if AuthService.verify_password(password, user.password):
            # If user is using legacy password format, upgrade to bcrypt
            if not security_service.password_hasher.is_bcrypt_hash(user.password):
                # Upgrade password to bcrypt
                user.password = AuthService.hash_password(password)
                user.updated_at = datetime.utcnow()
                db.commit()
            
            return user
        
        return None
    
    @staticmethod
    def create_user(
        db: Session,
        username: str,
        password: str,
        user_type: UserType,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Optional[User]:
        """
        Create a new user account
        
        Args:
            db: Database session
            username: Username
            password: Plain text password
            user_type: User type
            name: Full name
            email: Email address
            phone: Phone number
            
        Returns:
            Created User object if successful, None otherwise
        """
        # Check if user already exists
        existing_user = db.query(User).filter(User.id == username).first()
        if existing_user:
            return None
        
        # Hash password using bcrypt
        hashed_password = AuthService.hash_password(password)
        
        # Create user
        user = User(
            id=username,
            password=hashed_password,
            type=user_type,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(user)
        db.flush()  # Get the user ID
        
        # Create user detail if additional info provided
        if name or email or phone:
            user_detail = UserDetail(
                id=username,
                name=name,
                email=email,
                phone=phone
            )
            db.add(user_detail)
        
        db.commit()
        db.refresh(user)
        
        return user
    
    @staticmethod
    def change_password(db: Session, username: str, old_password: str, new_password: str) -> bool:
        """
        Change user password
        
        Args:
            db: Database session
            username: Username
            old_password: Current password
            new_password: New password
            
        Returns:
            True if password changed successfully, False otherwise
        """
        # Authenticate with old password
        user = AuthService.authenticate_user(db, username, old_password)
        if not user:
            return False
        
        # Hash new password using bcrypt
        hashed_password = AuthService.hash_password(new_password)
        
        # Update password
        user.password = hashed_password
        user.updated_at = datetime.utcnow()
        
        db.commit()
        return True


# Request/Response models
class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: Optional[bool] = False


class LoginResponse(Response):
    token: Optional[str] = None
    session_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    user_id: Optional[str] = None
    user_type: Optional[UserType] = None


class RegisterRequest(BaseModel):
    username: str
    password: str
    user_type: UserType
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class RegisterResponse(Response):
    token: Optional[str] = None
    session_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    user_id: Optional[str] = None


class LogoutRequest(BaseModel):
    token: str
    logout_all: Optional[bool] = False


class ChangePasswordRequest(BaseModel):
    username: str
    old_password: str
    new_password: str


class ResetPasswordRequest(BaseModel):
    username: str
    new_password: str
    reset_token: str


# API endpoints
@router.post("/api/auth/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """Enhanced login with session management, rate limiting, and security logging"""
    try:
        # Check rate limiting
        if security_service.check_authentication_rate_limit(http_request):
            security_service.log_security_event(
                "rate_limit_exceeded",
                {"username": request.username, "action": "login"},
                http_request
            )
            return LoginResponse(code=429, message="登录尝试过于频繁，请稍后重试")
        
        # Record authentication attempt
        security_service.record_authentication_attempt(http_request, request.username)
        
        # Validate input
        username_validation = security_service.input_validator.validate_username(request.username)
        if not username_validation['is_valid']:
            security_service.log_security_event(
                "invalid_input",
                {"username": request.username, "errors": username_validation['errors']},
                http_request
            )
            return LoginResponse(code=400, message="用户名格式不正确")
        
        # Authenticate user
        user = AuthService.authenticate_user(db, request.username, request.password)
        if not user:
            # Log failed login attempt
            audit_service.log_audit_event(
                event_type=AuditEventType.LOGIN_FAILED,
                severity=SeverityLevel.MEDIUM,
                user_id=request.username,
                resource="authentication",
                action="login",
                details={"reason": "invalid_credentials"},
                request=http_request,
                success=False
            )
            security_service.log_security_event(
                "login_failed",
                {"username": request.username, "reason": "invalid_credentials"},
                http_request
            )
            return LoginResponse(code=31, message="错误的账号或者密码")
        
        # Check if user is active
        if not user.is_active:
            security_service.log_security_event(
                "login_failed",
                {"username": request.username, "reason": "account_disabled"},
                http_request
            )
            return LoginResponse(code=32, message="账号已被禁用")
        
        # Clear rate limiting on successful login
        security_service.clear_authentication_attempts(http_request, request.username)
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        # Create session
        expires_hours = 24 * 7 if request.remember_me else 24  # 7 days if remember me, 1 day otherwise
        
        # Get client info
        ip_address = http_request.client.host if http_request.client else None
        user_agent = http_request.headers.get("user-agent")
        
        session_info = SessionService.create_session(
            db=db,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_hours=expires_hours
        )
        
        # Log successful login
        audit_service.log_audit_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            severity=SeverityLevel.LOW,
            user_id=user.id,
            resource="authentication",
            action="login",
            details={
                "user_type": user.type.value,
                "remember_me": request.remember_me,
                "session_duration_hours": expires_hours
            },
            request=http_request,
            session_id=session_info["session_id"],
            success=True
        )
        security_service.log_security_event(
            "login_success",
            {"username": request.username, "user_type": user.type.value},
            http_request
        )
        
        return LoginResponse(
            code=0,
            message="登录成功",
            token=session_info["token"],
            session_id=session_info["session_id"],
            expires_at=session_info["expires_at"],
            user_id=user.id,
            user_type=user.type
        )
        
    except Exception as e:
        security_service.log_security_event(
            "login_error",
            {"username": request.username, "error": str(e)},
            http_request
        )
        return LoginResponse(code=500, message=f"登录失败: {str(e)}")


@router.post("/api/auth/register", response_model=RegisterResponse)
async def register(
    request: RegisterRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """Enhanced registration with input validation and security logging"""
    try:
        # Check rate limiting
        if security_service.check_authentication_rate_limit(http_request):
            security_service.log_security_event(
                "rate_limit_exceeded",
                {"username": request.username, "action": "register"},
                http_request
            )
            return RegisterResponse(code=429, message="注册尝试过于频繁，请稍后重试")
        
        # Record authentication attempt
        security_service.record_authentication_attempt(http_request, request.username)
        
        # Validate registration input
        validation_result = security_service.validate_registration_input(
            username=request.username,
            password=request.password,
            email=request.email,
            name=request.name
        )
        
        if not validation_result['is_valid']:
            security_service.log_security_event(
                "registration_validation_failed",
                {"username": request.username, "errors": validation_result['errors']},
                http_request
            )
            return RegisterResponse(code=400, message="; ".join(validation_result['errors']))
        
        # Create user
        user = AuthService.create_user(
            db=db,
            username=request.username,
            password=request.password,
            user_type=request.user_type,
            name=request.name,
            email=request.email,
            phone=request.phone
        )
        
        if not user:
            security_service.log_security_event(
                "registration_failed",
                {"username": request.username, "reason": "username_exists"},
                http_request
            )
            return RegisterResponse(code=32, message="用户名已存在")
        
        # Clear rate limiting on successful registration
        security_service.clear_authentication_attempts(http_request, request.username)
        
        # Create session for new user
        ip_address = http_request.client.host if http_request.client else None
        user_agent = http_request.headers.get("user-agent")
        
        session_info = SessionService.create_session(
            db=db,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_hours=24
        )
        
        # Log successful registration
        audit_service.log_audit_event(
            event_type=AuditEventType.USER_CREATE,
            severity=SeverityLevel.LOW,
            user_id=user.id,
            resource="user_account",
            action="create",
            details={
                "user_type": request.user_type.value,
                "password_strength": validation_result.get('password_strength', 0),
                "has_email": bool(request.email),
                "has_name": bool(request.name),
                "has_phone": bool(request.phone)
            },
            request=http_request,
            session_id=session_info["session_id"],
            success=True
        )
        security_service.log_security_event(
            "registration_success",
            {
                "username": request.username,
                "user_type": request.user_type.value,
                "password_strength": validation_result.get('password_strength', 0)
            },
            http_request
        )
        
        return RegisterResponse(
            code=0,
            message="注册成功",
            token=session_info["token"],
            session_id=session_info["session_id"],
            expires_at=session_info["expires_at"],
            user_id=user.id
        )
        
    except Exception as e:
        security_service.log_security_event(
            "registration_error",
            {"username": request.username, "error": str(e)},
            http_request
        )
        return RegisterResponse(code=500, message=f"注册失败: {str(e)}")


@router.post("/api/auth/logout")
async def logout(request: LogoutRequest, http_request: Request, db: Session = Depends(get_db)):
    """Enhanced logout with session management and audit logging"""
    try:
        if request.logout_all:
            # Get user from session first
            session_info = SessionService.validate_session(db, request.token)
            if session_info:
                # Invalidate all sessions for this user
                count = SessionService.invalidate_all_user_sessions(db, session_info["user_id"])
                
                # Log logout all devices
                audit_service.log_audit_event(
                    event_type=AuditEventType.LOGOUT,
                    severity=SeverityLevel.LOW,
                    user_id=session_info["user_id"],
                    resource="authentication",
                    action="logout_all",
                    details={"sessions_invalidated": count},
                    request=http_request,
                    success=True
                )
                
                return Response(code=0, message=f"已注销所有设备 ({count} 个会话)")
            else:
                return Response(code=401, message="无效的会话")
        else:
            # Get session info before invalidating
            session_info = SessionService.validate_session(db, request.token)
            
            # Invalidate current session only
            success = SessionService.invalidate_session(db, request.token)
            if success:
                # Log logout
                audit_service.log_audit_event(
                    event_type=AuditEventType.LOGOUT,
                    severity=SeverityLevel.LOW,
                    user_id=session_info["user_id"] if session_info else None,
                    resource="authentication",
                    action="logout",
                    details={"session_id": session_info["session_id"] if session_info else None},
                    request=http_request,
                    success=True
                )
                
                return Response(code=0, message="注销成功")
            else:
                return Response(code=401, message="无效的会话")
                
    except Exception as e:
        return Response(code=500, message=f"注销失败: {str(e)}")


@router.post("/api/auth/change-password")
async def change_password(
    request: ChangePasswordRequest, 
    http_request: Request,
    db: Session = Depends(get_db)
):
    """Change user password with validation and security logging"""
    try:
        # Validate new password
        password_validation = security_service.password_validator.validate_password(request.new_password)
        if not password_validation['is_valid']:
            security_service.log_security_event(
                "password_change_validation_failed",
                {"username": request.username, "errors": password_validation['errors']},
                http_request
            )
            return Response(code=400, message="; ".join(password_validation['errors']))
        
        success = AuthService.change_password(
            db, request.username, request.old_password, request.new_password
        )
        
        if success:
            # Invalidate all sessions for security
            SessionService.invalidate_all_user_sessions(db, request.username)
            
            # Log successful password change
            audit_service.log_audit_event(
                event_type=AuditEventType.PASSWORD_CHANGE,
                severity=SeverityLevel.MEDIUM,
                user_id=request.username,
                resource="user_account",
                action="password_change",
                details={
                    "password_strength": password_validation.get('strength_score', 0),
                    "sessions_invalidated": True
                },
                request=http_request,
                success=True
            )
            security_service.log_security_event(
                "password_change_success",
                {
                    "username": request.username,
                    "password_strength": password_validation.get('strength_score', 0)
                },
                http_request
            )
            
            return Response(code=0, message="密码修改成功，请重新登录")
        else:
            security_service.log_security_event(
                "password_change_failed",
                {"username": request.username, "reason": "invalid_old_password"},
                http_request
            )
            return Response(code=31, message="当前密码错误")
            
    except Exception as e:
        security_service.log_security_event(
            "password_change_error",
            {"username": request.username, "error": str(e)},
            http_request
        )
        return Response(code=500, message=f"密码修改失败: {str(e)}")


@router.post("/api/auth/reset-password")
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset user password (placeholder for future implementation)"""
    # TODO: Implement password reset with email/SMS verification
    return Response(code=501, message="密码重置功能暂未实现")


@router.get("/api/auth/me")
async def get_current_user_info(
    http_request: Request,
    db: Session = Depends(get_db)
):
    """Get current user information from session"""
    try:
        # Get token from header
        token = http_request.headers.get("Authorization")
        if token and token.startswith("Bearer "):
            token = token[7:]  # Remove "Bearer " prefix
        else:
            # Fallback to legacy token header
            token = http_request.headers.get("token")
        
        if not token:
            return Response(code=401, message="未提供认证令牌")
        
        # Validate session
        session_info = SessionService.validate_session(db, token)
        if not session_info:
            return Response(code=401, message="无效或已过期的会话")
        
        # Get user details
        user = db.query(User).filter(User.id == session_info["user_id"]).first()
        if not user:
            return Response(code=404, message="用户不存在")
        
        user_detail = db.query(UserDetail).filter(UserDetail.id == user.id).first()
        
        user_info = {
            "user_id": user.id,
            "user_type": user.type,
            "is_active": user.is_active,
            "last_login": user.last_login,
            "created_at": user.created_at,
            "session_expires_at": session_info["expires_at"]
        }
        
        if user_detail:
            user_info.update({
                "name": user_detail.name,
                "email": user_detail.email,
                "phone": user_detail.phone,
                "sex": user_detail.sex,
                "birth": user_detail.birth,
                "address": user_detail.address
            })
        
        return Response(code=0, message="获取用户信息成功", data=user_info)
        
    except Exception as e:
        return Response(code=500, message=f"获取用户信息失败: {str(e)}")


@router.post("/api/auth/refresh")
async def refresh_token(
    http_request: Request,
    db: Session = Depends(get_db)
):
    """Refresh session token"""
    try:
        # Get token from header
        token = http_request.headers.get("Authorization")
        if token and token.startswith("Bearer "):
            token = token[7:]  # Remove "Bearer " prefix
        else:
            # Fallback to legacy token header
            token = http_request.headers.get("token")
        
        if not token:
            return Response(code=401, message="未提供认证令牌")
        
        # Refresh session
        session_info = SessionService.refresh_session(db, token, 24)
        if session_info:
            return Response(
                code=0,
                message="令牌刷新成功",
                data={
                    "expires_at": session_info["expires_at"],
                    "last_accessed": session_info["last_accessed"]
                }
            )
        else:
            return Response(code=401, message="无效的会话")
            
    except Exception as e:
        return Response(code=500, message=f"令牌刷新失败: {str(e)}")