"""
Doctor API Token Dependency

This module provides dependency functions for doctor API endpoints to handle token extraction
from headers and automatic injection into request objects.
"""

from typing import Dict, Any, Optional
from fastapi import Request, Header, HTTPException, Depends, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel

# Token request model for body parsing
class TokenRequest(BaseModel):
    token: Optional[str] = None

from dense_platform_backend_main.api.auth.session import get_db, SessionService
from dense_platform_backend_main.database.table import UserType

# Create security scheme for Bearer token
security = HTTPBearer(auto_error=False)

async def get_token_from_header(
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """
    Extract token from Authorization header
    
    Args:
        authorization: Authorization credentials from header
        
    Returns:
        Token string
        
    Raises:
        HTTPException: If no valid token is found
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required - no token provided")
    
    return authorization.credentials


async def get_token_from_header_or_body(
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token_request: Optional[TokenRequest] = None
) -> str:
    """
    Extract token from Authorization header or request body
    
    Args:
        authorization: Authorization credentials from header
        token_request: Token from request body (optional)
        
    Returns:
        Token string
        
    Raises:
        HTTPException: If no valid token is found
    """
    # First try to get token from Authorization header
    if authorization:
        return authorization.credentials
    
    # If no header token, try to get from request body
    if token_request and token_request.token:
        return token_request.token
    
    # If no token found in either place, return error
    raise HTTPException(status_code=401, detail="Authentication required - no token provided")


async def validate_doctor_token(
    token: str = Depends(get_token_from_header),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Validate token and ensure user is a doctor
    
    Args:
        token: JWT token
        db: Database session
        
    Returns:
        Session info with user details
        
    Raises:
        HTTPException: If authentication fails or user is not a doctor
    """
    # Validate session
    session_info = SessionService.validate_session(db, token)
    if not session_info:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    # Check if user is doctor or has doctor role
    user_id = session_info["user_id"]
    user_type = session_info.get("user_type", UserType.Patient)
    
    # Get user roles for additional checking
    from dense_platform_backend_main.services.rbac_service import RBACService
    user_roles = RBACService.get_user_roles(db, user_id)
    
    is_doctor = (
        user_type == UserType.Doctor or
        any(role["name"] == "doctor" for role in user_roles) or
        any(role["name"] == "admin" for role in user_roles)
    )
    
    if not is_doctor:
        raise HTTPException(status_code=403, detail="Doctor access required")
    
    # Enhance session info
    session_info.update({
        "roles": user_roles,
        "permissions": RBACService.get_user_permissions(db, user_id),
        "is_admin": RBACService.has_admin_role(db, user_id)
    })
    
    return session_info


async def validate_doctor_token_flexible(
    token: str = Depends(get_token_from_header_or_body),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Validate token from header or body and ensure user is a doctor
    
    Args:
        token: JWT token from header or body
        db: Database session
        
    Returns:
        Session info with user details
        
    Raises:
        HTTPException: If authentication fails or user is not a doctor
    """
    # Validate session
    session_info = SessionService.validate_session(db, token)
    if not session_info:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    # Check if user is doctor or has doctor role
    user_id = session_info["user_id"]
    user_type = session_info.get("user_type", UserType.Patient)
    
    # Get user roles for additional checking
    from dense_platform_backend_main.services.rbac_service import RBACService
    user_roles = RBACService.get_user_roles(db, user_id)
    
    is_doctor = (
        user_type == UserType.Doctor or
        any(role["name"] == "doctor" for role in user_roles) or
        any(role["name"] == "admin" for role in user_roles)
    )
    
    if not is_doctor:
        raise HTTPException(status_code=403, detail="Doctor access required")
    
    # Enhance session info
    session_info.update({
        "roles": user_roles,
        "permissions": RBACService.get_user_permissions(db, user_id),
        "is_admin": RBACService.has_admin_role(db, user_id)
    })
    
    return session_info