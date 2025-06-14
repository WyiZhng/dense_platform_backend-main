from datetime import date
import typing
from typing import Optional

from fastapi import APIRouter, File, UploadFile,HTTPException
from pydantic import BaseModel, ConfigDict

from sqlalchemy.orm import Session
from dense_platform_backend_main.database.storage import (
    save_report, load_report, get_user_reports,
    save_comment, get_report_comments,
    save_report_image, get_report_images,delete_report_nopicture,
    delete_report
)
from dense_platform_backend_main.database.api import *
from dense_platform_backend_main.database.table import ImageType, ReportStatus, Comment, DenseImage
from dense_platform_backend_main.utils.request import TokenRequest
from dense_platform_backend_main.utils.response import Response
from dense_platform_backend_main.utils import (resolveAccountJwt)
from pydantic import ConfigDict

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
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
    id: str
    user: str
    doctor: str
    submitTime: date
    current_status: ReportStatus


class ReportResponse(Response):
    reports: List[Report]


@router.post("/api/getReports")
async def getReports(request: GetReportRequest):
    username = resolveAccountJwt(request.token)["account"]
    accounts = load_accounts()
    user_data = accounts.get(username)
    type = user_data['type']
    reports = []
    raw_reports = get_user_reports(username,type)
    for report_data in raw_reports:
        try:
            report_data["submitTime"] = date.fromisoformat(report_data["submitTime"])
            reports.append(Report(**report_data))
        except Exception as e:
            print(f"Error processing report: {e}")
            continue

    return ReportResponse(reports=reports)

class ReportImageRequest(TokenRequest):
    id: str
    type: ImageType


class ReportImageResponse(Response):
    images: List[str]


@router.post("/api/report/images")
def reportImages(request: ReportImageRequest):
    username = resolveAccountJwt(request.token)["account"]
    report = load_report(request.id)
    if request.type == ImageType.source:
        if not report:
            return ReportImageResponse(images=[])
        return ReportImageResponse(images=report.get("images", []))
    else :
        return ReportImageResponse(images=report.get("Result_img", []))



class DeleteReportRequest(TokenRequest):
    id: str


@router.post("/api/report/delete")
def deleteReport(request: DeleteReportRequest):
    username = resolveAccountJwt(request.token)["account"]
    report = load_report(request.id)

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if report["user"] == username or report["doctor"] == username:
        if delete_report(request.id):
            return Response()
        else:
            raise HTTPException(status_code=500, detail="Failed to delete report")
    raise HTTPException(status_code=403, detail="Not authorized to delete this report")


class ReportDetailRequest(TokenRequest):
    id: str


class CommentModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
    user: str
    content: str


class ReportDetailResponse(Response):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
    id: str
    user: str
    doctor: str
    submitTime: date
    current_status: ReportStatus
    diagnose: Optional[str] = None
    comments: typing.List[CommentModel] = []


@router.post("/api/report/detail")
def getReportDetail(request: ReportDetailRequest):
    username = resolveAccountJwt(request.token)["account"]

    report_data = load_report(request.id)
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")

    try:
        report_data["submitTime"] = date.fromisoformat(report_data["submitTime"])

        comments = []
        raw_comments = get_report_comments(request.id)
        for comment_data in raw_comments:
            comments.append(CommentModel(**comment_data))
        resp = ReportDetailResponse(**report_data)
        resp.comments = comments
        return resp
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DiagnoseRequest(TokenRequest):
    id: str
    diagnose: str

@router.post('/api/report/diagnose/submit')
def submitDiagnose(request: DiagnoseRequest):
    username = resolveAccountJwt(request.token)["account"]

    # 获取报告数据
    report_data = load_report(request.id)
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")

    # 鉴权检查医生是否匹配
    if report_data.get('doctor') != username:
        raise HTTPException(status_code=403, detail="Not authorized to diagnose this report")

    # 更新报告状态和诊断结果
    report_data['diagnose'] = request.diagnose
    report_data['current_status'] = ReportStatus.Completed

    # 保存更新后的报告
    save_report(report_data)
    delete_report_nopicture(request.id)
    return Response()


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
