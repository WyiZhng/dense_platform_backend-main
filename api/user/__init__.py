from fastapi import APIRouter
from dense_platform_backend_main.api.user.login import router as user_login_router
from dense_platform_backend_main.api.user.info import router as user_info_router
from dense_platform_backend_main.api.user.report import router as report_router
router = APIRouter()
router.include_router(user_login_router)
router.include_router(user_info_router)
router.include_router(report_router)

