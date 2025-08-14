import base64
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from dense_platform_backend_main.api.auth.session import get_db
from dense_platform_backend_main.database.table import DenseReport, DenseImage, Image, ResultImage, ImageType, User
from dense_platform_backend_main.services.database_storage_service import DatabaseStorageService
from dense_platform_backend_main.utils.response import Response

router = APIRouter()

class ReportListItem(BaseModel):
    """检测报告列表项模型"""
    report_id: str
    submit_time: str  # 格式化后的时间字符串
    diagnose_status: str  # "normal" 或 "abnormal"
    diagnose_text: str  # 诊断结果文本

class ReportListResponse(BaseModel):
    """检测报告列表响应模型"""
    success: bool
    code: int = 0
    message: str = ""
    data: Optional[List[ReportListItem]] = None

class ReportDetailResponse(BaseModel):
    """检测报告详情响应模型"""
    success: bool
    code: int = 0
    message: str = ""
    data: Optional[dict] = None

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

def format_diagnose_status(diagnose_text: str) -> str:
    """
    根据诊断结果文本判断状态
    
    Args:
        diagnose_text: 诊断结果文本
        
    Returns:
        "normal" 表示未明显异常（绿色），"abnormal" 表示发现疑似龋齿（红色）
    """
    if not diagnose_text:
        return "normal"
    
    # 根据算法服务返回的具体诊断文本进行判断
    # 算法服务返回的可能结果：
    # 1. "未检测到龋齿" - 正常状态
    # 2. "您的牙齿非常健康，请继续保持！" - 正常状态  
    # 3. "您有X颗轻度/中度/重度龋齿..." - 异常状态
    
    # 明确的正常状态关键词（优先检查）
    normal_keywords = [
        "未检测到龋齿",
        "牙齿非常健康", 
        "请继续保持",
        "未发现",
        "正常",
        "健康"
    ]
    
    # 检查是否为正常状态
    for keyword in normal_keywords:
        if keyword in diagnose_text:
            return "normal"
    
    # 明确的异常状态关键词
    abnormal_keywords = [
        "轻度龋齿",
        "中度龋齿", 
        "重度龋齿",
        "龋齿",
        "蛀牙",
        "请立即就医",
        "建议尽快就医",
        "请及时治疗"
    ]
    
    # 检查是否为异常状态
    for keyword in abnormal_keywords:
        if keyword in diagnose_text:
            return "abnormal"
    
    # 如果都没有匹配到，默认返回正常状态
    return "normal"

def format_diagnose_display_text(diagnose_text: str, status: str) -> str:
    """
    格式化诊断结果显示文本
    
    Args:
        diagnose_text: 原始诊断结果文本
        status: 诊断状态
        
    Returns:
        格式化后的显示文本
    """
    if status == "normal":
        return "未见明显异常"
    else:
        return "发现疑似龋齿"

@router.get("/api/new/reports/list")
async def get_user_reports(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    获取用户检测报告列表
    
    返回用户最近的检测报告，包括时间和诊断结果
    
    Args:
        request: FastAPI请求对象，用于获取用户信息
        db: 数据库会话
        
    Returns:
        检测报告列表响应
    """
    try:
        # 从请求头获取用户信息
        try:
            user_info = get_user_from_headers(request)
        except HTTPException as e:
            return ReportListResponse(
                success=False,
                code=e.status_code,
                message=e.detail
            )
        
        user_openid = user_info["openid"]
        print(f"[DEBUG] 正在获取用户报告列表，OpenID: {user_openid}")
        
        # 根据OpenID查询用户记录
        user_record = db.query(User).filter(User.openid == user_openid).first()
        if not user_record:
            print(f"[ERROR] 未找到OpenID为 {user_openid} 的用户记录")
            return ReportListResponse(
                success=False,
                code=404,
                message="用户不存在"
            )
        
        print(f"[DEBUG] 找到用户记录: ID={user_record.id}, OpenID={user_record.openid}")
        
        # 查询用户的检测报告，按提交时间倒序排列
        reports = db.query(DenseReport).filter(
            DenseReport.user == user_record.id
        ).order_by(desc(DenseReport.submitTime)).all()
        
        print(f"[DEBUG] 查询到 {len(reports)} 条报告记录")
        for i, report in enumerate(reports):
            print(f"[DEBUG] 报告 {i+1}: ID={report.id}, 用户ID={report.user}, 医生={report.doctor}, 提交时间={report.submitTime}, 诊断={report.diagnose[:50] if report.diagnose else 'None'}...")
        
        if not reports:
            return ReportListResponse(
                success=True,
                code=0,
                message="暂无检测记录",
                data=[]
            )
        
        # 构建返回数据
        report_list = []
        for report in reports:
            # 格式化时间 - 修改为显示日期和时间，精确到小时分钟
            if report.submitTime:
                formatted_time = report.submitTime.strftime("%Y年%m月%d日 %H:%M")
            else:
                formatted_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")
            
            # 判断诊断状态
            diagnose_status = format_diagnose_status(report.diagnose or "")
            
            # 格式化显示文本
            display_text = format_diagnose_display_text(report.diagnose or "", diagnose_status)
            
            report_item = ReportListItem(
                report_id=str(report.id),
                submit_time=formatted_time,
                diagnose_status=diagnose_status,
                diagnose_text=display_text
            )
            report_list.append(report_item)
        
        # 返回检测报告列表
        
        return ReportListResponse(
            success=True,
            code=0,
            message="获取成功",
            data=report_list
        )
        
    except Exception as e:
        print(f"ERROR: 获取报告列表失败: {e}")
        import traceback
        traceback.print_exc()
        
        return ReportListResponse(
            success=False,
            code=500,
            message=f"获取检测报告列表失败: {str(e)}"
        )

@router.get("/api/new/reports/detail/{report_id}")
async def get_report_detail(
    report_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    获取检测报告详情
    
    返回指定报告的详细信息，包括检测后的图片和诊断结果
    
    Args:
        report_id: 报告ID
        request: FastAPI请求对象，用于获取用户信息
        db: 数据库会话
        
    Returns:
        检测报告详情响应
    """
    try:
        # 从请求头获取用户信息
        try:
            user_info = get_user_from_headers(request)
        except HTTPException as e:
            return ReportDetailResponse(
                success=False,
                code=e.status_code,
                message=e.detail
            )
        
        user_openid = user_info["openid"]
        print(f"[DEBUG] 正在获取报告详情，报告ID: {report_id}, 用户OpenID: {user_openid}")
        
        # 根据OpenID查询用户记录
        user_record = db.query(User).filter(User.openid == user_openid).first()
        if not user_record:
            print(f"[ERROR] 未找到OpenID为 {user_openid} 的用户记录")
            return ReportDetailResponse(
                success=False,
                code=404,
                message="用户不存在"
            )
        
        print(f"[DEBUG] 找到用户记录: ID={user_record.id}, OpenID={user_record.openid}")
        
        # 查询报告信息，确保是当前用户的报告
        report = db.query(DenseReport).filter(
            DenseReport.id == int(report_id),
            DenseReport.user == user_record.id
        ).first()
        
        print(f"[DEBUG] 查询报告结果: {'找到报告' if report else '未找到报告'}")
        if report:
            print(f"[DEBUG] 报告详情: ID={report.id}, 用户ID={report.user}, 医生={report.doctor}, 诊断={report.diagnose[:50] if report.diagnose else 'None'}...")
        
        if not report:
            return ReportDetailResponse(
                success=False,
                code=404,
                message="报告不存在或无权限访问"
            )
        
        # 查询关联的图片信息
        dense_images = db.query(DenseImage).filter(
            DenseImage.report == int(report_id)
        ).all()
        
        # 获取原始图片和结果图片
        original_image_base64 = None
        result_image_base64 = None
        
        for dense_image in dense_images:
            if dense_image._type == ImageType.source and dense_image.image:
                # 获取原始图片
                original_image_data = DatabaseStorageService.load_image(db, str(dense_image.image))
                if original_image_data:
                    original_image_base64 = base64.b64encode(original_image_data).decode('utf-8')
            
            elif dense_image._type == ImageType.result and dense_image.result_image:
                # 获取结果图片
                result_image_data = DatabaseStorageService.load_result_image(db, str(dense_image.result_image))
                if result_image_data:
                    result_image_base64 = base64.b64encode(result_image_data).decode('utf-8')
        
        # 构建返回数据
        detail_data = {
            "report_id": str(report.id),
            "submit_time": report.submitTime.strftime("%Y年%m月%d日") if report.submitTime else "",
            "diagnose": report.diagnose or "暂无诊断结果",
            "status": report.current_status.name if report.current_status else "Unknown",
            "original_image": original_image_base64,  # 原始上传图片的base64
            "result_image": result_image_base64      # 检测结果图片的base64
        }
        
        return ReportDetailResponse(
            success=True,
            code=0,
            message="获取成功",
            data=detail_data
        )
        
    except Exception as e:
        print(f"ERROR: 获取报告详情失败: {e}")
        import traceback
        traceback.print_exc()
        
        return ReportDetailResponse(
            success=False,
            code=500,
            message=f"获取检测报告详情失败: {str(e)}"
        )