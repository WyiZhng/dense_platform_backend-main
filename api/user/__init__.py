from fastapi import APIRouter
from .login import router as user_login_router
from .info import router as user_info_router
from .report import router as report_router
router = APIRouter()
router.include_router(user_login_router)
router.include_router(user_info_router)
router.include_router(report_router)

