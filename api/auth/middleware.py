"""
Authentication Middleware

This module provides middleware for protecting API endpoints with session-based authentication.
"""

from typing import Optional, Dict, Any, Callable, List
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from dense_platform_backend_main.database.table import UserType
from .session import SessionService, get_db

# Security scheme for Bearer token
security = HTTPBearer(auto_error=False)


class AuthMiddleware:
    """Authentication middleware for protecting API endpoints"""
    
    @staticmethod
    def get_token_from_request(request: Request) -> Optional[str]:
        """
        Extract token from request headers
        
        Args:
            request: FastAPI request object
            
        Returns:
            Token string if found, None otherwise
        """
        # Try Authorization header first (Bearer token)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix
        
        # Fallback to legacy token header
        return request.headers.get("token")
    
    @staticmethod
    def require_auth(
        request: Request,
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Require authentication for an endpoint
        
        Args:
            request: FastAPI request object
            db: Database session
            
        Returns:
            User session info
            
        Raises:
            HTTPException: If authentication fails
        """
        token = AuthMiddleware.get_token_from_request(request)
        
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
        
        return session_info
    
    @staticmethod
    def require_user_type(allowed_types: List[UserType]):
        """
        Create a dependency that requires specific user types
        
        Args:
            allowed_types: List of allowed user types
            
        Returns:
            Dependency function
        """
        def check_user_type(
            request: Request,
            db: Session = Depends(get_db)
        ) -> Dict[str, Any]:
            session_info = AuthMiddleware.require_auth(request, db)
            
            if session_info["user_type"] not in allowed_types:
                raise HTTPException(
                    status_code=403,
                    detail="Insufficient permissions"
                )
            
            return session_info
        
        return check_user_type
    
    @staticmethod
    def require_doctor(
        request: Request,
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Require doctor authentication
        
        Args:
            request: FastAPI request object
            db: Database session
            
        Returns:
            User session info
            
        Raises:
            HTTPException: If not a doctor
        """
        session_info = AuthMiddleware.require_auth(request, db)
        
        if session_info["user_type"] != UserType.Doctor:
            raise HTTPException(
                status_code=403,
                detail="Doctor access required"
            )
        
        return session_info
    
    @staticmethod
    def require_patient(
        request: Request,
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Require patient authentication
        
        Args:
            request: FastAPI request object
            db: Database session
            
        Returns:
            User session info
            
        Raises:
            HTTPException: If not a patient
        """
        session_info = AuthMiddleware.require_auth(request, db)
        
        if session_info["user_type"] != UserType.Patient:
            raise HTTPException(
                status_code=403,
                detail="Patient access required"
            )
        
        return session_info
    
    @staticmethod
    def require_self_or_doctor(user_id: str):
        """
        Create a dependency that requires the user to be accessing their own data or be a doctor
        
        Args:
            user_id: The user ID being accessed
            
        Returns:
            Dependency function
        """
        def check_self_or_doctor(
            request: Request,
            db: Session = Depends(get_db)
        ) -> Dict[str, Any]:
            session_info = AuthMiddleware.require_auth(request, db)
            
            # Allow if user is accessing their own data or if user is a doctor
            if (session_info["user_id"] != user_id and 
                session_info["user_type"] != UserType.Doctor):
                raise HTTPException(
                    status_code=403,
                    detail="Access denied - can only access own data or require doctor privileges"
                )
            
            return session_info
        
        return check_self_or_doctor
    
    @staticmethod
    def optional_auth(
        request: Request,
        db: Session = Depends(get_db)
    ) -> Optional[Dict[str, Any]]:
        """
        Optional authentication - returns user info if authenticated, None otherwise
        
        Args:
            request: FastAPI request object
            db: Database session
            
        Returns:
            User session info if authenticated, None otherwise
        """
        token = AuthMiddleware.get_token_from_request(request)
        
        if not token:
            return None
        
        return SessionService.validate_session(db, token)


# Convenience dependencies
RequireAuth = Depends(AuthMiddleware.require_auth)
RequireDoctor = Depends(AuthMiddleware.require_doctor)
RequirePatient = Depends(AuthMiddleware.require_patient)
OptionalAuth = Depends(AuthMiddleware.optional_auth)


def RequireUserType(*user_types: UserType):
    """
    Convenience function to create user type requirement dependency
    
    Args:
        user_types: Allowed user types
        
    Returns:
        Dependency
    """
    return Depends(AuthMiddleware.require_user_type(list(user_types)))


def RequireSelfOrDoctor(user_id: str):
    """
    Convenience function to create self-or-doctor requirement dependency
    
    Args:
        user_id: User ID being accessed
        
    Returns:
        Dependency
    """
    return Depends(AuthMiddleware.require_self_or_doctor(user_id))