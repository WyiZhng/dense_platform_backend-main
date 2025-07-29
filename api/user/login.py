from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from dense_platform_backend_main.database.table import UserType
from dense_platform_backend_main.utils.response import Response
from pydantic import BaseModel

from dense_platform_backend_main.api.auth.auth import AuthService
from dense_platform_backend_main.api.auth.session import SessionService, get_db

router = APIRouter()


class LoginRequest(BaseModel):  # 登录请求
    username: str
    password: str


class RegisterRequest(BaseModel):  # 注册请求
    username: str
    password: str
    type: UserType


class LoginResponse(Response):  # 登录响应
    def __init__(self, **data: Any):
        super().__init__(**data)

    token: Optional[str] = None  # 登录成功时，这个字段会包含生成的 JWT 令牌；否则为 None。
    user_id: Optional[str] = None
    username: Optional[str] = None
    type: Optional[int] = None
    user_type: Optional[int] = None
    is_admin: Optional[bool] = None
    roles: Optional[list] = None
    permissions: Optional[list] = None


@router.post("/api/login", response_model=LoginResponse)
async def login(request: LoginRequest, http_request: Request, db: Session = Depends(get_db)):  # 登录
    """Legacy login endpoint - redirects to new auth system with security enhancements"""
    try:
        # Import security service
        from dense_platform_backend_main.services.security_service import security_service
        
        # Check rate limiting
        if security_service.check_authentication_rate_limit(http_request):
            security_service.log_security_event(
                "rate_limit_exceeded",
                {"username": request.username, "action": "legacy_login"},
                http_request
            )
            return LoginResponse(code=429, message="登录尝试过于频繁，请稍后重试", token=None)
        
        # Record authentication attempt
        security_service.record_authentication_attempt(http_request, request.username)
        
        # Validate input
        username_validation = security_service.input_validator.validate_username(request.username)
        if not username_validation['is_valid']:
            security_service.log_security_event(
                "invalid_input",
                {"username": request.username, "errors": username_validation['errors']},
                http_request
            )
            return LoginResponse(code=400, message="用户名格式不正确", token=None)
        
        # Authenticate user using new system
        user = AuthService.authenticate_user(db, request.username, request.password)
        if not user:
            security_service.log_security_event(
                "login_failed",
                {"username": request.username, "reason": "invalid_credentials", "endpoint": "legacy"},
                http_request
            )
            return LoginResponse(code=31, message="错误的账号或者密码", token=None)
        
        # Check if user is active
        if not user.is_active:
            security_service.log_security_event(
                "login_failed",
                {"username": request.username, "reason": "account_disabled", "endpoint": "legacy"},
                http_request
            )
            return LoginResponse(code=32, message="账号已被禁用", token=None)
        
        # Clear rate limiting on successful login
        security_service.clear_authentication_attempts(http_request, request.username)
        
        # Create session
        ip_address = http_request.client.host if http_request.client else None
        user_agent = http_request.headers.get("user-agent")
        
        session_info = SessionService.create_session(
            db=db,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_hours=24
        )
        
        # Log successful login
        security_service.log_security_event(
            "login_success",
            {"username": request.username, "user_type": user.type.value, "endpoint": "legacy"},
            http_request
        )
        
        # 根据用户名和用户类型确定用户角色
        user_type = user.type.value
        is_admin = False
        
        # 如果用户名是admin，直接设置为管理员
        if request.username.lower() == "admin":
            user_type = 2  # Admin type
            is_admin = True
        
        # 获取用户的RBAC角色和权限
        from dense_platform_backend_main.services.rbac_service import RBACService
        user_roles = RBACService.get_user_roles(db, user.id)
        user_permissions = RBACService.get_user_permissions(db, user.id)
        
        # 如果用户有admin角色，也设置为管理员
        if any(role["name"] == "admin" for role in user_roles):
            user_type = 2
            is_admin = True
        
        # 构建增强的响应数据
        response_data = {
            "token": session_info["token"],
            "user_id": user.id,
            "username": request.username,
            "type": user_type,
            "user_type": user_type,
            "is_admin": is_admin,
            "roles": user_roles,
            "permissions": user_permissions
        }
        
        return LoginResponse(code=0, message="登录成功", token=session_info["token"], **response_data)
        
    except Exception as e:
        # Import security service for error logging
        from dense_platform_backend_main.services.security_service import security_service
        security_service.log_security_event(
            "login_error",
            {"username": request.username, "error": str(e), "endpoint": "legacy"},
            http_request
        )
        return LoginResponse(code=500, message=f"登录失败: {str(e)}", token=None)


@router.post("/api/register", response_model=LoginResponse)
async def register(request: RegisterRequest, http_request: Request, db: Session = Depends(get_db)):
    """Legacy register endpoint - redirects to new auth system with security enhancements"""
    try:
        # Import security service
        from dense_platform_backend_main.services.security_service import security_service
        
        # Check rate limiting
        if security_service.check_authentication_rate_limit(http_request):
            security_service.log_security_event(
                "rate_limit_exceeded",
                {"username": request.username, "action": "legacy_register"},
                http_request
            )
            return LoginResponse(code=429, message="注册尝试过于频繁，请稍后重试", token=None)
        
        # Record authentication attempt
        security_service.record_authentication_attempt(http_request, request.username)
        
        # Validate registration input
        validation_result = security_service.validate_registration_input(
            username=request.username,
            password=request.password
        )
        
        if not validation_result['is_valid']:
            security_service.log_security_event(
                "registration_validation_failed",
                {"username": request.username, "errors": validation_result['errors'], "endpoint": "legacy"},
                http_request
            )
            return LoginResponse(code=400, message="; ".join(validation_result['errors']), token=None)
        
        # Create user using new system
        user = AuthService.create_user(
            db=db,
            username=request.username,
            password=request.password,
            user_type=request.type
        )
        
        if not user:
            security_service.log_security_event(
                "registration_failed",
                {"username": request.username, "reason": "username_exists", "endpoint": "legacy"},
                http_request
            )
            return LoginResponse(code=32, message="已存在的账号，如果忘记密码请联系管理员，或者更换账号ID重新注册", token=None)
        
        # Clear rate limiting on successful registration
        security_service.clear_authentication_attempts(http_request, request.username)
        
        # Create session for new user
        ip_address = http_request.client.host if http_request.client else None
        user_agent = http_request.headers.get("user-agent")
        
        session_info = SessionService.create_session(
            db=db,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_hours=24
        )
        
        # Log successful registration
        security_service.log_security_event(
            "registration_success",
            {
                "username": request.username,
                "user_type": request.type.value,
                "password_strength": validation_result.get('password_strength', 0),
                "endpoint": "legacy"
            },
            http_request
        )
        
        return LoginResponse(code=0, message="注册成功", token=session_info["token"])
        
    except Exception as e:
        # Import security service for error logging
        from dense_platform_backend_main.services.security_service import security_service
        security_service.log_security_event(
            "registration_error",
            {"username": request.username, "error": str(e), "endpoint": "legacy"},
            http_request
        )
        return LoginResponse(code=500, message=f"注册失败: {str(e)}", token=None)


"""

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    type: UserType
    pass


class LoginResponse(Response):
    def __init__(self, **data: Any):
        super().__init__(**data)

    token: Optional[str] = None


@router.post("/api/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    Session = sessionmaker(bind=engine)
    session = Session()
    with session:
        user = queryAccount(session, request.username, request.password)
        if user is None:
            return LoginResponse(code=31, message="错误的账号或者密码", token=None)
        return LoginResponse(token=makeAccountJwt(user.id))


@router.post("/api/register", response_model=LoginResponse)
async def register(request: RegisterRequest):
    Session = sessionmaker(bind=engine)
    session = Session()
    with session:
        user = addUserAccount(session, request.username, request.password, request.type)
        if not user:
            return LoginResponse(code=32, message="已存在的账号", token=None)
        return LoginResponse(token=makeAccountJwt(request.username))
"""

