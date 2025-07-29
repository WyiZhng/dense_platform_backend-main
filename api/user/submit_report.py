import typing
import uuid
import base64
import aiohttp
import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from dense_platform_backend_main.utils.response import Response
from dense_platform_backend_main.api.auth.session import get_db, SessionService
from dense_platform_backend_main.database.table import DenseReport, ReportStatus, DenseImage, Image, ImageType, ResultImage
from dense_platform_backend_main.services.database_storage_service import DatabaseStorageService
from dense_platform_backend_main.config.algorithm_config import algorithm_config

router = APIRouter()


class ReportRequest(BaseModel):
    doctor: str
    file: typing.List[int]  # 前端传递的字段名是file，不是images


class ReportResponse(Response):
    report_id: str = ""


def get_token_from_request(request: Request) -> str:
    """从请求中获取token"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    return auth_header[7:]  # Remove "Bearer " prefix


async def call_algorithm_service(image_data: bytes) -> dict:
    """调用算法服务进行图像检测"""
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


async def process_algorithm_detection(report_id: int, image_id: int):
    """处理算法检测并保存结果"""
    # 创建新的数据库会话
    from dense_platform_backend_main.api.auth.session import SessionLocal
    db = SessionLocal()
    
    try:
        print(f"🔍 开始处理算法检测: 报告ID={report_id}, 图片ID={image_id}")
        
        # 1. 从数据库加载图片数据
        image = db.query(Image).filter(Image.id == image_id).first()
        if not image:
            print(f"❌ 图片ID {image_id} 不存在")
            return
        
        print(f"📷 加载图片: ID={image_id}, 大小={len(image.data)} bytes")
        
        # 2. 调用算法服务
        algorithm_result = await call_algorithm_service(image.data)
        
        if not algorithm_result["success"]:
            print(f"❌ 算法服务调用失败: {algorithm_result['error']}")
            # 更新报告状态为失败
            report = db.query(DenseReport).filter(DenseReport.id == report_id).first()
            if report:
                report.current_status = ReportStatus.Failed
                report.diagnose = f"检测失败: {algorithm_result['error']}"
                db.commit()
            return
        
        # 3. 处理算法结果
        result_data = algorithm_result["data"]
        detections = result_data.get("detections", [])
        diagnosis = result_data.get("diagnosis", "")
        result_image_base64 = result_data.get("result_image")
        
        print(f"🎯 算法检测完成: {len(detections)} 个目标, 诊断: {diagnosis}")
        
        # 4. 保存结果图片
        result_image_id = None
        if result_image_base64:
            try:
                # 解码base64结果图片
                result_image_data = base64.b64decode(result_image_base64)
                
                # 保存到result_imgs表
                result_image = ResultImage(
                    report_id=report_id,
                    filename=f"result_{image_id}.jpg",
                    data=result_image_data,
                    format="jpg",
                    created_time=datetime.now(),
                    file_size=len(result_image_data)
                )
                db.add(result_image)
                db.flush()  # 获取ID
                result_image_id = result_image.id
                
                print(f"💾 结果图片保存成功: ID={result_image_id}")
                
                # 创建结果图片关联
                dense_result_image = DenseImage(
                    report=report_id,
                    result_image=result_image_id,
                    _type=ImageType.result
                )
                db.add(dense_result_image)
                
            except Exception as e:
                print(f"❌ 保存结果图片失败: {e}")
        
        # 5. 更新报告状态和诊断结果
        report = db.query(DenseReport).filter(DenseReport.id == report_id).first()
        if report:
            report.current_status = ReportStatus.Completed
            report.diagnose = diagnosis
            
            # 如果有检测结果，也可以保存详细的检测数据
            if detections:
                detection_summary = {
                    "detections": detections,
                    "total_count": len(detections)
                }
                # 可以将检测详情保存到diagnose字段或单独的字段
                import json
                report.diagnose = f"{diagnosis}\n\n检测详情: {json.dumps(detection_summary, ensure_ascii=False)}"
        
        # 6. 提交所有更改
        db.commit()
        
        print(f"✅ 算法检测处理完成:")
        print(f"  - 报告ID: {report_id}")
        print(f"  - 检测目标: {len(detections)}")
        print(f"  - 诊断结果: {diagnosis}")
        print(f"  - 结果图片ID: {result_image_id}")
        
    except Exception as e:
        print(f"❌ 算法检测处理失败: {e}")
        db.rollback()
        
        # 更新报告状态为失败
        try:
            report = db.query(DenseReport).filter(DenseReport.id == report_id).first()
            if report:
                report.current_status = ReportStatus.Failed
                report.diagnose = f"处理失败: {str(e)}"
                db.commit()
        except:
            pass


@router.post("/api/submitReport")
async def submitReport(
    request: ReportRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    提交报告接口 - 完整业务逻辑
    """
    try:
        print(f"🚀 NEW CODE: 收到报告提交请求 (v2.0):")
        print(f"  医生: {request.doctor}")
        print(f"  图片数量: {len(request.file)}")
        print(f"  图片IDs: {request.file}")
        
        # 1. 获取并验证用户token
        try:
            token = get_token_from_request(http_request)
            session_info = SessionService.validate_session(db, token)
            if not session_info:
                raise HTTPException(status_code=401, detail="Invalid or expired session")
            current_user_id = session_info["user_id"]
            print(f"  当前用户: {current_user_id}")
        except Exception as e:
            print(f"认证失败: {e}")
            # 如果认证失败，使用默认用户（开发阶段）
            current_user_id = "zwy"
            print(f"  使用默认用户: {current_user_id}")
            # raise HTTPException(status_code=401, detail="Authentication required")
        
        # 2. 验证医生是否存在
        from dense_platform_backend_main.database.table import User, UserType
        doctor_user = db.query(User).filter(User.id == request.doctor).first()
        if not doctor_user:
            raise HTTPException(status_code=400, detail=f"医生 {request.doctor} 不存在")
        
        # 3. 验证图片是否存在且属于当前用户（这里暂时跳过所有权验证）
        valid_images = []
        for img_id in request.file:
            image = db.query(Image).filter(Image.id == img_id).first()
            if not image:
                print(f"⚠️  图片ID {img_id} 不存在，跳过")
                continue
            valid_images.append(img_id)
            print(f"  ✅ 验证图片ID: {img_id}")
        
        if not valid_images:
            raise HTTPException(status_code=400, detail="没有有效的图片")
        
        # 4. 创建报告记录
        report = DenseReport(
            user=current_user_id,  # 使用认证的用户ID
            doctor=request.doctor,
            current_status=ReportStatus.Checking,  # 设置为检查中状态
            submitTime=datetime.now().date()
        )
        
        # 保存报告到数据库
        db.add(report)
        db.flush()  # 获取自动生成的ID，但不提交事务
        
        # 5. 创建图片与报告的关联关系
        for img_id in valid_images:
            dense_image = DenseImage(
                report=report.id,
                image=img_id,
                _type=ImageType.source  # 使用source表示原始图片
            )
            db.add(dense_image)
            print(f"  ✅ 创建图片关联: 报告ID={report.id}, 图片ID={img_id}")
        
        # 6. 提交所有事务
        db.commit()
        
        report_id = str(report.id)
        print(f"✅ 报告提交成功:")
        print(f"  - 报告ID: {report_id}")
        print(f"  - 用户: {current_user_id}")
        print(f"  - 医生: {request.doctor}")
        print(f"  - 关联图片数量: {len(valid_images)}")
        
        # 7. 异步处理算法检测
        print(f"🚀 准备启动算法检测: 报告ID={report.id}, 图片ID={valid_images[0]}")
        try:
            await process_algorithm_detection(report.id, valid_images[0])  # 处理第一张图片
            print(f"✅ 算法检测已完成")
        except Exception as e:
            print(f"⚠️  算法检测失败: {e}")
            import traceback
            traceback.print_exc()
            # 不影响报告提交的成功
        
        return ReportResponse(
            code=0,
            message="报告提交成功",
            report_id=report_id
        )
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        print(f"提交报告时发生错误: {e}")
        print(f"错误类型: {type(e)}")
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to submit report: {str(e)} (Type: {type(e).__name__})")