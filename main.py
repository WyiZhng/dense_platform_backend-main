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
    # HTTP origins (向后兼容)
    "http://localhost:5174",
    "http://localhost",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.3.30:5173",
    "http://192.168.71.86:5173",
    "http://10.18.225.115:5173",
    "http://115.236.153.174",
    "http://115.236.153.174:443",
    # 服务器公网IP配置 (小程序后端部署)
    "http://49.235.37.140",
    "http://49.235.37.140:8889",
    # HTTPS origins (新增HTTPS支持)
    "https://localhost:5174",
    "https://localhost",
    "https://localhost:5173",
    "https://127.0.0.1:5173",
    "https://192.168.3.30:5173",
    "https://192.168.71.86:5173",
    "https://10.18.225.115:5173",
    "https://115.236.153.174",
    "https://115.236.153.174:443",
    # 服务器公网IP HTTPS配置 (小程序后端部署)
    "https://49.235.37.140",
    "https://49.235.37.140:8889",
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
    from pathlib import Path
    
    # 获取SSL证书文件路径
    current_dir = Path(__file__).parent
    ssl_keyfile = current_dir / "server.key"
    ssl_certfile = current_dir / "server.crt"
    
    # 检查SSL证书文件是否存在
    if ssl_keyfile.exists() and ssl_certfile.exists():
        print("🔒 使用HTTPS启动服务器...")
        print(f"   证书文件: {ssl_certfile}")
        print(f"   私钥文件: {ssl_keyfile}")
        print(f"   本地访问地址: https://127.0.0.1:8889")
        print(f"   服务器访问地址: https://49.235.37.140:8889")
        print("   ⚠️  自签名证书会显示安全警告，这是正常的")
        
        # 使用HTTPS配置启动服务器 (服务器部署配置)
        config = uvicorn.Config(
            app, 
            host="0.0.0.0",  # 允许外部访问，适用于服务器部署
            port=8889, 
            log_level="info",
            ssl_keyfile=str(ssl_keyfile),  # SSL私钥文件路径
            ssl_certfile=str(ssl_certfile) # SSL证书文件路径
        )
    else:
        print("⚠️  未找到SSL证书文件，使用HTTP启动服务器...")
        print("   如需使用HTTPS，请先运行: python generate_ssl_cert.py")
        print(f"   本地访问地址: http://127.0.0.1:8889")
        print(f"   服务器访问地址: http://49.235.37.140:8889")
        
        # 使用HTTP配置启动服务器（服务器部署配置）
        config = uvicorn.Config(
            app, 
            host="0.0.0.0",  # 允许外部访问，适用于服务器部署
            port=8889, 
            log_level="info"
        )
    
    server = uvicorn.Server(config)
    
    # For Python 3.6 compatibility
    loop = asyncio.get_event_loop()
    loop.run_until_complete(server.serve())
