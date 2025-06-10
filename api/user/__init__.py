from fastapi import APIRouter
<<<<<<< HEAD
from dense_platform_backend_main.api.user.login import router as user_login_router
from dense_platform_backend_main.api.user.info import router as user_info_router
from dense_platform_backend_main.api.user.report import router as report_router
=======
from .login import router as user_login_router
from .info import router as user_info_router
from .report import router as report_router
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
router = APIRouter()
router.include_router(user_login_router)
router.include_router(user_info_router)
router.include_router(report_router)

