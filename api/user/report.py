from datetime import date, datetime
import typing
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from pydantic import BaseModel
from typing import List

from sqlalchemy.orm import Session
from dense_platform_backend_main.services.database_storage_service import DatabaseStorageService
from dense_platform_backend_main.database.api import *
from dense_platform_backend_main.database.table import ImageType, ReportStatus, Comment, DenseImage, User, UserType
from dense_platform_backend_main.utils.request import TokenRequest
from dense_platform_backend_main.utils.response import Response
from dense_platform_backend_main.utils import (resolveAccountJwt)
from dense_platform_backend_main.services.rbac_middleware import RequireAuthWithContext, RequirePermission, RequireAnyPermission
from dense_platform_backend_main.api.auth.session import get_db

router = APIRouter()


class UploadResponse(Response):
    fileId: str


class ReportRequest(BaseModel):
    token: str
    doctor: str
    images: typing.List[str]


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


class GetReportRequest(BaseModel):
    token: str


class Report(BaseModel):
    class Config:
        from_attributes = True
        arbitrary_types_allowed = True
    id: str
    user: str
    doctor: str
    submitTime: datetime
    current_status: ReportStatus


class ReportResponse(Response):
    reports: List[Report]


@router.post("/api/getReports")
async def getReports(
    db: Session = Depends(get_db),
    current_user = RequireAuthWithContext
):
    """获取报告列表 - 需要报告读取权限或患者报告权限"""
    username = current_user["user_id"]
    print(f"DEBUG: getReports called for user: {username}")
    
    # Get user type from database
    user = db.query(User).filter(User.id == username).first()
    if not user:
        print(f"DEBUG: User {username} not found in database")
        raise HTTPException(status_code=404, detail="User not found")
    
    user_type = 0 if user.type == UserType.Patient else 1
    print(f"DEBUG: User type: {user_type} ({'Patient' if user_type == 0 else 'Doctor'})")
    
    # 检查数据库中是否有任何报告
    all_reports = db.query(DenseReport).all()
    print(f"DEBUG: Total reports in database: {len(all_reports)}")
    for report in all_reports:
        print(f"DEBUG: Report ID: {report.id}, User: {report.user}, Doctor: {report.doctor}, Status: {report.current_status}")
    
    reports = []
    raw_reports = DatabaseStorageService.get_user_reports(db, username, user_type)
    print(f"DEBUG: Raw reports from database: {len(raw_reports)} reports found")
    print(f"DEBUG: DatabaseStorageService.get_user_reports returned: {raw_reports}")
    
    for raw_report in raw_reports:
        print(f"DEBUG: Processing raw report: {raw_report}")
    
    for report_data in raw_reports:
        try:
            # 处理时间字段，兼容不同的时间格式
            submit_time = report_data["submitTime"]
            if isinstance(submit_time, str):
                # 尝试不同的时间格式解析
                try:
                    # 尝试ISO格式
                    report_data["submitTime"] = datetime.fromisoformat(submit_time.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    try:
                        # 尝试标准格式
                        report_data["submitTime"] = datetime.strptime(submit_time, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        try:
                            # 尝试日期格式
                            report_data["submitTime"] = datetime.strptime(submit_time, '%Y-%m-%d')
                        except ValueError:
                            # 如果都失败，使用当前时间
                            print(f"Warning: Could not parse time '{submit_time}', using current time")
                            report_data["submitTime"] = datetime.now()
            elif not isinstance(submit_time, datetime):
                # 如果不是字符串也不是datetime，使用当前时间
                report_data["submitTime"] = datetime.now()
            
            print(f"Processing report: {report_data}")
            reports.append(Report(**report_data))
        except Exception as e:
            print(f"Error processing report: {e}")
            print(f"Report data: {report_data}")
            continue

    return ReportResponse(reports=reports)

class ReportImageRequest(BaseModel):
    id: str
    type: ImageType


class ReportImageResponse(Response):
    images: List[str]


@router.post("/api/report/images")
def reportImages(
    request: ReportImageRequest,
    db: Session = Depends(get_db),
    current_user = RequireAuthWithContext
):
    """获取报告图片 - 需要报告读取权限、患者报告权限或医生审查权限"""
    username = current_user["user_id"]
    print(f"DEBUG: reportImages called by user: {username}")
    print(f"DEBUG: request data: id={request.id}, type={request.type}")
    
    report = DatabaseStorageService.load_report(db, request.id)
    print(f"DEBUG: loaded report: {report is not None}")
    
    # 检查用户是否有权限访问此报告
    if report and report.get("user") != username and report.get("doctor") != username:
        # 如果用户不是报告的患者或医生，检查是否有管理权限
        if not any(perm["resource"] == "report" and perm["action"] == "manage" for perm in current_user.get("permissions", [])):
            raise HTTPException(status_code=403, detail="Not authorized to access this report")
    
    if request.type == ImageType.source:
        if not report:
            return ReportImageResponse(images=[])
        images = report.get("images", [])
        print(f"DEBUG: source images: {images}")
        return ReportImageResponse(images=images)
    else:  # ImageType.result
        if not report:
            return ReportImageResponse(images=[])
        
        # 获取结果图片 - 从新的 result_imgs 表
        result_images = DatabaseStorageService.get_report_result_images(db, request.id)
        result_image_ids = [img["id"] for img in result_images]
        print(f"DEBUG: result images: {result_image_ids}")
        return ReportImageResponse(images=result_image_ids)



class DeleteReportRequest(BaseModel):
    id: str


@router.post("/api/report/delete")
def deleteReport(
    request: DeleteReportRequest,
    db: Session = Depends(get_db),
    current_user = RequireAuthWithContext
):
    """删除报告 - 需要报告删除权限或管理权限"""
    username = current_user["user_id"]
    report = DatabaseStorageService.load_report(db, request.id)

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # 检查用户是否有权限删除此报告
    if report["user"] != username and report["doctor"] != username:
        # 如果用户不是报告的患者或医生，检查是否有管理权限
        if not any(perm["resource"] == "report" and perm["action"] == "manage" for perm in current_user.get("permissions", [])):
            raise HTTPException(status_code=403, detail="Not authorized to delete this report")

    if DatabaseStorageService.delete_report(db, request.id):
        return Response()
    else:
        raise HTTPException(status_code=500, detail="Failed to delete report")


class ReportDetailRequest(BaseModel):
    id: str


class CommentModel(BaseModel):
    class Config:
        from_attributes = True
        arbitrary_types_allowed = True
    user: str
    content: str


class ReportDetailResponse(Response):
    class Config:
        from_attributes = True
        arbitrary_types_allowed = True
    id: str
    user: str
    doctor: str
    submitTime: datetime
    current_status: ReportStatus
    diagnose: Optional[str] = None
    comments: typing.List[CommentModel] = []
    images: typing.List[str] = []  # 添加图片字段


@router.post("/api/report/detail")
def getReportDetail(
    request: ReportDetailRequest,
    db: Session = Depends(get_db),
    current_user = RequireAuthWithContext
):
    """获取报告详情 - 需要报告读取权限、患者报告权限或医生审查权限 (使用数据库存储)"""
    username = current_user["user_id"]

    report_data = DatabaseStorageService.load_report(db, request.id)
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")

    # 检查用户是否有权限访问此报告
    if report_data.get("user") != username and report_data.get("doctor") != username:
        # 如果用户不是报告的患者或医生，检查是否有管理权限
        if not any(perm["resource"] == "report" and perm["action"] == "manage" for perm in current_user.get("permissions", [])):
            raise HTTPException(status_code=403, detail="Not authorized to access this report")

    try:
        if isinstance(report_data["submitTime"], str):
            # Python 3.6兼容的日期解析
            try:
                # 简单的日期格式处理
                if 'T' in report_data["submitTime"]:
                    # ISO格式: 2024-01-01T12:00:00
                    date_part = report_data["submitTime"].split('T')[0]
                    time_part = report_data["submitTime"].split('T')[1].split('.')[0]  # 移除毫秒
                    report_data["submitTime"] = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M:%S")
                else:
                    # 简单日期格式: 2024-01-01
                    report_data["submitTime"] = datetime.strptime(report_data["submitTime"], "%Y-%m-%d")
            except ValueError:
                # 如果解析失败，使用当前时间
                report_data["submitTime"] = datetime.now()
        
        # 获取评论
        comments = []
        raw_comments = DatabaseStorageService.get_report_comments(db, request.id)
        for comment_data in raw_comments:
            comments.append(CommentModel(**comment_data))
        
        # 获取图片信息
        images_data = DatabaseStorageService.get_report_images(db, request.id)
        source_images = images_data.get("source", [])
        
        # 创建响应对象
        resp = ReportDetailResponse(**report_data)
        resp.comments = comments
        resp.images = source_images  # 设置图片列表
        return resp
    except Exception as e:
        print(f"Error in getReportDetail: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class DiagnoseRequest(BaseModel):
    id: str
    diagnose: str

@router.post('/api/report/diagnose/submit')
def submitDiagnose(
    request: DiagnoseRequest,
    db: Session = Depends(get_db),
    current_user = RequireAuthWithContext
):
    """提交诊断 - 需要医生诊断权限或报告写入权限 (使用数据库存储)"""
    username = current_user["user_id"]

    # 获取报告数据
    report_data = DatabaseStorageService.load_report(db, request.id)
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")

    # 鉴权检查医生是否匹配
    if report_data.get('doctor') != username:
        # 如果不是指定医生，检查是否有管理权限
        if not any(perm["resource"] == "report" and perm["action"] == "manage" for perm in current_user.get("permissions", [])):
            raise HTTPException(status_code=403, detail="Not authorized to diagnose this report")

    # 更新报告状态和诊断结果
    success = DatabaseStorageService.update_report_status(
        db, request.id, ReportStatus.Completed, request.diagnose
    )
    
    if success:
        return Response()
    else:
        raise HTTPException(status_code=500, detail="Failed to update report")


#
# class UploadResponse(Response):
#     fileId: str
#
#
# # @router.post("/api/uploadImage")
# # async def uploadImage(request: Request):
# #     token = request.headers.get("token", None)
# #     if token is None:
# #         return Response(code=34, message="用户未登录")
# #     username = resolveAccountJwt(token)["account"]
# #     form = await request.form()
# #     file = form.get("file")
# #     fileFormat = file.filename.split(".")[-1]
# #     id = f"{uuid.uuid1()}.{fileFormat}"
# #     with open(f"images/{id}", "wb") as f:
# #         f.write(await file.read())
# #     return UploadResponse(code=0, message="", fileId=id)
#
#
# class ReportRequest(BaseModel):
#     token: str
#     doctor: str
#     images: typing.List[int]
#
#
# @router.post("/api/submitReport")
# async def submitReport(request: ReportRequest):
#     session = sessionmaker(bind=engine)()
#     username = resolveAccountJwt(request.token)["account"]
#     with session:
#         report = DenseReport(user=username, doctor=request.doctor)
#         session.add(report)
#         session.flush()
#         for i in request.images:
#             image = DenseImage(report=report.id, image=i, _type=ImageType.source)
#             session.add(image)
#         session.flush()
#         session.commit()
#         return Response()
#
#
# class GetReportRequest(BaseModel):
#     token: str
#
#
# class Report(BaseModel):
#     model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
#     id: int
#     user: str
#     doctor: str
#     submitTime: date
#     current_status: ReportStatus
#
#
# class ReportResponse(Response):
#     reports: List[Report]
#
#
# @router.post("/api/getReports")
# async def getReports(request: GetReportRequest):
#     def mapping(x: DenseReport):
#         report = Report.model_validate(x)
#         report.doctor = x.user1.user_detail.name if x.user1.user_detail is not None else x.user1.id
#         return report
#
#     username = resolveAccountJwt(request.token)["account"]
#     session: Session = sessionmaker(bind=engine)()
#     with (session):
#         if isDoctor(session, username):
#             reports = session.query(DenseReport).filter(DenseReport.doctor == username).all()
#         else:
#             reports = get_reports(session, username)
#
#         return ReportResponse(reports=[mapping(i) for i in reports])
#
#
# class ReportImageRequest(TokenRequest):
#     id: int
#     type: ImageType
#
#
# class ReportImageResponse(Response):
#     images: List[int]
#
#
# @router.post("/api/report/images")
# def reportImages(request: ReportImageRequest):
#     username = resolveAccountJwt(request.token)["account"]
#     session = sessionmaker(bind=engine)()
#     with session:
#         results = session.query(DenseImage).join(DenseReport).filter(
#             and_(DenseImage._type == request.type, DenseReport.id == request.id)).all()
#
#         return ReportImageResponse(images=list([i.image for i in results]))
#
#
# class DeleteReportRequest(TokenRequest):
#     id: int
#
#
# @router.post("/api/report/delete")
# def deleteReport(request: DeleteReportRequest):
#     username = resolveAccountJwt(request.token)["account"]
#     session = sessionmaker(bind=engine)()
#     with session:
#         report = session.query(DenseReport).filter(DenseReport.id == request.id).first()
#         session.delete(report)
#
#         session.commit()
#         return Response()
#
#
# class ReportDetailRequest(TokenRequest):
#     id: int
#
#
# class CommentModel(BaseModel):
#     model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
#     user: str
#     content: str
#
#
# class ReportDetailResponse(Response):
#     model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
#     id: int
#     user: str
#     doctor: str
#     submitTime: date
#     current_status: ReportStatus
#     diagnose: Optional[str] = None
#     comments: typing.List[CommentModel] = []
#
#
# @router.post("/api/report/detail")
# def getReportDetail(request: ReportDetailRequest):
#     username = resolveAccountJwt(request.token)["account"]
#     session = sessionmaker(bind=engine)()
#     with session:
#         report = session.query(DenseReport).filter(DenseReport.id == request.id).first()
#         comments = session.query(Comment).filter(Comment.dense_report == report).all()
#         resp = ReportDetailResponse.model_validate(report)
#         resp.comments = list([CommentModel.model_validate(comment) for comment in comments])
#         return resp
#
#
# class DiagnoseRequest(TokenRequest):
#     id: int
#     diagnose: str
#
#
# @router.post('/api/report/diagnose/submit')
# def submitDiagnose(request: DiagnoseRequest):
#     username = resolveAccountJwt(request.token)["account"]
#     session = sessionmaker(bind=engine)()
#     with session:
#         #鉴权 id是否是该doctor所属的
#         report = session.query(DenseReport).filter(DenseReport.id == request.id).first()
#         report.diagnose = request.diagnose
#         report.current_status = ReportStatus.Completed
#         session.commit()
#         return Response()
