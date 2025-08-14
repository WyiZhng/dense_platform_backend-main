"""\n微信小程序登录API模块\n\n提供微信小程序登录相关的API接口\n"""

from fastapi import APIRouter
from .wx_auth import router as wx_auth_router
from .upload import router as upload_router
from .reports import router as reports_router

router = APIRouter()
router.include_router(wx_auth_router)
router.include_router(upload_router)
router.include_router(reports_router)