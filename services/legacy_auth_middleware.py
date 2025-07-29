"""
Legacy Authentication Middleware

This module provides middleware for legacy endpoints that pass tokens in request body
instead of Authorization headers.
"""

from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session

from dense_platform_backend_main.database.table import UserType
from dense_platform_backend_main.api.auth.session import SessionService, get_db
from dense_platform_backend_main.services.rbac_service import RBACService


class LegacyAuthMiddleware:
    """Legacy authentication middleware for endpoints using token in request body"""
    
    @staticmethod
    def validate_token_from_body(token: str, db: Session) -> Dict[str, Any]:
        """
        Validate token and return user session info
        
        Args:
            token: Token string from request body
            db: Database session
            
        Returns:
            User session info
            
        Raises:
            HTTPException: If authentication fails
        """
        if not token:
            raise HTTPException(
                status_code=401,
                detail="Authentication required - no token provided"
            )
        
        session_info = SessionService.validate_session(db, token)
        if not session_info:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired session"
            )
        
        # Enhance session info with roles and permissions
        user_roles = RBACService.get_user_roles(db, session_info["user_id"])
        user_permissions = RBACService.get_user_permissions(db, session_info["user_id"])
        
        session_info.update({
            "roles": user_roles,
            "permissions": user_permissions,
            "is_admin": RBACService.has_admin_role(db, session_info["user_id"])
        })
        
        return session_info
    
    @staticmethod
    def require_doctor_legacy(token: str, db: Session) -> Dict[str, Any]:
        """
        Require doctor authentication from token in request body
        
        Args:
            token: Token from request body
            db: Database session
            
        Returns:
            User session info
            
        Raises:
            HTTPException: If not a doctor
        """
        session_info = LegacyAuthMiddleware.validate_token_from_body(token, db)
        
        # Check if user is doctor or has doctor role
        is_doctor = (
            session_info["user_type"] == UserType.Doctor or
            any(role["name"] == "doctor" for role in session_info.get("roles", [])) or
            any(role["name"] == "admin" for role in session_info.get("roles", []))
        )
        
        if not is_doctor:
            raise HTTPException(
                status_code=403,
                detail="Doctor access required"
            )
        
        return session_info
    
    @staticmethod
    def require_permission_legacy(token: str, db: Session, resource: str, action: str) -> Dict[str, Any]:
        """
        Require specific permission from token in request body
        
        Args:
            token: Token from request body
            db: Database session
            resource: Resource name
            action: Action name
            
        Returns:
            User session info
            
        Raises:
            HTTPException: If permission denied
        """
        session_info = LegacyAuthMiddleware.validate_token_from_body(token, db)
        
        # Check if user has the required permission
        has_permission = RBACService.check_permission(
            db, session_info["user_id"], resource, action
        )
        
        if not has_permission:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions - requires {resource}:{action}"
            )
        
        return session_info
    
    @staticmethod
    def require_auth_legacy(token: str, db: Session) -> Dict[str, Any]:
        """
        Require authentication from token in request body
        
        Args:
            token: Token from request body
            db: Database session
            
        Returns:
            User session info
        """
        return LegacyAuthMiddleware.validate_token_from_body(token, db)


# Convenience functions for use in endpoints
def RequireDoctorLegacy(token: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Convenience function to require doctor authentication from request body token
    """
    return LegacyAuthMiddleware.require_doctor_legacy(token, db)


def RequirePermissionLegacy(resource: str, action: str):
    """
    Convenience function to require specific permission from request body token
    """
    def check_permission(token: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
        return LegacyAuthMiddleware.require_permission_legacy(token, db, resource, action)
    return check_permission


def RequireAuthLegacy(token: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Convenience function to require authentication from request body token
    """
    return LegacyAuthMiddleware.require_auth_legacy(token, db)