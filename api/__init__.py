from dense_platform_backend_main.api.user import router as user_router
from dense_platform_backend_main.api.common import router as common_router
from dense_platform_backend_main.api.doctor import router as doctor_router
from dense_platform_backend_main.api.auth import router as auth_router
from dense_platform_backend_main.api.admin.rbac import router as admin_rbac_router
from dense_platform_backend_main.api.admin.user_management import router as admin_user_router
from dense_platform_backend_main.api.admin.dashboard import router as admin_dashboard_router
from dense_platform_backend_main.api.admin.system_config import router as admin_config_router
from dense_platform_backend_main.api.admin.audit import router as admin_audit_router
from dense_platform_backend_main.api.new import router as wx_auth_router  # 微信登录API路由
from fastapi import APIRouter
router = APIRouter()
router.include_router(user_router)
router.include_router(common_router)
router.include_router(doctor_router)
router.include_router(auth_router)
router.include_router(admin_rbac_router)
router.include_router(admin_user_router)
router.include_router(admin_dashboard_router)
router.include_router(admin_config_router)
router.include_router(admin_audit_router)
router.include_router(wx_auth_router)  # 添加微信登录路由
