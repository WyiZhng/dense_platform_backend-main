"""
User Logout API

This module provides logout functionality with proper session management.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from dense_platform_backend_main.utils.response import Response
from dense_platform_backend_main.api.auth.session import SessionService, get_db
from dense_platform_backend_main.api.auth.middleware import AuthMiddleware

router = APIRouter()


class LogoutRequest(BaseModel):
    token: Optional[str] = None
    logout_all: Optional[bool] = False


@router.post("/api/logout")
async def logout(
    request: LogoutRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    Logout endpoint with proper session management
    
    This endpoint preserves user data while invalidating sessions
    """
    try:
        # Get token from request body or header
        token = request.token
        if not token:
            token = AuthMiddleware.get_token_from_request(http_request)
        
        if not token:
            return Response(code=401, message="未提供认证令牌")
        
        if request.logout_all:
            # Get user from session first
            session_info = SessionService.validate_session(db, token)
            if session_info:
                # Invalidate all sessions for this user
                count = SessionService.invalidate_all_user_sessions(db, session_info["user_id"])
                return Response(code=0, message=f"已注销所有设备 ({count} 个会话)")
            else:
                return Response(code=401, message="无效的会话")
        else:
            # Invalidate current session only
            success = SessionService.invalidate_session(db, token)
            if success:
                return Response(code=0, message="注销成功")
            else:
                return Response(code=401, message="无效的会话")
                
    except Exception as e:
        return Response(code=500, message=f"注销失败: {str(e)}")


@router.post("/api/user/logout")
async def user_logout(
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    Alternative logout endpoint for user namespace
    """
    try:
        token = AuthMiddleware.get_token_from_request(http_request)
        
        if not token:
            return Response(code=401, message="未提供认证令牌")
        
        # Invalidate current session
        success = SessionService.invalidate_session(db, token)
        if success:
            return Response(code=0, message="注销成功")
        else:
            return Response(code=401, message="无效的会话")
                
    except Exception as e:
        return Response(code=500, message=f"注销失败: {str(e)}")