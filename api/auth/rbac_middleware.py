"""
Global RBAC Middleware

This module provides global middleware for applying role-based access control
to all API endpoints automatically.
"""

from typing import Dict, Any, Optional, List, Tuple
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import re

from dense_platform_backend_main.api.auth.session import SessionService, get_db
from dense_platform_backend_main.services.rbac_service import RBACService
from dense_platform_backend_main.services.rbac_middleware import RBACMiddleware


class GlobalRBACMiddleware:
    """Global RBAC middleware for automatic route protection"""
    
    # Define route patterns and their required permissions
    ROUTE_PERMISSIONS = {
        # Admin routes - require admin permissions
        r'^/admin/users.*': [("admin", "users")],
        r'^/admin/dashboard.*': [("admin", "system")],
        r'^/admin/config.*': [("admin", "system")],
        r'^/admin/rbac.*': [("admin", "roles")],
        
        # User profile routes - require authentication + self-access or admin
        r'^/api/user$': [("user", "read")],
        r'^/api/info$': [("user", "read")],
        r'^/api/submitInfo$': [("user", "write")],
        r'^/api/submitAvatar$': [("user", "write")],
        r'^/api/avatar$': [("user", "read")],
        
        # Report routes - require report permissions
        r'^/api/getReports$': [("report", "read"), ("patient", "reports")],
        r'^/api/report/images$': [("report", "read"), ("patient", "reports"), ("doctor", "review")],
        r'^/api/report/delete$': [("report", "delete"), ("report", "manage")],
        r'^/api/report/detail$': [("report", "read"), ("patient", "reports"), ("doctor", "review")],
        r'^/api/report/diagnose/submit$': [("doctor", "diagnose"), ("report", "write")],
        
        # Doctor routes - require doctor role or specific permissions
        r'^/api/doctor/info.*': [("doctor", "profile")],
        
        # Image routes - require authentication
        r'^/api/image$': [("user", "write")],
        r'^/api/image/get$': [("user", "read")],
        r'^/api/image/getresult_img$': [("user", "read")],
    }
    
    # Routes that don't require authentication
    PUBLIC_ROUTES = [
        r'^/auth/login$',
        r'^/auth/register$',
        r'^/auth/password-reset.*',
        r'^/docs.*',
        r'^/openapi.json$',
        r'^/redoc.*',
        r'^/$',
        r'^/api/doctors$',  # 医生列表API设为公开
    ]
    
    @staticmethod
    def is_public_route(path: str) -> bool:
        """Check if a route is public (doesn't require authentication)"""
        for pattern in GlobalRBACMiddleware.PUBLIC_ROUTES:
            if re.match(pattern, path):
                return True
        return False
    
    @staticmethod
    def get_required_permissions(path: str) -> Optional[List[Tuple[str, str]]]:
        """Get required permissions for a route"""
        for pattern, permissions in GlobalRBACMiddleware.ROUTE_PERMISSIONS.items():
            if re.match(pattern, path):
                return permissions
        return None
    
    @staticmethod
    def check_route_access(
        request: Request,
        db: Session,
        required_permissions: List[Tuple[str, str]]
    ) -> Dict[str, Any]:
        """
        Check if user has access to a route based on required permissions
        
        Args:
            request: FastAPI request object
            db: Database session
            required_permissions: List of (resource, action) tuples
            
        Returns:
            User session info if authorized
            
        Raises:
            HTTPException: If not authorized
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
        
        # Check if user has any of the required permissions
        user_id = session_info["user_id"]
        has_permission = False
        
        for resource, action in required_permissions:
            if RBACService.check_permission(db, user_id, resource, action):
                has_permission = True
                break
        
        if not has_permission:
            perm_strings = [f"{r}:{a}" for r, a in required_permissions]
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions - requires one of: {', '.join(perm_strings)}"
            )
        
        # Enhance session info with roles and permissions
        user_roles = RBACService.get_user_roles(db, user_id)
        user_permissions = RBACService.get_user_permissions(db, user_id)
        
        session_info.update({
            "roles": user_roles,
            "permissions": user_permissions,
            "is_admin": RBACService.has_admin_role(db, user_id)
        })
        
        return session_info
    
    @staticmethod
    def create_route_dependency(path: str):
        """
        Create a dependency function for a specific route
        
        Args:
            path: Route path
            
        Returns:
            Dependency function
        """
        # Check if route is public
        if GlobalRBACMiddleware.is_public_route(path):
            return None
        
        # Get required permissions
        required_permissions = GlobalRBACMiddleware.get_required_permissions(path)
        
        if not required_permissions:
            # Default to requiring authentication for unknown routes
            required_permissions = [("user", "read")]
        
        def route_dependency(
            request: Request,
            db: Session = Depends(get_db)
        ) -> Dict[str, Any]:
            return GlobalRBACMiddleware.check_route_access(
                request, db, required_permissions
            )
        
        return Depends(route_dependency)


class RouteProtectionConfig:
    """Configuration for route protection"""
    
    def __init__(self):
        self.protected_routes = {}
        self.public_routes = set()
        self.default_permissions = [("user", "read")]
    
    def add_protected_route(
        self, 
        pattern: str, 
        permissions: List[Tuple[str, str]]
    ):
        """Add a protected route pattern"""
        self.protected_routes[pattern] = permissions
    
    def add_public_route(self, pattern: str):
        """Add a public route pattern"""
        self.public_routes.add(pattern)
    
    def set_default_permissions(self, permissions: List[Tuple[str, str]]):
        """Set default permissions for unspecified routes"""
        self.default_permissions = permissions
    
    def is_route_public(self, path: str) -> bool:
        """Check if a route is public"""
        for pattern in self.public_routes:
            if re.match(pattern, path):
                return True
        return False
    
    def get_route_permissions(self, path: str) -> List[Tuple[str, str]]:
        """Get permissions required for a route"""
        for pattern, permissions in self.protected_routes.items():
            if re.match(pattern, path):
                return permissions
        return self.default_permissions


# Global route protection configuration
route_config = RouteProtectionConfig()

# Configure protected routes
route_config.add_protected_route(r'^/admin/users.*', [("admin", "users")])
route_config.add_protected_route(r'^/admin/dashboard.*', [("admin", "system")])
route_config.add_protected_route(r'^/admin/config.*', [("admin", "system")])
route_config.add_protected_route(r'^/admin/rbac.*', [("admin", "roles")])

route_config.add_protected_route(r'^/api/user$', [("user", "read")])
route_config.add_protected_route(r'^/api/info$', [("user", "read")])
route_config.add_protected_route(r'^/api/submitInfo$', [("user", "write")])
route_config.add_protected_route(r'^/api/submitAvatar$', [("user", "write")])
route_config.add_protected_route(r'^/api/avatar$', [("user", "read")])

route_config.add_protected_route(r'^/api/getReports$', [("report", "read"), ("patient", "reports")])
route_config.add_protected_route(r'^/api/report/images$', [("report", "read"), ("patient", "reports"), ("doctor", "review")])
route_config.add_protected_route(r'^/api/report/delete$', [("report", "delete"), ("report", "manage")])
route_config.add_protected_route(r'^/api/report/detail$', [("report", "read"), ("patient", "reports"), ("doctor", "review")])
route_config.add_protected_route(r'^/api/report/diagnose/submit$', [("doctor", "diagnose"), ("report", "write")])

route_config.add_protected_route(r'^/api/doctor/info.*', [("doctor", "profile")])

route_config.add_protected_route(r'^/api/image$', [("user", "write")])
route_config.add_protected_route(r'^/api/image/get$', [("user", "read")])
route_config.add_protected_route(r'^/api/image/getresult_img$', [("user", "read")])

# Configure public routes
route_config.add_public_route(r'^/auth/login$')
route_config.add_public_route(r'^/auth/register$')
route_config.add_public_route(r'^/auth/password-reset.*')
route_config.add_public_route(r'^/docs.*')
route_config.add_public_route(r'^/openapi.json$')
route_config.add_public_route(r'^/redoc.*')
route_config.add_public_route(r'^/$')
route_config.add_public_route(r'^/api/doctors$')


def create_global_auth_dependency():
    """
    Create a global authentication dependency that can be applied to all routes
    
    Returns:
        Dependency function
    """
    def global_auth_check(
        request: Request,
        db: Session = Depends(get_db)
    ) -> Optional[Dict[str, Any]]:
        path = request.url.path
        
        # Check if route is public
        if route_config.is_route_public(path):
            return None
        
        # Get required permissions for this route
        required_permissions = route_config.get_route_permissions(path)
        
        # Check access
        return GlobalRBACMiddleware.check_route_access(
            request, db, required_permissions
        )
    
    return Depends(global_auth_check)


# Global authentication dependency
GlobalAuth = create_global_auth_dependency()


def apply_rbac_to_router(router, exclude_paths: Optional[List[str]] = None):
    """
    Apply RBAC protection to all routes in a router
    
    Args:
        router: FastAPI router
        exclude_paths: List of paths to exclude from protection
    """
    exclude_paths = exclude_paths or []
    
    for route in router.routes:
        if hasattr(route, 'path') and route.path not in exclude_paths:
            # Check if route is public
            if not route_config.is_route_public(route.path):
                # Add RBAC dependency to route
                if hasattr(route, 'dependencies'):
                    route.dependencies.append(GlobalAuth)
                else:
                    route.dependencies = [GlobalAuth]


def get_user_from_global_auth(request: Request) -> Optional[Dict[str, Any]]:
    """
    Get user information from global auth context
    
    Args:
        request: FastAPI request object
        
    Returns:
        User information if authenticated, None otherwise
    """
    # This would be set by the global auth middleware
    return getattr(request.state, 'user', None)


def require_permission_for_route(
    resource: str, 
    action: str, 
    allow_self: bool = False,
    user_id_param: Optional[str] = None
):
    """
    Create a route-specific permission requirement
    
    Args:
        resource: Resource name
        action: Action name
        allow_self: Whether to allow self-access
        user_id_param: Parameter name containing user ID for self-access check
        
    Returns:
        Dependency function
    """
    def permission_check(
        request: Request,
        db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        token = RBACMiddleware.get_token_from_request(request)
        
        if not token:
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )
        
        session_info = SessionService.validate_session(db, token)
        if not session_info:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired session"
            )
        
        user_id = session_info["user_id"]
        
        # Check self-access if enabled
        if allow_self and user_id_param:
            path_params = request.path_params
            target_user_id = path_params.get(user_id_param)
            if target_user_id and target_user_id == user_id:
                return session_info
        
        # Check permission
        if not RBACService.check_permission(db, user_id, resource, action):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions - requires {resource}:{action}"
            )
        
        return session_info
    
    return Depends(permission_check)