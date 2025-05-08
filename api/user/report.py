from datetime import date
import typing
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from database.table import ImageType, ReportStatus
from database.storage import (
    save_report, load_report, get_user_reports,
    save_comment, get_report_comments,
    save_report_image, get_report_images,
    delete_report,load_accounts 
)
from utils.request import TokenRequest
from utils.response import Response
from utils import resolveAccountJwt

router = APIRouter()


class UploadResponse(Response):
    fileId: str


class ReportRequest(BaseModel):
    token: str
    doctor: str
    images: typing.List[str]


@router.post("/api/submitReport")
async def submitReport(request: ReportRequest):
    username = resolveAccountJwt(request.token)["account"]
    # 创建一个字典来统计各个标签的数量
    
    report_data = {
        "user": username,
        "doctor": request.doctor,
        "submitTime": str(date.today()),
        "current_status": ReportStatus.Checking,
        "images": request.images,
        "diagnose": None,
        "dia": None,
        "dia_time": None,
        "dia_result": None
    }
    
    save_report(report_data)
    return Response()
#  img_path = f"storage/images/{request.images[0]}.jpg"  # 假设图片存储路径

#     # 读取图片并转换为字节流
#     with open(img_path, 'rb') as img_file:
#         contents = img_file.read()
#     image_np = np.asarray(bytearray(contents), dtype=np.uint8)

#     img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
#     try:
#         data_json,image_id = predict(img)  # 预测过程，将所需数据保存并返回（这里可以保存到数据库）
#     except Exception as e:
#         print(e)
#     diag = teechLevel(str(data_json))
#     username = resolveAccountJwt(request.token)["account"]
#     report_data = {
#         "user": username,
#         "doctor": request.doctor,
#         "submitTime": str(date.today()),
#         "current_status": ReportStatus.Checking,
#         "images": request.images,
#         "diagnose": diag,
#         "Result_img":image_id
#     }
#     save_report(report_data)
#     return str(data_json),image_id


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
    reports: list[Report]

#12.9修改了这个接口和其中get_user_reports的参数这样子方便区分用户和医师
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
    images: list[str]


@router.post("/api/report/images")
def reportImages(request: ReportImageRequest):
    username = resolveAccountJwt(request.token)["account"]
    report = load_report(request.id)
    if not report:
        return ReportImageResponse(images=[])
    return ReportImageResponse(images=report.get("images", []))


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
    diagnose: str | None
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
    delete_report(request.id)
    return Response()

# #算法接口备份
# @router.post("/algorithm/predict")
# async def predict_image(file: UploadFile = File(...)):  # 接受一个图片文件输入

#     contents = await file.read()
#     image_np = np.asarray(bytearray(contents), dtype=np.uint8)
#     img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
#     try:
#         data_json,image_id = predict(img)  # 预测过程，将所需数据保存并返回（这里可以保存到数据库）
#     except Exception as e:
#         print(e)

  
#     return str(data_json),image_id
