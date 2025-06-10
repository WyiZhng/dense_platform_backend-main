from datetime import date
import typing
import asyncio
from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel, ConfigDict
from dense_platform_backend_main.database.api import teechLevel,teechLevel2
from dense_platform_backend_main.database.table import ImageType, ReportStatus
from dense_platform_backend_main.database.storage import (
    save_report, load_report, get_user_reports,
    save_comment, get_report_comments,
    save_report_image, get_report_images,
    delete_report, save_report_com
)
from dense_platform_backend_main.utils.request import TokenRequest
from dense_platform_backend_main.utils.response import Response
from dense_platform_backend_main.utils import resolveAccountJwt
from fastapi.responses import FileResponse
import cv2
import numpy as np
from ultralytics import YOLO
import base64
import uuid
import os
from pathlib import Path
from collections import Counter


router = APIRouter()

yolo_model = YOLO("best.pt")  # 路径可根据实际情况调整


class ReportRequest(BaseModel):
    token: str
    doctor: str
    images: typing.List[str]

# @router.post("/algorithm/predict")
@router.post("/api/submitReport")
async def predict_image(request: ReportRequest):
    async def process_images():
        img_path = f"storage/images/{request.images[0]}.jpg"  # 假设图片存储路径
        file_path =  Path("storage/images") / f"{request.images[0]}.jpg"

        # 读取图片
        with open(img_path, 'rb') as img_file:
            contents = img_file.read()
        image_np = np.asarray(bytearray(contents), dtype=np.uint8)
        img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)

        try:
            # YOLOv8推理
            results = yolo_model(file_path)
            result = results[0]

            # 处理检测结果
            detections = []
            if len(result.boxes) > 0:
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

            # 保存带检测框的图片
            result_img = result.plot()
            image_id = str(uuid.uuid4())
            result_dir = "storage/reports/Result_image"
            os.makedirs(result_dir, exist_ok=True)
            result_img_path = f"{result_dir}/{image_id}.jpg"
            cv2.imwrite(result_img_path, result_img)

            # 组装data_json
            data_json = {
                "detections": detections,
                "result_image": f"{image_id}.jpg"
            }

        except Exception as e:
            print(e)

        #diag = teechLevel(str(data_json))
        classes = [item["class"] for item in detections]
        diag = teechLevel2(classes)
        #class_counts = Counter(item["class"] for item in detections)
        

        username = resolveAccountJwt(request.token)["account"]
        report_data = {
            "user": username,
            "doctor": request.doctor,
            "submitTime": str(date.today()),
            "current_status": ReportStatus.Completed,
            "images": request.images,
            "diagnose":diag,
            "Result_img": [image_id]
        }
        save_report_com(report_data)
        delete_report(report_id)

    # 启动异步任务
    asyncio.create_task(process_images())

    username = resolveAccountJwt(request.token)["account"]
    report_data = {
        "user": username,
        "doctor": request.doctor,
        "submitTime": str(date.today()),
        "current_status": ReportStatus.Checking,
        "images": request.images,
        "diagnose": "",
        "Result_img": ""
    }
    report_id = save_report(report_data)

    return Response()


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