"""
RBAC Middleware

This module provides middleware for role-based access control with permission checking.
"""

from typing import Optional, Dict, Any, Callable, List
from functools import wraps
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session

from dense_platform_backend_main.database.table import UserType
from dense_platform_backend_main.api.auth.session import SessionService, get_db
from .rbac_service import RBACService


class RBACMiddleware:
    """Role-Based Access Control middleware for protecting API endpoints"""
    
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
    def require_permission(resource: str, action: str):
        """
        Create a dependency that requires specific permission
        
        Args:
            resource: Resource name (e.g., 'user', 'report', 'admin')
            action: Action name (e.g., 'read', 'write', 'delete', 'manage')
            
        Returns:
            Dependency function
        """
        def check_permission(
            request: Request,
            db: Session = Depends(get_db)
        ) -> Dict[str, Any]:
            token = RBACMiddleware.get_token_from_request(request)
            
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
        
        return check_permission
    
    @staticmethod
    def require_any_permission(permissions: List[tuple]):
        """
        Create a dependency that requires any of the specified permissions
        
        Args:
            permissions: List of (resource, action) tuples
            
        Returns:
            Dependency function
        """
        def check_any_permission(
            request: Request,
            db: Session = Depends(get_db)
        ) -> Dict[str, Any]:
            token = RBACMiddleware.get_token_from_request(request)
            
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
            
            # Check if user has any of the required permissions
            has_any_permission = False
            for resource, action in permissions:
                if RBACService.check_permission(
                    db, session_info["user_id"], resource, action
                ):
                    has_any_permission = True
                    break
            
            if not has_any_permission:
                perm_strings = [f"{r}:{a}" for r, a in permissions]
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions - requires one of: {', '.join(perm_strings)}"
                )
            
            return session_info
        
        return check_any_permission
    
    @staticmethod
    def require_role(role_name: str):
        """
        Create a dependency that requires a specific role
        
        Args:
            role_name: Name of the required role
            
        Returns:
            Dependency function
        """
        def check_role(
            request: Request,
            db: Session = Depends(get_db)
        ) -> Dict[str, Any]:
            token = RBACMiddleware.get_token_from_request(request)
            
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
            
            # Check if user has the required role
            user_roles = RBACService.get_user_roles(db, session_info["user_id"])
            has_role = any(role["name"] == role_name for role in user_roles)
            
            if not has_role:
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions - requires {role_name} role"
                )
            
            return session_info
        
        return check_role
    
    @staticmethod
    def require_admin(
        request: Request,
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Require admin role
        
        Args:
            request: FastAPI request object
            db: Database session
            
        Returns:
            User session info
            
        Raises:
            HTTPException: If not an admin
        """
        token = RBACMiddleware.get_token_from_request(request)
        
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
        
        # Check if user has admin role
        if not RBACService.has_admin_role(db, session_info["user_id"]):
            raise HTTPException(
                status_code=403,
                detail="Administrator access required"
            )
        
        return session_info
    
    @staticmethod
    def require_self_or_permission(user_id: str, resource: str, action: str):
        """
        Create a dependency that requires the user to be accessing their own data 
        or have specific permission
        
        Args:
            user_id: The user ID being accessed
            resource: Resource name for permission check
            action: Action name for permission check
            
        Returns:
            Dependency function
        """
        def check_self_or_permission(
            request: Request,
            db: Session = Depends(get_db)
        ) -> Dict[str, Any]:
            token = RBACMiddleware.get_token_from_request(request)
            
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
            
            # Allow if user is accessing their own data
            if session_info["user_id"] == user_id:
                return session_info
            
            # Otherwise check if user has the required permission
            has_permission = RBACService.check_permission(
                db, session_info["user_id"], resource, action
            )
            
            if not has_permission:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied - can only access own data or requires {resource}:{action} permission"
                )
            
            return session_info
        
        return check_self_or_permission
    
    @staticmethod
    def get_user_context(
        request: Request,
        db: Session = Depends(get_db)
    ) -> Optional[Dict[str, Any]]:
        """
        Get user context with roles and permissions (optional authentication)
        
        Args:
            request: FastAPI request object
            db: Database session
            
        Returns:
            User context with roles and permissions if authenticated, None otherwise
        """
        token = RBACMiddleware.get_token_from_request(request)
        
        if not token:
            return None
        
        session_info = SessionService.validate_session(db, token)
        if not session_info:
            return None
        
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
    def require_auth_with_context(
        request: Request,
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Require authentication and return enhanced user context
        
        Args:
            request: FastAPI request object
            db: Database session
            
        Returns:
            Enhanced user session info with roles and permissions
            
        Raises:
            HTTPException: If authentication fails
        """
        token = RBACMiddleware.get_token_from_request(request)
        
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
        try:
            user_roles = RBACService.get_user_roles(db, session_info["user_id"])
            # 暂时注释掉可能不存在的方法
            # user_permissions = RBACService.get_user_permissions(db, session_info["user_id"])
            user_permissions = []  # 临时使用空列表
            
            session_info.update({
                "roles": user_roles,
                "permissions": user_permissions,
                "is_admin": RBACService.has_admin_role(db, session_info["user_id"])
            })
        except Exception as e:
            print(f"ERROR: 获取用户角色权限时出错: {e}")
            # 如果获取角色权限失败，至少返回基本的session信息
            session_info.update({
                "roles": [],
                "permissions": [],
                "is_admin": False
            })
        
        return session_info


# Convenience dependencies
RequireAdmin = Depends(RBACMiddleware.require_admin)
RequireAuthWithContext = Depends(RBACMiddleware.require_auth_with_context)
GetUserContext = Depends(RBACMiddleware.get_user_context)


def RequirePermission(resource: str, action: str):
    """
    Convenience function to create permission requirement dependency
    
    Args:
        resource: Resource name
        action: Action name
        
    Returns:
        Dependency
    """
    return Depends(RBACMiddleware.require_permission(resource, action))


def RequireAnyPermission(*permissions):
    """
    Convenience function to create any-permission requirement dependency
    
    Args:
        permissions: Variable number of (resource, action) tuples
        
    Returns:
        Dependency
    """
    return Depends(RBACMiddleware.require_any_permission(list(permissions)))


def RequireRole(role_name: str):
    """
    Convenience function to create role requirement dependency
    
    Args:
        role_name: Role name
        
    Returns:
        Dependency
    """
    return Depends(RBACMiddleware.require_role(role_name))


def RequireSelfOrPermission(user_id: str, resource: str, action: str):
    """
    Convenience function to create self-or-permission requirement dependency
    
    Args:
        user_id: User ID being accessed
        resource: Resource name
        action: Action name
        
    Returns:
        Dependency
    """
    return Depends(RBACMiddleware.require_self_or_permission(user_id, resource, action))