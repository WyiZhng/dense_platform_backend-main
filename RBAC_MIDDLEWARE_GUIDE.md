# RBAC Middleware Implementation Guide

This document provides a comprehensive guide to the Role-Based Access Control (RBAC) middleware implementation in the Dense Platform backend.

## Overview

The RBAC middleware system provides automatic route protection and permission checking for all API endpoints. It ensures that users can only access resources they have permission to use based on their assigned roles and permissions.

## Architecture

### Core Components

1. **RBACService** (`services/rbac_service.py`)
   - Handles role and permission management
   - Provides permission checking functionality
   - Manages user role assignments

2. **RBACMiddleware** (`services/rbac_middleware.py`)
   - Core middleware for route protection
   - Provides dependency functions for FastAPI endpoints
   - Handles authentication and authorization

3. **GlobalRBACMiddleware** (`api/auth/rbac_middleware.py`)
   - Global route protection configuration
   - Automatic permission mapping for routes
   - Route pattern matching and protection

## Permission System

### Default Permissions

The system includes the following default permissions:

#### User Management
- `user.read` - Read user information
- `user.write` - Create and update user information
- `user.delete` - Delete user accounts
- `user.manage` - Full user management access

#### Report Management
- `report.read` - Read medical reports
- `report.write` - Create and update medical reports
- `report.delete` - Delete medical reports
- `report.manage` - Full report management access

#### Admin Permissions
- `admin.system` - System administration access
- `admin.users` - User administration access
- `admin.roles` - Role and permission management
- `admin.audit` - Access to audit logs

#### Doctor Permissions
- `doctor.diagnose` - Create medical diagnoses
- `doctor.review` - Review patient reports
- `doctor.comment` - Add comments to reports
- `doctor.profile` - Manage doctor profile

#### Patient Permissions
- `patient.profile` - Manage own profile
- `patient.reports` - View own reports

### Default Roles

#### Admin Role
- Full system access
- All permissions included
- Can manage users, roles, and system configuration

#### Doctor Role
- Medical professional access
- Can review reports, create diagnoses, and manage own profile
- Limited administrative access

#### Patient Role
- Basic user access
- Can manage own profile and view own reports
- No administrative access

## Usage Examples

### Basic Authentication

```python
from dense_platform_backend_main.services.rbac_middleware import RequireAuthWithContext

@router.post("/api/user")
async def get_user_info(
    current_user = RequireAuthWithContext
):
    user_id = current_user["user_id"]
    # Access user information
    return {"user_id": user_id}
```

### Permission-Based Access

```python
from dense_platform_backend_main.services.rbac_middleware import RequirePermission

@router.post("/api/admin/users")
async def manage_users(
    current_user = RequirePermission("admin", "users")
):
    # Only users with admin:users permission can access
    return {"message": "User management access granted"}
```

### Role-Based Access

```python
from dense_platform_backend_main.services.rbac_middleware import RequireRole

@router.post("/api/doctor/diagnose")
async def create_diagnosis(
    current_user = RequireRole("doctor")
):
    # Only users with doctor role can access
    return {"message": "Doctor access granted"}
```

### Multiple Permission Options

```python
from dense_platform_backend_main.services.rbac_middleware import RequireAnyPermission

@router.post("/api/reports")
async def get_reports(
    current_user = RequireAnyPermission(
        ("report", "read"),
        ("patient", "reports"),
        ("doctor", "review")
    )
):
    # Users with any of these permissions can access
    return {"reports": []}
```

### Admin Access

```python
from dense_platform_backend_main.services.rbac_middleware import RequireAdmin

@router.post("/admin/system/config")
async def system_config(
    current_user = RequireAdmin
):
    # Only admin users can access
    return {"config": {}}
```

## Route Protection Configuration

### Automatic Route Protection

The system automatically protects routes based on patterns defined in `GlobalRBACMiddleware`:

```python
ROUTE_PERMISSIONS = {
    # Admin routes
    r'^/admin/users.*': [("admin", "users")],
    r'^/admin/dashboard.*': [("admin", "system")],
    r'^/admin/config.*': [("admin", "system")],
    
    # User routes
    r'^/api/user$': [("user", "read")],
    r'^/api/info$': [("user", "read")],
    
    # Report routes
    r'^/api/getReports$': [("report", "read"), ("patient", "reports")],
    r'^/api/report/delete$': [("report", "delete"), ("report", "manage")],
}
```

### Public Routes

Routes that don't require authentication:

```python
PUBLIC_ROUTES = [
    r'^/auth/login$',
    r'^/auth/register$',
    r'^/auth/password-reset.*',
    r'^/docs.*',
    r'^/openapi.json$',
]
```

## Error Handling

### Authentication Errors

- **401 Unauthorized**: No token provided or invalid session
- **403 Forbidden**: Insufficient permissions for the requested resource

### Example Error Responses

```json
{
  "detail": "Authentication required - no token provided"
}
```

```json
{
  "detail": "Insufficient permissions - requires admin:users"
}
```

## Best Practices

### 1. Use Appropriate Permission Levels

- Use specific permissions rather than broad access
- Follow the principle of least privilege
- Grant only necessary permissions for each role

### 2. Consistent Permission Naming

- Use format: `resource.action` (e.g., `user.read`, `report.write`)
- Keep resource names consistent across the system
- Use standard action names: `read`, `write`, `delete`, `manage`

### 3. Proper Error Handling

```python
@router.post("/api/protected")
async def protected_endpoint(
    current_user = RequirePermission("resource", "action")
):
    try:
        # Your endpoint logic here
        return {"success": True}
    except Exception as e:
        # Handle errors appropriately
        raise HTTPException(status_code=500, detail=str(e))
```

### 4. Self-Access Patterns

For endpoints where users should access their own data:

```python
@router.get("/api/users/{user_id}")
async def get_user_details(
    user_id: str,
    current_user = RequireAuthWithContext
):
    # Allow self-access or admin access
    if current_user["user_id"] != user_id:
        # Check if user has admin permission
        if not any(perm["resource"] == "admin" and perm["action"] == "users" 
                  for perm in current_user.get("permissions", [])):
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Proceed with logic
    return {"user_id": user_id}
```

## Testing RBAC Implementation

### Running Tests

```bash
# Basic RBAC functionality test
python test_rbac_basic.py

# Admin functionality test
python test_admin_basic.py

# Complete system test
python test_admin_functionality.py
```

### Test Coverage

The test suite covers:
- RBAC middleware imports and functionality
- Route protection configuration
- Endpoint integration with RBAC
- Admin endpoint protection
- Permission hierarchy and inheritance

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure all RBAC middleware modules are properly imported
   - Check Python path configuration

2. **Permission Denied**
   - Verify user has required permissions
   - Check role assignments
   - Ensure RBAC system is properly initialized

3. **Token Issues**
   - Verify token is included in request headers
   - Check token format (Bearer token vs legacy token header)
   - Ensure session is valid and not expired

### Debug Information

Enable debug logging to troubleshoot RBAC issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Migration Guide

### Updating Existing Endpoints

1. **Add RBAC Imports**
```python
from dense_platform_backend_main.services.rbac_middleware import (
    RequireAuthWithContext, RequirePermission, RequireRole
)
```

2. **Replace Authentication Logic**
```python
# Old way
token = request.headers.get("token")
user_info = validate_token(token)

# New way
@router.post("/endpoint")
async def endpoint(current_user = RequireAuthWithContext):
    user_id = current_user["user_id"]
```

3. **Add Permission Checks**
```python
# Add appropriate permission requirements
current_user = RequirePermission("resource", "action")
```

## Security Considerations

### Token Security
- Use Bearer tokens in Authorization header
- Implement proper token expiration
- Secure token storage and transmission

### Permission Granularity
- Define specific permissions for each resource
- Avoid overly broad permissions
- Regular permission audits

### Audit Logging
- All permission checks are logged
- Failed access attempts are recorded
- Regular security monitoring

## Conclusion

The RBAC middleware system provides comprehensive security for the Dense Platform backend. It ensures proper authentication and authorization for all endpoints while maintaining flexibility for different access patterns and requirements.

For additional support or questions, refer to the test files and implementation examples in the codebase.