import sys
import os
# 将项目根目录添加到Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dense_platform_backend_main.api import router
from dense_platform_backend_main.algorithm import router_1  # Algorithm router
import uvicorn

app = FastAPI()
origins = [
    "http://localhost:5174",
    "http://localhost",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.3.30:5173",
    "http://192.168.71.86:5173",
    "http://10.18.225.115:5173",
    "http://115.236.153.174",
    "http://115.236.153.174:443",
    "*"  # Allow all origins for development
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(router_1)  # Algorithm router enabled


@app.exception_handler(Exception)
def handle_all(request: Request, ex: Exception):
    return {"code": -1, "message": ex}

if __name__ == "__main__":
    import asyncio
    import uvicorn
    
    # Python 3.6 compatible way to run uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=8889, log_level="info")
    server = uvicorn.Server(config)
    
    # For Python 3.6 compatibility
    loop = asyncio.get_event_loop()
    loop.run_until_complete(server.serve()) 
