import typing
from sqlalchemy.orm import sessionmaker
import typing
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from dense_platform_backend_main.database.storage import (
    load_accounts, load_user_detail, save_user_detail,
    save_doctor_info, load_doctor_info
)
from dense_platform_backend_main.database.db import engine
from dense_platform_backend_main.database.table import UserType, Doctor as tDoctor, User, UserSex
from dense_platform_backend_main.utils.response import Response
from dense_platform_backend_main.utils import resolveAccountJwt
from dense_platform_backend_main.utils.request import TokenRequest
from pydantic import BaseModel, ConfigDict

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

#
#
# class Doctor(BaseModel):
#     id: str
#     name: str
#     sex: UserSex
#     position: str = ""
#     workplace: str = ""
#
#
# class DoctorResponse(Response):
#     doctors: typing.List[Doctor]
#
#
# @router.post("/api/doctors")
# async def doctors(request: TokenRequest):
#     username = resolveAccountJwt(request.token)["account"]
#     session = sessionmaker(bind=engine)()
#     _doctors = []
#     with session:
#         query_doctors = session.query(User).filter(User.type == UserType.Doctor).all()
#         for doctor in query_doctors:
#             tD = session.query(tDoctor).filter(tDoctor.id == doctor.id).first()
#             detail = doctor.user_detail
#             (name, sex) = (doctor.id, UserSex.Male) if detail is None else (detail.name, detail.sex)
#             (position, workplace) = ("", "") if tD is None else (tD.workplace, tD.position)
#             _doctors.append(Doctor(id=doctor.id, name=name, sex=sex, position=position, workplace=workplace))
#         return DoctorResponse(doctors=_doctors)
#
#
# class DoctorInfo(BaseModel):
#     model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
#     position: str
#     workplace: str
#
#
# class DoctorInfoResponse(Response):
#     form: DoctorInfo
#
#
# class SetDoctorInfoRequest(TokenRequest):
#     form: DoctorInfo
#
#
# @router.post("/api/doctor/info/set")
# async def setDoctorInfo(request: SetDoctorInfoRequest):
#     username = resolveAccountJwt(request.token)["account"]
#     session = sessionmaker(bind=engine)()
#     with session:
#         info = session.query(tDoctor).filter(tDoctor.id == username).first()
#         info.position = request.form.position
#         info.workplace = request.form.workplace
#         session.commit()
#         return DoctorInfoResponse(form=DoctorInfo.model_validate(info))
#
#
# @router.post("/api/doctor/info")
# async def doctorInfo(request: TokenRequest):
#     username = resolveAccountJwt(request.token)["account"]
#     session = sessionmaker(bind=engine)()
#     with session:
#         info = session.query(tDoctor).filter(tDoctor.id == username).first()
#
#         if info is None:
#             info = tDoctor(id=username, position='', workplace='')
#             session.add(info)
#         session.commit()
#         return DoctorInfoResponse(form=DoctorInfo.model_validate(info))
