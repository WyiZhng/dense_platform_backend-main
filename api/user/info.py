from typing import Any
from datetime import date
import os,time
from fastapi import APIRouter, HTTPException
from fastapi.requests import Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from database.storage import load_accounts, load_user_detail, save_user_detail, save_user_avatar
from database.table import UserType
from database.table import UserSex
from utils.response import Response
from utils import resolveAccountJwt
from utils.request import TokenRequest
from fastapi import FastAPI, File, UploadFile
from database.api import uploadImage,uploadavatar
router = APIRouter()


class Form(BaseModel):
    def __init__(self, /, **data: Any):
        super().__init__(**data)

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
    name: str = None
    sex: UserSex = None
    birth: date = None
    phone: str = None
    email: str = None
    address: str = None


class InfoResponse(Response):
    def __init__(self, /, **data: Any):
        super().__init__(**data)

    form: Form


class UserData(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    username: str
    type: UserType


class UserResponse(Response):
    user: UserData


@router.post("/api/user")
async def user(request: TokenRequest):
    username = resolveAccountJwt(request.token)["account"]
    accounts = load_accounts()
    user_data = accounts.get(username)
    if user_data:
        # 创建 UserData 实例
        user = UserData(username=username, type=user_data['type'])
        return UserResponse(user=user)
    else:
        return Response(code=31, message="用户不存在")


# @router.post("/api/user")
# async def user(request: TokenRequest):
#     username = resolveAccountJwt(request.token)["account"]
#     accounts = load_accounts()
#     user_data = accounts.get(username)
#     if user_data:
#         return username,user_data
#     return Response(code=31, message="用户不存在")


@router.post("/api/info")
async def info(request: TokenRequest):
    username = resolveAccountJwt(request.token)["account"]
    user_info = load_user_detail(username)
    if user_info is None:
        return InfoResponse(code="33", message="用户没有设置信息", form=Form(name=username))
    return InfoResponse(form=Form(**user_info))


class SubmitInfoRequest(TokenRequest):
    form: Form


@router.post("/api/submitInfo")
async def submitInfo(request: SubmitInfoRequest):
    username = resolveAccountJwt(request.token)["account"]
    request.form.birth = request.form.birth.isoformat()#将datatime格式转为字符串，这样子才符合json格式
    form_data = request.form.model_dump()
    save_user_detail(username, form_data)
    return Response()



class ImageResponse(Response):
    image: str

class AvatarRequest(TokenRequest):
    id: int


@router.post("/api/submitAvatar")
async def submitAvatar(request: AvatarRequest):
    session = sessionmaker(bind=engine)()
    username = resolveAccountJwt(request.token)["account"]
    with session:
        detail = queryInfo(session, username)
        if detail is None:
            detail = UserDetail(id=username)
            session.add(detail)
        image = session.query(Image).filter(Image.id == request.id).first()
        detail.image = image
        session.commit()
        return Response()



@router.post("/api/avatar") 
async def avatar(request: TokenRequest):
    # 从token获取用户名
    username = resolveAccountJwt(request.token)["account"]
    for ext in ['jpg', 'png', 'jpeg']:
        image_path = f"storage/images/{username}.{ext}"
        # 如果头像文件存在,返回头像
        if os.path.exists(image_path):
            return StreamingResponse(open(image_path, "rb"))
    return StreamingResponse(open("default.png", "rb"))
    # 返回头像图片流
    
#  # 从token获取用户名
#     username = resolveAccountJwt(request.token)["account"]
#     # 获取用户信息
#     user_info = load_user_detail(username)
#     # 如果用户信息不存在或没有头像,返回默认头像
#     if user_info is None or 'avatar' not in user_info:
#         return StreamingResponse(open("default.png", "rb"))
#     # 获取头像ID
#     avatar_id = user_info['avatar']
#     # 构建头像图片路径
#     image_path = f"storage/images/{avatar_id}.{avatar_id.split('.')[-1]}"
#     # 如果头像文件不存在,返回默认头像
#     if not os.path.exists(image_path):
#         return StreamingResponse(open("default.png", "rb"))
#     # 返回头像图片流
#     return StreamingResponse(open(image_path, "rb"))


@router.post("/api/uploadimage/")
async def create_upload_file(requset:str,file: UploadFile | None = None):
    if not file:
        return {"message": "No upload file sent"}
    else:
        username = requset
        #user_info = load_user_detail(username) or {}
        # 读取上传文件的内容
        image_data = await file.read()
        # 从原始文件名获取扩展名
        image_ext = file.filename.split('.')[-1]
        # 生成唯一文件名(使用时间戳)
        save_name = save_user_avatar(username, image_ext, image_data)
        return {"filename": save_name}





