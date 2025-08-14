import asyncio
import aiohttp
import base64
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from dense_platform_backend_main.api.auth.session import get_db
from dense_platform_backend_main.database.table import ImageType, ReportStatus, User
from dense_platform_backend_main.services.database_storage_service import DatabaseStorageService
from dense_platform_backend_main.utils.response import Response
from dense_platform_backend_main.config.algorithm_config import algorithm_config

router = APIRouter()

class UploadResponse(BaseModel):
    """图片上传响应模型"""
    success: bool
    code: int = 0
    message: str = ""
    data: Optional[dict] = None

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
        
        # 调用算法服务进行图像检测
        
        # 调用算法服务
        async with aiohttp.ClientSession() as session:
            async with session.post(
                algorithm_config.get_predict_url(),
                json=request_data,
                timeout=aiohttp.ClientTimeout(total=algorithm_config.get_timeout())
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    # 算法服务调用成功
                    return {
                        "success": True,
                        "data": result
                    }
                else:
                    error_text = await response.text()
                    print(f"ERROR: 算法服务错误: {response.status}")
                    return {
                        "success": False,
                        "error": f"算法服务返回错误: {response.status} - {error_text}"
                    }
                    
    except asyncio.TimeoutError:
        print("ERROR: 算法服务超时")
        return {
            "success": False,
            "error": "算法服务调用超时"
        }
    except Exception as e:
        print(f"ERROR: 算法服务失败: {str(e)}")
        return {
            "success": False,
            "error": f"调用算法服务失败: {str(e)}"
        }

def get_user_from_headers(request: Request) -> dict:
    """
    从请求头获取用户信息
    
    Args:
        request: FastAPI请求对象
        
    Returns:
        包含用户信息的字典
    """
    user_openid = request.headers.get("User-Openid")
    
    if not user_openid:
        raise HTTPException(status_code=401, detail="缺少用户OpenID")
    
    return {
        "openid": user_openid
    }

async def process_image_async(image_id: str, image_data: bytes, user_info: dict, db: Session):
    """
    异步处理图片：调用算法服务并保存结果
    
    Args:
        image_id: 图片ID
        image_data: 图片二进制数据
        user_info: 用户信息
        db: 数据库会话
    """
    try:
        # 开始处理图片 - 添加调试信息
        print(f"[DEBUG] 开始异步处理图片 - 位置: process_image_async函数")
        print(f"[DEBUG] 图片ID: {image_id}")
        print(f"[DEBUG] 用户信息: {user_info}")
        print(f"[DEBUG] 图片数据大小: {len(image_data)} bytes")
        
        # 调用算法服务
        print(f"[DEBUG] 正在调用算法服务...")
        algorithm_result = await call_algorithm_service(image_data)
        
        if not algorithm_result["success"]:
            # 详细的算法服务调用失败调试信息
            print(f"[DEBUG] 算法服务调用失败 - 位置: process_image_async函数")
            print(f"[DEBUG] 图片ID: {image_id}")
            print(f"[DEBUG] 用户OpenID: {user_info.get('openid', '未知')}")
            print(f"[DEBUG] 图片数据大小: {len(image_data)} bytes")
            print(f"[DEBUG] 算法错误信息: {algorithm_result.get('error', '未知错误')}")
            print(f"[DEBUG] 完整算法响应: {algorithm_result}")
            # 可以在这里记录失败日志或发送通知
            return
        
        # 获取算法结果
        result_data = algorithm_result["data"]
        print(f"[DEBUG] 算法服务调用成功")
        # 获取算法检测结果
        
        # 获取诊断结果
        diagnosis = result_data.get("diagnosis", "未检测到龋齿")
        print(f"[DEBUG] 诊断结果: {diagnosis}")
        
        # 根据OpenID查询用户ID
        user_openid = user_info["openid"]
        user_record = db.query(User).filter(User.openid == user_openid).first()
        if not user_record:
            print(f"[ERROR] 未找到OpenID为 {user_openid} 的用户记录")
            return
        
        print(f"[DEBUG] 找到用户记录: ID={user_record.id}, OpenID={user_record.openid}")
        
        # 创建报告数据
        report_data = {
            "user": user_record.id,  # 使用数据库中的用户ID
            "doctor": "AI智能诊断",  # 默认医生名称
            "submitTime": datetime.now().isoformat(),
            "current_status": ReportStatus.Completed,  # 直接标记为完成
            "images": [image_id],
            "diagnose": diagnosis
        }
        
        # 保存报告到数据库
        print(f"[DEBUG] 正在保存报告到数据库...")
        print(f"[DEBUG] 报告数据: {report_data}")
        report_id = DatabaseStorageService.save_report(db, report_data)
        print(f"[DEBUG] 报告保存成功，报告ID: {report_id}")
        
        # 检查报告ID是否有效
        if not report_id:
            print(f"[DEBUG] 报告保存失败，无法继续处理结果图片")
            return
        
        # 保存结果图片到数据库（如果有）
        result_image_id = None
        if result_data.get("result_image"):
            try:
                # 解码base64结果图片
                result_image_data = base64.b64decode(result_data["result_image"])
                print(f"[DEBUG] 正在保存结果图片，报告ID: {report_id}")
                
                # 保存结果图片到result_imgs表，现在有了有效的report_id
                result_image_id = DatabaseStorageService.save_result_image(
                    db, 
                    str(report_id),  # 使用刚刚保存的报告ID
                    result_image_data, 
                    f"result_{image_id}.jpg",
                    "jpg"
                )
                print(f"[DEBUG] 结果图片保存成功，结果图片ID: {result_image_id}")
            except Exception as e:
                # 详细的错误调试信息，帮助快速定位问题
                print(f"[DEBUG] 保存结果图片失败 - 位置: process_image_async函数")
                print(f"[DEBUG] 图片ID: {image_id}")
                print(f"[DEBUG] 报告ID: {report_id}")
                print(f"[DEBUG] 结果图片文件名: result_{image_id}.jpg")
                print(f"[DEBUG] 错误类型: {type(e).__name__}")
                print(f"[DEBUG] 错误详情: {str(e)}")
                print(f"[DEBUG] 结果图片数据大小: {len(result_image_data) if 'result_image_data' in locals() else '未知'} bytes")
                # 记录异常以便后续分析
                import traceback
                print(f"[DEBUG] 完整错误堆栈:\n{traceback.format_exc()}")
        
        # 如果有结果图片ID，说明结果图片已经保存成功并且已经关联到报告
        if result_image_id:
            print(f"[DEBUG] 结果图片处理完成，图片ID: {result_image_id}")
        else:
            print(f"[DEBUG] 没有结果图片或结果图片保存失败")
        
        # 图片处理完成
        print(f"[DEBUG] 图片异步处理完成 - 位置: process_image_async函数")
        print(f"[DEBUG] 最终状态: 成功")
        print(f"[DEBUG] 图片ID: {image_id}")
        print(f"[DEBUG] 报告ID: {report_id}")
        print(f"[DEBUG] 结果图片ID: {result_image_id if result_image_id else '无'}")
        print(f"[DEBUG] 诊断结果: {diagnosis}")
        
    except Exception as e:
        # 整个函数的异常处理调试信息
        print(f"[DEBUG] process_image_async函数发生未捕获异常")
        print(f"[DEBUG] 图片ID: {image_id}")
        print(f"[DEBUG] 用户信息: {user_info}")
        print(f"[DEBUG] 异常类型: {type(e).__name__}")
        print(f"[DEBUG] 异常详情: {str(e)}")
        # 记录完整的异常堆栈
        import traceback
        print(f"[DEBUG] 完整异常堆栈:\n{traceback.format_exc()}")
        # 重新抛出异常以便上层处理
        raise

@router.post("/api/new/uploadImage")
async def upload_image(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    图片上传接口
    
    接收用户上传的牙齿图片，保存到数据库，并异步调用算法服务进行分析
    
    Args:
        request: FastAPI请求对象，用于获取请求头信息
        background_tasks: 后台任务管理器
        file: 上传的图片文件
        db: 数据库会话
        
    Returns:
        上传结果响应
    """
    try:
        # 验证文件类型
        if not file.content_type or not file.content_type.startswith('image/'):
            return UploadResponse(
                success=False,
                code=400,
                message="请上传有效的图片文件"
            )
        
        # 从请求头获取用户信息
        try:
            user_info = get_user_from_headers(request)
        except HTTPException as e:
            return UploadResponse(
                success=False,
                code=e.status_code,
                message=e.detail
            )
        
        # 读取文件内容
        file_content = await file.read()
        
        # 验证文件大小（限制为10MB）
        if len(file_content) > 10 * 1024 * 1024:
            return UploadResponse(
                success=False,
                code=400,
                message="文件大小不能超过10MB"
            )
        
        # 用户上传图片
        
        # 保存图片到数据库
        try:
            # 生成文件名
            file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
            filename = f"{uuid.uuid4()}.{file_extension}"
            
            # 保存到数据库
            image_id = DatabaseStorageService.save_image(
                db,
                file_content,
                filename,
                file_extension
            )
            
            # 图片保存成功
            
        except Exception as e:
            print(f"ERROR: 保存图片失败: {e}")
            return UploadResponse(
                success=False,
                code=500,
                message=f"保存图片失败: {str(e)}"
            )
        
        # 添加后台任务：异步调用算法服务
        background_tasks.add_task(
            process_image_async,
            image_id,
            file_content,
            user_info,
            db
        )
        
        # 立即返回上传成功响应
        return UploadResponse(
            success=True,
            code=0,
            message="图片上传成功，正在进行AI分析",
            data={
                "image_id": image_id,
                "filename": filename,
                "user": user_info["openid"]
            }
        )
        
    except Exception as e:
        print(f"ERROR: 上传失败: {e}")
        import traceback
        traceback.print_exc()
        
        return UploadResponse(
            success=False,
            code=500,
            message=f"上传失败: {str(e)}"
        )