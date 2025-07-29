from fastapi import APIRouter
from dense_platform_backend_main.api.doctor.info import router as info_router
from dense_platform_backend_main.api.doctor.report_management_backup import router as report_management_router
from dense_platform_backend_main.api.doctor.comment_system import router as comment_system_router

# Create a router
router = APIRouter()

# Include the routers
router.include_router(info_router)
router.include_router(report_management_router)
router.include_router(comment_system_router)
