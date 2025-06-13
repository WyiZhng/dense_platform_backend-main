from datetime import date
import typing
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException
from fastapi.background import BackgroundTasks
from pydantic import BaseModel
from dense_platform_backend_main.database.api import teechLevel, teechLevel2
from dense_platform_backend_main.database.table import ImageType, ReportStatus
from dense_platform_backend_main.database.storage import save_report_com
from dense_platform_backend_main.utils.request import TokenRequest
from dense_platform_backend_main.utils.response import Response
from dense_platform_backend_main.utils import resolveAccountJwt
import cv2
import numpy as np
from ultralytics import YOLO
import os
from pathlib import Path
import uuid

router = APIRouter()

# 初始化全局线程池，控制并发量
executor = ThreadPoolExecutor(max_workers=4)

# 加载YOLO模型（应用启动时加载，避免重复加载）
yolo_model = None

async def load_yolo_model():
    global yolo_model
    if yolo_model is None:
        yolo_model = YOLO("best.pt")
    return yolo_model

class ReportRequest(BaseModel):
    token: str
    doctor: str
    images: typing.List[str]

@router.post("/api/submitReport")
async def predict_image(request: ReportRequest, background_tasks: BackgroundTasks):
    """提交报告接口，优化异步处理避免阻塞"""
    
    async def process_images_async():
        """异步处理图片的核心函数，使用await处理所有阻塞操作"""
        try:
            # 确保模型已加载
            model = await load_yolo_model()
            
            img_name = request.images[0]
            img_path = f"storage/images/{img_name}.jpg"
            file_path = Path("storage/images") / f"{img_name}.jpg"
            
            # 异步读取文件（使用aiofiles）
            import aiofiles
            async with aiofiles.open(img_path, 'rb') as img_file:
                contents = await img_file.read()
            
            # 在线程池中执行numpy和cv2的同步操作
            image_np = await asyncio.get_event_loop().run_in_executor(
                executor, 
                lambda: np.asarray(bytearray(contents), dtype=np.uint8)
            )
            img = await asyncio.get_event_loop().run_in_executor(
                executor, 
                lambda: cv2.imdecode(image_np, cv2.IMREAD_COLOR)
            )
            
            # 在线程池中执行YOLOv8推理（计算密集型操作）
            results = await asyncio.get_event_loop().run_in_executor(
                executor, 
                lambda: model(file_path)
            )
            result = results[0] if results else None
            
            # 处理检测结果（同步逻辑，因逻辑简单可直接执行）
            detections = []
            if result and len(result.boxes) > 0:
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    confidence = float(box.conf[0])
                    class_id = int(box.cls[0])
                    class_name = result.names[class_id]
                    detections.append({
                        "class": class_name,
                        "confidence": round(confidence, 3),
                        "box": {
                            "x1": round(x1, 2),
                            "y1": round(y1, 2),
                            "x2": round(x2, 2),
                            "y2": round(y2, 2)
                        }
                    })
            
            # 保存带检测框的图片（线程池执行）
            if result:
                result_img = await asyncio.get_event_loop().run_in_executor(
                    executor, 
                    lambda: result.plot()
                )
                image_id = str(uuid.uuid4())
                result_dir = "storage/reports/Result_image"
                os.makedirs(result_dir, exist_ok=True)
                result_img_path = f"{result_dir}/{image_id}.jpg"
                
                await asyncio.get_event_loop().run_in_executor(
                    executor, 
                    lambda: cv2.imwrite(result_img_path, result_img)
                )
            else:
                image_id = None
            
            # 处理诊断逻辑
            classes = [item["class"] for item in detections]
            diag = teechLevel2(classes) if classes else "未检测到目标"
            
            # 保存报告（线程池执行）
            username = resolveAccountJwt(request.token)["account"]
            report_data = {
                "user": username,
                "doctor": request.doctor,
                "submitTime": str(date.today()),
                "current_status": ReportStatus.Completed,
                "images": request.images,
                "diagnose": diag,
                "Result_img": [image_id] if image_id else []
            }
            
            await asyncio.get_event_loop().run_in_executor(
                executor, 
                lambda: save_report_com(report_data)
            )
            
        except Exception as e:
            print(f"处理报告时出错: {e}")
            # 这里可以添加错误日志记录
    
    # 使用FastAPI的BackgroundTasks管理后台任务
    background_tasks.add_task(process_images_async)
    
    # 立即返回，不等待任务完成
    return Response(
        status_code=202,
        content={"message": "报告已提交，正在处理中", "request_id": str(uuid.uuid4())}
    )
# @router.post("/api/submitReport")
# async def submitReport(request: ReportRequest):
#     username = resolveAccountJwt(request.token)["account"]
#
#     report_data = {
#         "user": username,
#         "doctor": request.doctor,
#         "submitTime": str(date.today()),
#         "current_status": ReportStatus.Checking,
#         "images": request.images,
#         "diagnose": None
#     }
#
#     save_report(report_data)
#     return Response()