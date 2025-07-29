"""
Authentication Compatibility Layer

This module provides backward compatibility for existing JWT-based authentication
while transitioning to the new session-based system.
"""

from typing import Optional, Dict, Any
from fastapi import Request
from sqlalchemy.orm import Session

from dense_platform_backend_main.utils.jwt import resolveAccountJwt
from dense_platform_backend_main.api.auth.session import SessionService
from dense_platform_backend_main.database.table import User


class AuthCompat:
    """Compatibility layer for authentication"""
    
    @staticmethod
    def resolve_token(token: str, db: Session) -> Optional[Dict[str, Any]]:
        """
        Resolve token using both new session system and legacy JWT
        
        Args:
            token: Authentication token
            db: Database session
            
        Returns:
            User info if token is valid, None otherwise
        """
        # Try new session system first
        session_info = SessionService.validate_session(db, token)
        if session_info:
            return {
                "account": session_info["user_id"],
                "user_id": session_info["user_id"],
                "user_type": session_info["user_type"],
                "session_based": True
            }
        
        # Fallback to legacy JWT
        try:
            jwt_payload = resolveAccountJwt(token)
            if jwt_payload and "account" in jwt_payload:
                # Verify user still exists and is active
                user = db.query(User).filter(User.id == jwt_payload["account"]).first()
                if user and user.is_active:
                    return {
                        "account": jwt_payload["account"],
                        "user_id": jwt_payload["account"],
                        "user_type": user.type,
                        "session_based": False
                    }
        except Exception:
            # JWT validation failed
            pass
        
        return None
    
    @staticmethod
    def get_user_from_request(request: Request, db: Session) -> Optional[Dict[str, Any]]:
        """
        Get user info from request using compatible token resolution
        
        Args:
            request: FastAPI request object
            db: Database session
            
        Returns:
            User info if authenticated, None otherwise
        """
        # Try Authorization header first (Bearer token)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            return AuthCompat.resolve_token(token, db)
        
        # Fallback to legacy token header
        token = request.headers.get("token")
        if token:
            return AuthCompat.resolve_token(token, db)
        
        return None