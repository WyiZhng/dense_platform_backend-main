"""
Password Reset API

This module provides password reset functionality with secure token-based verification.
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from pydantic import BaseModel, EmailStr

from dense_platform_backend_main.database.db import engine
from dense_platform_backend_main.database.table import Base, User, UserDetail
from dense_platform_backend_main.utils.response import Response
from .session import get_db, SessionService
from .auth import AuthService

router = APIRouter()


class PasswordResetToken(Base):
    """Password reset token model"""
    __tablename__ = 'password_reset_token'
    
    id = Column(String(64), primary_key=True)
    user_id = Column(String(20), ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    used_at = Column(DateTime, nullable=True)


class PasswordResetService:
    """Service for managing password reset tokens"""
    
    @staticmethod
    def generate_reset_token() -> str:
        """Generate a secure reset token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for secure storage"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    @staticmethod
    def create_reset_token(db: Session, user_id: str, expires_hours: int = 1) -> str:
        """
        Create a password reset token
        
        Args:
            db: Database session
            user_id: User ID
            expires_hours: Token expiration in hours
            
        Returns:
            Reset token string
        """
        # Invalidate any existing tokens for this user
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.is_used == False
        ).update({"is_used": True, "used_at": datetime.utcnow()})
        
        # Generate new token
        token = PasswordResetService.generate_reset_token()
        token_hash = PasswordResetService.hash_token(token)
        token_id = secrets.token_urlsafe(16)
        expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
        
        # Create token record
        reset_token = PasswordResetToken(
            id=token_id,
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            is_used=False
        )
        
        db.add(reset_token)
        db.commit()
        
        return token
    
    @staticmethod
    def validate_reset_token(db: Session, token: str) -> Optional[str]:
        """
        Validate a reset token and return user ID if valid
        
        Args:
            db: Database session
            token: Reset token to validate
            
        Returns:
            User ID if token is valid, None otherwise
        """
        token_hash = PasswordResetService.hash_token(token)
        
        # Find valid token
        reset_token = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        ).first()
        
        if reset_token:
            return reset_token.user_id
        
        return None
    
    @staticmethod
    def use_reset_token(db: Session, token: str) -> bool:
        """
        Mark a reset token as used
        
        Args:
            db: Database session
            token: Reset token to mark as used
            
        Returns:
            True if token was marked as used, False otherwise
        """
        token_hash = PasswordResetService.hash_token(token)
        
        # Find and mark token as used
        reset_token = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        ).first()
        
        if reset_token:
            reset_token.is_used = True
            reset_token.used_at = datetime.utcnow()
            db.commit()
            return True
        
        return False
    
    @staticmethod
    def cleanup_expired_tokens(db: Session) -> int:
        """
        Clean up expired reset tokens
        
        Args:
            db: Database session
            
        Returns:
            Number of tokens cleaned up
        """
        count = db.query(PasswordResetToken).filter(
            PasswordResetToken.expires_at < datetime.utcnow()
        ).delete()
        
        db.commit()
        return count


# Request/Response models
class RequestPasswordResetRequest(BaseModel):
    username: str
    email: Optional[EmailStr] = None


class RequestPasswordResetResponse(Response):
    reset_token: Optional[str] = None  # In production, this should be sent via email
    expires_at: Optional[datetime] = None


class ValidateResetTokenRequest(BaseModel):
    token: str


class ValidateResetTokenResponse(Response):
    valid: bool = False
    user_id: Optional[str] = None
    expires_at: Optional[datetime] = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    username: str
    old_password: str
    new_password: str


# API endpoints
@router.post("/api/auth/request-password-reset", response_model=RequestPasswordResetResponse)
async def request_password_reset(
    request: RequestPasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    Request a password reset token
    
    In production, this would send an email with the reset link.
    For development, it returns the token directly.
    """
    try:
        # Find user by username
        user = db.query(User).filter(User.id == request.username).first()
        if not user:
            # Don't reveal if user exists or not for security
            return RequestPasswordResetResponse(
                code=0,
                message="如果用户存在，重置链接已发送"
            )
        
        # Check if user is active
        if not user.is_active:
            return RequestPasswordResetResponse(
                code=0,
                message="如果用户存在，重置链接已发送"
            )
        
        # If email is provided, verify it matches
        if request.email:
            user_detail = db.query(UserDetail).filter(UserDetail.id == user.id).first()
            if not user_detail or user_detail.email != request.email:
                return RequestPasswordResetResponse(
                    code=0,
                    message="如果用户存在，重置链接已发送"
                )
        
        # Create reset token
        reset_token = PasswordResetService.create_reset_token(db, user.id, expires_hours=1)
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        # TODO: In production, send email with reset link instead of returning token
        # send_password_reset_email(user.email, reset_token)
        
        return RequestPasswordResetResponse(
            code=0,
            message="密码重置令牌已生成",
            reset_token=reset_token,  # Remove this in production
            expires_at=expires_at
        )
        
    except Exception as e:
        return RequestPasswordResetResponse(
            code=500,
            message=f"请求密码重置失败: {str(e)}"
        )


@router.post("/api/auth/validate-reset-token", response_model=ValidateResetTokenResponse)
async def validate_reset_token(
    request: ValidateResetTokenRequest,
    db: Session = Depends(get_db)
):
    """Validate a password reset token"""
    try:
        user_id = PasswordResetService.validate_reset_token(db, request.token)
        
        if user_id:
            # Get token expiration
            token_hash = PasswordResetService.hash_token(request.token)
            reset_token = db.query(PasswordResetToken).filter(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.is_used == False
            ).first()
            
            return ValidateResetTokenResponse(
                code=0,
                message="令牌有效",
                valid=True,
                user_id=user_id,
                expires_at=reset_token.expires_at if reset_token else None
            )
        else:
            return ValidateResetTokenResponse(
                code=401,
                message="无效或已过期的令牌",
                valid=False
            )
            
    except Exception as e:
        return ValidateResetTokenResponse(
            code=500,
            message=f"验证令牌失败: {str(e)}",
            valid=False
        )


@router.post("/api/auth/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Reset password using a reset token"""
    try:
        # Validate token
        user_id = PasswordResetService.validate_reset_token(db, request.token)
        if not user_id:
            return Response(code=401, message="无效或已过期的令牌")
        
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return Response(code=404, message="用户不存在")
        
        # Hash new password
        hashed_password, salt = AuthService.hash_password(request.new_password)
        password_with_salt = f"{hashed_password}:{salt}"
        
        # Update password
        user.password = password_with_salt
        user.updated_at = datetime.utcnow()
        
        # Mark token as used
        PasswordResetService.use_reset_token(db, request.token)
        
        # Invalidate all existing sessions for security
        SessionService.invalidate_all_user_sessions(db, user_id)
        
        db.commit()
        
        return Response(code=0, message="密码重置成功，请重新登录")
        
    except Exception as e:
        db.rollback()
        return Response(code=500, message=f"密码重置失败: {str(e)}")


@router.post("/api/auth/change-password")
async def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db)
):
    """Change password with current password verification"""
    try:
        # Authenticate with current password
        user = AuthService.authenticate_user(db, request.username, request.old_password)
        if not user:
            return Response(code=401, message="当前密码错误")
        
        # Hash new password
        hashed_password, salt = AuthService.hash_password(request.new_password)
        password_with_salt = f"{hashed_password}:{salt}"
        
        # Update password
        user.password = password_with_salt
        user.updated_at = datetime.utcnow()
        
        # Invalidate all existing sessions for security
        SessionService.invalidate_all_user_sessions(db, user.id)
        
        db.commit()
        
        return Response(code=0, message="密码修改成功，请重新登录")
        
    except Exception as e:
        db.rollback()
        return Response(code=500, message=f"密码修改失败: {str(e)}")


@router.post("/api/auth/cleanup-reset-tokens")
async def cleanup_expired_reset_tokens(db: Session = Depends(get_db)):
    """Clean up expired reset tokens (admin endpoint)"""
    try:
        count = PasswordResetService.cleanup_expired_tokens(db)
        return Response(code=0, message=f"清理了 {count} 个过期令牌")
        
    except Exception as e:
        return Response(code=500, message=f"清理令牌失败: {str(e)}")


# Create the table if it doesn't exist
def create_password_reset_table():
    """Create password reset token table"""
    try:
        PasswordResetToken.__table__.create(engine, checkfirst=True)
        print("Password reset token table created successfully")
    except Exception as e:
        print(f"Error creating password reset token table: {e}")


# Initialize table on import
create_password_reset_table()