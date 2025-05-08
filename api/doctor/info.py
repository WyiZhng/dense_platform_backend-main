import typing
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from database.storage import (
    load_accounts, load_user_detail, save_user_detail,
    save_doctor_info, load_doctor_info
)
from database.table import UserType, UserSex
from utils.response import Response
from utils import resolveAccountJwt
from utils.request import TokenRequest

router = APIRouter()

class Doctor(BaseModel):
    id: str
    name: str
    sex: UserSex
    position: str = ""
    workplace: str = ""

class DoctorResponse(Response):
    doctors: typing.List[Doctor]

@router.post("/api/doctors")
async def doctors(request: TokenRequest):
    username = resolveAccountJwt(request.token)["account"]
    _doctors = []
    
    # 从账号文件中获取所有医生
    accounts = load_accounts()
    for user_id, account in accounts.items():
        if account.get('type') != UserType.Doctor:
            continue
            
        # 获取医生的基本信息
        user_detail = load_user_detail(user_id)
        doctor_info = load_doctor_info(user_id)
        
        # 设置默认值
        name = user_detail.get('name', user_id) if user_detail else user_id
        sex = user_detail.get('sex', UserSex.Male) if user_detail else UserSex.Male
        position = doctor_info.get('position', '') if doctor_info else ''
        workplace = doctor_info.get('workplace', '') if doctor_info else ''
        
        _doctors.append(Doctor(
            id=user_id,
            name=name,
            sex=sex,
            position=position,
            workplace=workplace
        ))
    
    return DoctorResponse(doctors=_doctors)

class DoctorInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
    position: str
    workplace: str

class DoctorInfoResponse(Response):
    form: DoctorInfo

class SetDoctorInfoRequest(TokenRequest):
    form: DoctorInfo

@router.post("/api/doctor/info/set")
async def setDoctorInfo(request: SetDoctorInfoRequest):
    username = resolveAccountJwt(request.token)["account"]
    
    # 保存医生特定信息
    doctor_info = {
        'id': username,
        'position': request.form.position,
        'workplace': request.form.workplace
    }
    save_doctor_info(username, doctor_info)
    
    return DoctorInfoResponse(form=DoctorInfo(**doctor_info))

@router.post("/api/doctor/info")
async def doctorInfo(request: TokenRequest):
    username = resolveAccountJwt(request.token)["account"]
    
    # 获取医生信息，如果不存在则创建默认值
    doctor_info = load_doctor_info(username)
    if doctor_info is None:
        doctor_info = {
            'id': username,
            'position': '',
            'workplace': ''
        }
        save_doctor_info(username, doctor_info)
    
    return DoctorInfoResponse(form=DoctorInfo(**doctor_info))
