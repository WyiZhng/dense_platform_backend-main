from datetime import date, datetime
import typing
import asyncio
import aiohttp
import base64
import os
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from fastapi.background import BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from dense_platform_backend_main.database.table import ImageType, ReportStatus
from dense_platform_backend_main.services.database_storage_service import DatabaseStorageService
from dense_platform_backend_main.services.rbac_middleware import RequireAuthWithContext
from dense_platform_backend_main.api.auth.session import get_db
from dense_platform_backend_main.utils.response import Response

router = APIRouter()

# 导入算法服务配置
from dense_platform_backend_main.config.algorithm_config import algorithm_config

class ReportRequest(BaseModel):
    doctor: str
    images: typing.List[str]

async def call_algorithm_service(image_data: bytes) -> dict:
    """
    调用独立的算法服务进行图像检测
    
    Args:
        image_data: 图像的二进制数据
        
    Returns:
        算法服务的响应结果
    """
    try:
        # 将图像数据编码为base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # 准备请求数据
        request_data = {
            "image_data": image_base64,
            "image_format": "jpg"
        }
        
        # 调用算法服务
        async with aiohttp.ClientSession() as session:
            async with session.post(
                algorithm_config.get_predict_url(),
                json=request_data,
                timeout=aiohttp.ClientTimeout(total=algorithm_config.get_timeout())
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "data": result
                    }
                else:
                    error_text = await response.text()
                    return {
                        "success": False,
                        "error": f"算法服务返回错误: {response.status} - {error_text}"
                    }
                    
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": "算法服务调用超时"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"调用算法服务失败: {str(e)}"
        }

@router.post("/api/submitReport")
async def submit_report(
    request: ReportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = RequireAuthWithContext
):
    """
    提交报告接口 - 使用独立算法服务
    """
    
    async def process_images_async():
        """异步处理图片的核心函数，调用独立算法服务"""
        try:
            username = current_user["user_id"]
            print(f"DEBUG: 用户 {username} 提交报告，医生: {request.doctor}")
            
            if not request.images:
                print("ERROR: 没有提供图片")
                return
            
            # 获取第一张图片进行处理
            img_id = request.images[0]
            print(f"DEBUG: 处理图片ID: {img_id}")
            
            # 从数据库加载图片数据
            image_data = DatabaseStorageService.load_image(db, img_id)
            if not image_data:
                print(f"ERROR: 无法加载图片 {img_id}")
                return
            
            print(f"DEBUG: 图片数据大小: {len(image_data)} bytes")
            
            # 调用独立的算法服务
            print("DEBUG: 调用算法服务...")
            algorithm_result = await call_algorithm_service(image_data)
            
            if not algorithm_result["success"]:
                print(f"ERROR: 算法服务调用失败: {algorithm_result['error']}")
                # 保存失败的报告
                report_data = {
                    "user": username,
                    "doctor": request.doctor,
                    "submitTime": datetime.now().isoformat(),
                    "current_status": ReportStatus.Checking,
                    "images": request.images,
                    "diagnose": f"处理失败: {algorithm_result['error']}"
                }
                DatabaseStorageService.save_report(db, report_data)
                return
            
            # 获取算法结果
            result_data = algorithm_result["data"]
            print(f"DEBUG: 算法检测结果: {len(result_data.get('detections', []))} 个检测目标")
            
            # 保存结果图片到数据库
            result_image_id = None
            if result_data.get("result_image"):
                try:
                    # 解码base64结果图片
                    result_image_data = base64.b64decode(result_data["result_image"])
                    
                    # 保存结果图片到result_imgs表
                    result_image_id = DatabaseStorageService.save_result_image(
                        db, 
                        result_image_data, 
                        f"result_{img_id}.jpg",
                        "jpg"
                    )
                    print(f"DEBUG: 结果图片保存成功，ID: {result_image_id}")
                except Exception as e:
                    print(f"ERROR: 保存结果图片失败: {e}")
            
            # 获取诊断结果
            diagnosis = result_data.get("diagnosis", "未检测到龋齿")
            print(f"DEBUG: 诊断结果: {diagnosis}")
            
            # 保存报告到数据库
            report_data = {
                "user": username,
                "doctor": request.doctor,
                "submitTime": datetime.now().isoformat(),
                "current_status": ReportStatus.Checking,
                "images": request.images,
                "diagnose": diagnosis
            }
            
            report_id = DatabaseStorageService.save_report(db, report_data)
            print(f"DEBUG: 报告保存成功，ID: {report_id}")
            
            # 如果有结果图片，关联到报告
            if result_image_id and report_id:
                try:
                    # 在dense_image表中创建关联记录
                    DatabaseStorageService.save_report_image(
                        db, 
                        str(report_id), 
                        str(result_image_id), 
                        ImageType.result
                    )
                    print(f"DEBUG: 结果图片关联成功")
                except Exception as e:
                    print(f"ERROR: 关联结果图片失败: {e}")
            
            print("DEBUG: 报告处理完成")
            
        except Exception as e:
            print(f"ERROR: 处理报告时出错: {e}")
            import traceback
            traceback.print_exc()
    
    # 使用FastAPI的BackgroundTasks管理后台任务
    background_tasks.add_task(process_images_async)
    
    # 立即返回，不等待任务完成
    return Response(
        code=0,
        message="报告已提交，正在处理中",
        data={"request_id": str(uuid.uuid4())}
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