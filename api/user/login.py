from typing import Any, Optional

from fastapi import APIRouter
from dense_platform_backend_main.database.storage import load_accounts, save_accounts
from dense_platform_backend_main.database.api import *
from dense_platform_backend_main.utils.response import Response
from pydantic import BaseModel

from dense_platform_backend_main.utils import makeAccountJwt

router = APIRouter()


class LoginRequest(BaseModel):  # 登录请求
    username: str
    password: str


class RegisterRequest(BaseModel):  # 注册请求
    username: str
    password: str
    type: UserType


class LoginResponse(Response):  # 登录响应
    def __init__(self, /, **data: Any):
        super().__init__(**data)

    token: Optional[str] = None  # 登录成功时，这个字段会包含生成的 JWT 令牌；否则为 None。


@router.post("/api/login", response_model=LoginResponse)
async def login(request: LoginRequest):  # 登录
    accounts = load_accounts()
    user = accounts.get(request.username)

    if user is None or user['password'] != request.password:
        return LoginResponse(code=31, message="错误的账号或者密码", token=None)

    return LoginResponse(token=makeAccountJwt(request.username))


@router.post("/api/register", response_model=LoginResponse)
async def register(request: RegisterRequest):
    accounts = load_accounts()

    if request.username in accounts:
        return LoginResponse(code=32, message="已存在的账号，如果忘记密码请联系管理员，或者更换账号ID重新注册", token=None)

    accounts[request.username] = {
        'password': request.password,
        'type': request.type
    }
    save_accounts(accounts)

    return LoginResponse(token=makeAccountJwt(request.username))


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
    def __init__(self, /, **data: Any):
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

