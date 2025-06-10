<<<<<<< HEAD
from dense_platform_backend_main.api.user import router as user_router
from dense_platform_backend_main.api.common import router as common_router
from dense_platform_backend_main.api.doctor import router as doctor_router
=======
from .user import router as user_router
from .common import router as common_router
from .doctor import  router as doctor_router
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
from fastapi import APIRouter
router = APIRouter()
router.include_router(user_router)
router.include_router(common_router)
router.include_router(doctor_router)
