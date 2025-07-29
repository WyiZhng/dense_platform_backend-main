"""
Session Management API

This module handles user session creation, validation, and management.
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session, sessionmaker
from pydantic import BaseModel

from dense_platform_backend_main.database.db import engine
from dense_platform_backend_main.database.table import User, UserSession, UserType
from dense_platform_backend_main.utils.response import Response

router = APIRouter()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SessionService:
    """Service for managing user sessions"""
    
    @staticmethod
    def generate_session_token() -> str:
        """Generate a secure session token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_session_id() -> str:
        """Generate a unique session ID"""
        return secrets.token_urlsafe(16)
    
    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for secure storage"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    @staticmethod
    def create_session(
        db: Session, 
        user_id: str, 
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        expires_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Create a new user session
        
        Args:
            db: Database session
            user_id: User ID
            ip_address: Client IP address
            user_agent: Client user agent
            expires_hours: Session expiration in hours
            
        Returns:
            Dict containing session info and token
        """
        # Generate session data
        session_id = SessionService.generate_session_id()
        token = SessionService.generate_session_token()
        token_hash = SessionService.hash_token(token)
        expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
        
        # Create session record
        user_session = UserSession(
            id=session_id,
            user_id=user_id,
            token=token_hash,
            expires_at=expires_at,
            is_active=True,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(user_session)
        db.commit()
        db.refresh(user_session)
        
        return {
            "session_id": session_id,
            "token": token,
            "expires_at": expires_at,
            "user_id": user_id
        }
    
    @staticmethod
    def validate_session(db: Session, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate a session token
        
        Args:
            db: Database session
            token: Session token to validate
            
        Returns:
            Session info if valid, None otherwise
        """
        token_hash = SessionService.hash_token(token)
        
        # Find active session
        session = db.query(UserSession).filter(
            UserSession.token == token_hash,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).first()
        
        if not session:
            return None
        
        # Update last accessed time
        session.last_accessed = datetime.utcnow()
        db.commit()
        
        # Get user info
        user = db.query(User).filter(User.id == session.user_id).first()
        if not user:
            return None
        
        return {
            "session_id": session.id,
            "user_id": session.user_id,
            "user_type": user.type,
            "expires_at": session.expires_at,
            "last_accessed": session.last_accessed
        }
    
    @staticmethod
    def refresh_session(db: Session, token: str, extends_hours: int = 24) -> Optional[Dict[str, Any]]:
        """
        Refresh a session token (extend expiration)
        
        Args:
            db: Database session
            token: Current session token
            extends_hours: Hours to extend the session
            
        Returns:
            Updated session info if successful, None otherwise
        """
        token_hash = SessionService.hash_token(token)
        
        # Find active session
        session = db.query(UserSession).filter(
            UserSession.token == token_hash,
            UserSession.is_active == True
        ).first()
        
        if not session:
            return None
        
        # Extend expiration
        session.expires_at = datetime.utcnow() + timedelta(hours=extends_hours)
        session.last_accessed = datetime.utcnow()
        db.commit()
        
        return {
            "session_id": session.id,
            "user_id": session.user_id,
            "expires_at": session.expires_at,
            "last_accessed": session.last_accessed
        }
    
    @staticmethod
    def invalidate_session(db: Session, token: str) -> bool:
        """
        Invalidate a session (logout)
        
        Args:
            db: Database session
            token: Session token to invalidate
            
        Returns:
            True if session was invalidated, False otherwise
        """
        token_hash = SessionService.hash_token(token)
        
        # Find and deactivate session
        session = db.query(UserSession).filter(
            UserSession.token == token_hash,
            UserSession.is_active == True
        ).first()
        
        if not session:
            return False
        
        session.is_active = False
        db.commit()
        return True
    
    @staticmethod
    def invalidate_all_user_sessions(db: Session, user_id: str) -> int:
        """
        Invalidate all sessions for a user
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            Number of sessions invalidated
        """
        count = db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True
        ).update({"is_active": False})
        
        db.commit()
        return count
    
    @staticmethod
    def cleanup_expired_sessions(db: Session) -> int:
        """
        Clean up expired sessions
        
        Args:
            db: Database session
            
        Returns:
            Number of sessions cleaned up
        """
        count = db.query(UserSession).filter(
            UserSession.expires_at < datetime.utcnow(),
            UserSession.is_active == True
        ).update({"is_active": False})
        
        db.commit()
        return count
    
    @staticmethod
    def get_user_sessions(db: Session, user_id: str) -> list:
        """
        Get all active sessions for a user
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            List of active sessions
        """
        sessions = db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).all()
        
        return [
            {
                "session_id": session.id,
                "created_at": session.created_at,
                "last_accessed": session.last_accessed,
                "expires_at": session.expires_at,
                "ip_address": session.ip_address,
                "user_agent": session.user_agent
            }
            for session in sessions
        ]


# Request/Response models
class CreateSessionRequest(BaseModel):
    user_id: str
    expires_hours: Optional[int] = 24


class CreateSessionResponse(Response):
    session_id: Optional[str] = None
    token: Optional[str] = None
    expires_at: Optional[datetime] = None


class ValidateSessionRequest(BaseModel):
    token: str


class ValidateSessionResponse(Response):
    valid: bool = False
    user_id: Optional[str] = None
    user_type: Optional[UserType] = None
    expires_at: Optional[datetime] = None


class RefreshSessionRequest(BaseModel):
    token: str
    extends_hours: Optional[int] = 24


class RefreshSessionResponse(Response):
    expires_at: Optional[datetime] = None


class InvalidateSessionRequest(BaseModel):
    token: str


class GetUserSessionsRequest(BaseModel):
    user_id: str


class GetUserSessionsResponse(Response):
    sessions: list = []


# Dependency for getting current user from session
async def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[Dict[str, Any]]:
    """
    Get current user from session token
    
    Args:
        request: FastAPI request object
        db: Database session
        
    Returns:
        User session info if valid, None otherwise
    """
    # Try to get token from header
    token = request.headers.get("Authorization")
    if token and token.startswith("Bearer "):
        token = token[7:]  # Remove "Bearer " prefix
    else:
        # Fallback to legacy token header
        token = request.headers.get("token")
    
    if not token:
        return None
    
    return SessionService.validate_session(db, token)


# API endpoints
@router.post("/api/session/create", response_model=CreateSessionResponse)
async def create_session(
    request: CreateSessionRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """Create a new user session"""
    try:
        # Verify user exists
        user = db.query(User).filter(User.id == request.user_id).first()
        if not user:
            return CreateSessionResponse(code=404, message="User not found")
        
        # Get client info
        ip_address = http_request.client.host if http_request.client else None
        user_agent = http_request.headers.get("user-agent")
        
        # Create session
        session_info = SessionService.create_session(
            db=db,
            user_id=request.user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_hours=request.expires_hours
        )
        
        return CreateSessionResponse(
            code=0,
            message="Session created successfully",
            session_id=session_info["session_id"],
            token=session_info["token"],
            expires_at=session_info["expires_at"]
        )
        
    except Exception as e:
        return CreateSessionResponse(code=500, message=f"Failed to create session: {str(e)}")


@router.post("/api/session/validate", response_model=ValidateSessionResponse)
async def validate_session(request: ValidateSessionRequest, db: Session = Depends(get_db)):
    """Validate a session token"""
    try:
        session_info = SessionService.validate_session(db, request.token)
        
        if session_info:
            return ValidateSessionResponse(
                code=0,
                message="Session is valid",
                valid=True,
                user_id=session_info["user_id"],
                user_type=session_info["user_type"],
                expires_at=session_info["expires_at"]
            )
        else:
            return ValidateSessionResponse(
                code=401,
                message="Invalid or expired session",
                valid=False
            )
            
    except Exception as e:
        return ValidateSessionResponse(
            code=500,
            message=f"Failed to validate session: {str(e)}",
            valid=False
        )


@router.post("/api/session/refresh", response_model=RefreshSessionResponse)
async def refresh_session(request: RefreshSessionRequest, db: Session = Depends(get_db)):
    """Refresh a session token"""
    try:
        session_info = SessionService.refresh_session(
            db, request.token, request.extends_hours
        )
        
        if session_info:
            return RefreshSessionResponse(
                code=0,
                message="Session refreshed successfully",
                expires_at=session_info["expires_at"]
            )
        else:
            return RefreshSessionResponse(code=401, message="Invalid session")
            
    except Exception as e:
        return RefreshSessionResponse(code=500, message=f"Failed to refresh session: {str(e)}")


@router.post("/api/session/invalidate")
async def invalidate_session(request: InvalidateSessionRequest, db: Session = Depends(get_db)):
    """Invalidate a session (logout)"""
    try:
        success = SessionService.invalidate_session(db, request.token)
        
        if success:
            return Response(code=0, message="Session invalidated successfully")
        else:
            return Response(code=401, message="Invalid session")
            
    except Exception as e:
        return Response(code=500, message=f"Failed to invalidate session: {str(e)}")


@router.post("/api/session/invalidate-all")
async def invalidate_all_sessions(
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Invalidate all sessions for a user"""
    if not current_user:
        return Response(code=401, message="Authentication required")
    
    # Only allow users to invalidate their own sessions or admin users
    if current_user["user_id"] != user_id and current_user["user_type"] != UserType.Doctor:
        return Response(code=403, message="Permission denied")
    
    try:
        count = SessionService.invalidate_all_user_sessions(db, user_id)
        return Response(code=0, message=f"Invalidated {count} sessions")
        
    except Exception as e:
        return Response(code=500, message=f"Failed to invalidate sessions: {str(e)}")


@router.post("/api/session/list", response_model=GetUserSessionsResponse)
async def get_user_sessions(
    request: GetUserSessionsRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all active sessions for a user"""
    if not current_user:
        return GetUserSessionsResponse(code=401, message="Authentication required")
    
    # Only allow users to view their own sessions or admin users
    if current_user["user_id"] != request.user_id and current_user["user_type"] != UserType.Doctor:
        return GetUserSessionsResponse(code=403, message="Permission denied")
    
    try:
        sessions = SessionService.get_user_sessions(db, request.user_id)
        return GetUserSessionsResponse(
            code=0,
            message="Sessions retrieved successfully",
            sessions=sessions
        )
        
    except Exception as e:
        return GetUserSessionsResponse(code=500, message=f"Failed to get sessions: {str(e)}")


@router.post("/api/session/cleanup")
async def cleanup_expired_sessions(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clean up expired sessions (admin only)"""
    if not current_user:
        return Response(code=401, message="Authentication required")
    
    # Only allow admin users
    if current_user["user_type"] != UserType.Doctor:
        return Response(code=403, message="Admin access required")
    
    try:
        count = SessionService.cleanup_expired_sessions(db)
        return Response(code=0, message=f"Cleaned up {count} expired sessions")
        
    except Exception as e:
        return Response(code=500, message=f"Failed to cleanup sessions: {str(e)}")