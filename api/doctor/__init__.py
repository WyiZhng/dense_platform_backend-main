from fastapi import APIRouter
<<<<<<< HEAD
from dense_platform_backend_main.api.doctor.info import router as info_router
=======
from .info import router as info_router
>>>>>>> 38dbfca60a1a7c61d649edf8a9b5fdef8588640a
router = APIRouter()
router.include_router(info_router)
