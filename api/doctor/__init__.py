from fastapi import APIRouter
from dense_platform_backend_main.api.doctor.info import router as info_router
router = APIRouter()
router.include_router(info_router)
