import typing
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from dense_platform_backend_main.database.table import UserType, Doctor as tDoctor, User, UserSex, UserDetail
from dense_platform_backend_main.services.database_storage_service import DatabaseStorageService
from dense_platform_backend_main.utils.response import Response
from dense_platform_backend_main.utils.request import TokenRequest
from dense_platform_backend_main.services.rbac_middleware import RequireAuthWithContext, RequirePermission, RequireRole
from dense_platform_backend_main.api.auth.session import get_db

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
async def doctors():
    """获取医生列表 - 公开接口，不需要认证"""
    from sqlalchemy.orm import sessionmaker
    from dense_platform_backend_main.database.db import engine
    
    _doctors = []
    
    try:
        # 创建数据库会话
        Session = sessionmaker(bind=engine)
        db = Session()
        
        try:
            # 从数据库中获取所有医生
            query_doctors = db.query(User).filter(User.type == UserType.Doctor).all()
            
            for doctor in query_doctors:
                # 获取医生的基本信息
                user_detail = DatabaseStorageService.load_user_detail(db, doctor.id)
                doctor_info = DatabaseStorageService.load_doctor_info(db, doctor.id)

                # 设置默认值，确保sex不为None
                name = user_detail.get('name', doctor.id) if user_detail else doctor.id
                sex_value = user_detail.get('sex') if user_detail else None
                
                # 处理sex值，确保它是有效的UserSex枚举值
                if sex_value is None:
                    sex = UserSex.Male
                elif isinstance(sex_value, UserSex):
                    sex = sex_value
                elif isinstance(sex_value, int):
                    sex = UserSex.Male if sex_value == 1 else UserSex.Female
                else:
                    sex = UserSex.Male  # 默认值
                    
                position = doctor_info.get('position', '') if doctor_info else ''
                workplace = doctor_info.get('workplace', '') if doctor_info else ''
                
                _doctors.append(Doctor(
                    id=doctor.id,
                    name=name,
                    sex=sex,
                    position=position,
                    workplace=workplace
                ))
        finally:
            db.close()

        return DoctorResponse(doctors=_doctors)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve doctors: {str(e)}")


class DoctorInfo(BaseModel):
    class Config:
        from_attributes = True
        arbitrary_types_allowed = True
    id: str
    name: Optional[str] = None
    sex: Optional[int] = None
    birth: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    position: str
    workplace: str
    description: Optional[str] = None


class DoctorInfoResponse(Response):
    form: DoctorInfo


class SetDoctorInfoRequest(BaseModel):
    form: DoctorInfo


@router.post("/api/doctor/info/set")
async def setDoctorInfo(
    request: SetDoctorInfoRequest,
    db: Session = Depends(get_db),
    current_user = RequireAuthWithContext
):
    """设置医生信息 - 需要医生用户类型"""
    username = current_user["user_id"]
    
    # 检查用户是否是医生类型
    user = db.query(User).filter(User.id == username).first()
    if not user or user.type != UserType.Doctor:
        raise HTTPException(status_code=403, detail="Only doctors can access this endpoint")

    try:
        # 分离用户基本信息和医生专业信息
        user_detail_data = {}
        doctor_info_data = {}
        
        # 用户基本信息 (存入 user_detail 表)
        if request.form.name is not None:
            user_detail_data['name'] = request.form.name
        if request.form.sex is not None:
            user_detail_data['sex'] = UserSex(request.form.sex) if isinstance(request.form.sex, int) else request.form.sex
        if request.form.birth is not None:
            # 处理日期格式
            if isinstance(request.form.birth, str):
                from datetime import datetime
                try:
                    birth_date = datetime.strptime(request.form.birth, '%Y-%m-%d').date()
                    user_detail_data['birth'] = birth_date
                except ValueError:
                    pass  # 如果日期格式不正确，跳过
            else:
                user_detail_data['birth'] = request.form.birth
        if request.form.phone is not None:
            user_detail_data['phone'] = request.form.phone
        if request.form.email is not None:
            user_detail_data['email'] = request.form.email
        if request.form.address is not None:
            user_detail_data['address'] = request.form.address
        
        # 医生专业信息 (存入 doctor 表)
        doctor_info_data['position'] = request.form.position or ''
        doctor_info_data['workplace'] = request.form.workplace or ''
        if request.form.description is not None:
            doctor_info_data['description'] = request.form.description
        
        # 保存用户基本信息到 user_detail 表
        if user_detail_data:
            user_detail_success = DatabaseStorageService.save_user_detail(db, username, user_detail_data)
            if not user_detail_success:
                raise HTTPException(status_code=500, detail="Failed to save user detail information")
        
        # 保存医生专业信息到 doctor 表
        doctor_success = DatabaseStorageService.save_doctor_info(db, username, doctor_info_data)
        if not doctor_success:
            raise HTTPException(status_code=500, detail="Failed to save doctor information")
        
        # 返回完整的医生信息
        complete_info = {
            'id': username,
            'name': user_detail_data.get('name'),
            'sex': user_detail_data.get('sex'),
            'birth': request.form.birth,
            'phone': user_detail_data.get('phone'),
            'email': user_detail_data.get('email'),
            'address': user_detail_data.get('address'),
            'position': doctor_info_data['position'],
            'workplace': doctor_info_data['workplace'],
            'description': doctor_info_data.get('description')
        }
        
        return DoctorInfoResponse(form=DoctorInfo(**complete_info))
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update doctor information: {str(e)}")


@router.post("/api/doctor/info")
async def doctorInfo(
    db: Session = Depends(get_db),
    current_user = RequireAuthWithContext
):
    """获取医生信息 - 需要医生用户类型"""
    username = current_user["user_id"]
    
    # 检查用户是否是医生类型
    user = db.query(User).filter(User.id == username).first()
    if not user or user.type != UserType.Doctor:
        raise HTTPException(status_code=403, detail="Only doctors can access this endpoint")

    # 获取用户详细信息
    user_detail = DatabaseStorageService.load_user_detail(db, username)
    
    # 获取医生专业信息，如果不存在则创建默认值
    doctor_info = DatabaseStorageService.load_doctor_info(db, username)
    if doctor_info is None:
        doctor_info = {
            'position': '',
            'workplace': '',
            'description': ''
        }
        DatabaseStorageService.save_doctor_info(db, username, doctor_info)

    # 合并用户基本信息和医生专业信息
    complete_info = {
        'id': username,
        'name': user_detail.get('name') if user_detail else None,
        'sex': user_detail.get('sex') if user_detail else None,
        'birth': user_detail.get('birth') if user_detail else None,
        'phone': user_detail.get('phone') if user_detail else None,
        'email': user_detail.get('email') if user_detail else None,
        'address': user_detail.get('address') if user_detail else None,
        'position': doctor_info.get('position', ''),
        'workplace': doctor_info.get('workplace', ''),
        'description': doctor_info.get('description', '')
    }

    return DoctorInfoResponse(form=DoctorInfo(**complete_info))