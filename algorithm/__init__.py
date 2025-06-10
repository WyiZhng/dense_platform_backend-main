from fastapi import APIRouter
from dense_platform_backend_main.algorithm.predict_router import router as algorithm_router
router_1 = APIRouter()
router_1.include_router(algorithm_router)
