from typing import Any, Optional
import os,time
import shutil
from datetime import date
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.requests import Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import inspect
from dense_platform_backend_main.database.storage import load_accounts, load_user_detail, save_user_detail, save_user_avatar,delete_avatars,delete_image
from dense_platform_backend_main.database.api import *
from dense_platform_backend_main.database.table import UserSex
from dense_platform_backend_main.utils.response import Response
from dense_platform_backend_main.utils import (resolveAccountJwt)
from dense_platform_backend_main.utils.request import TokenRequest
from fastapi import FastAPI, File, UploadFile

router = APIRouter()


class Form(BaseModel):#表单格式
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
    request.form.birth = request.form.birth.isoformat()  # 将datatime格式转为字符串，这样子才符合json格式
    form_data = request.form.model_dump()
    save_user_detail(username, form_data)
    return Response()


class AvatarRequest(TokenRequest):
    id: str
class ImageResponse(Response):
    image: str

@router.post("/api/submitAvatar")
async def submitAvatar(request: AvatarRequest):
    username = resolveAccountJwt(request.token)["account"]
    # 假设图片存储在 storage/images 目录下
    found = False
    delete_avatars(username)
    for ext in ['jpg', 'png', 'jpeg']:
        image_path = f"storage/images/{request.id}.{ext}"
        if os.path.exists(image_path):
            # 执行文件复制操作
            user_avatar_dir = "storage/avatars"
            os.makedirs(user_avatar_dir, exist_ok=True)
            # 保留原始文件扩展名
            new_avatar_path = f"{user_avatar_dir}/{username}.{ext}"
            try:
                shutil.copy2(image_path, new_avatar_path)
                found = True
                delete_image(request.id)
                return Response()  
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to save avatar: {str(e)}")
    
    if not found:
        raise HTTPException(status_code=404, detail="Image not found")

    


# @router.post("/api/submitAvatar")
# async def submitAvatar(request:Request):
#     form = await request.form()
#     # 等待异步请求的表单数据，并获取表单数据
#     file = form.get("file")
#     # 从表单数据中获取名为"file"的文件
#     token = request.headers.get("token", default=None)
#     # 从请求头中获取名为"token"的值，如果没有提供则默认为None
#     username = resolveAccountJwt(token)["account"]
#     if token is None:
#         return Response(code=34, message="权限不足")
#     #username = resolveAccountJwt(token)['account']
#     # 解析token并从中获取用户名
#     image_id = uploadavatar(username,file.filename,await file.read())
#     return ImageResponse(image=image_id)

# @router.post("/api/uploadimage/")
# async def create_upload_file(requset: str, file: Optional[UploadFile] = None):
#     if not file:
#         return {"message": "No upload file sent"}
#     else:
#         username = requset
#         # user_info = load_user_detail(username) or {}
#         # 读取上传文件的内容
#         image_data = await file.read()
#         # 从原始文件名获取扩展名
#         image_ext = file.filename.split('.')[-1]
#         # 生成唯一文件名(使用时间戳)
#         save_name = save_user_avatar(username, image_ext, image_data)
#         return {"filename": save_name}


@router.post("/api/avatar")
async def avatar(request: TokenRequest):
    # 从token获取用户名
    username = resolveAccountJwt(request.token)["account"]
    for ext in ['jpg', 'png', 'jpeg']:
        image_path = f"storage/avatars/{username}.{ext}"
        # 如果头像文件存在,返回头像
        if os.path.exists(image_path):
            return StreamingResponse([open(image_path, "rb").read()])
    return StreamingResponse(open("default.png", "rb"))

'''

class Form(BaseModel):
    def __init__(self, /, **data: Any):
        super().__init__(**data)

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
    name: Optional[str] = ""
    sex: Optional[UserSex] = None
    birth: Optional[date] = None
    phone: Optional[str] = ""
    email: Optional[str] = ""
    address: Optional[str] = ""


class InfoResponse(Response):
    def __init__(self, /, **data: Any):
        super().__init__(**data)

    form: Form


class UserData(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    type: str


class UserResponse(Response):
    user: UserData


@router.post("/api/user")
async def user(request: TokenRequest):
    _session = sessionmaker(bind=engine)()
    username = resolveAccountJwt(request.token)["account"]
    with _session:
        _user = _session.query(User).filter(User.id == username).first()
        return UserResponse(user=UserData.model_validate(_user))


@router.post("/api/info")
async def info(request: TokenRequest):
    session = sessionmaker(bind=engine)()
    username = resolveAccountJwt(request.token)["account"]
    with session:
        userInfo = queryInfo(session, username)
        if userInfo is None:
            return InfoResponse(code="33", message="用户没有设置信息", form=Form(name=username))
        return InfoResponse(form=Form.model_validate(userInfo))


class SubmitInfoRequest(TokenRequest):
    form: Form


@router.post("/api/submitInfo")
async def submitInfo(request: SubmitInfoRequest):
    session = sessionmaker(bind=engine)()
    username = resolveAccountJwt(request.token)["account"]
    with session:
        # deleteInfo(session, username)
        form = request.form.dict()
        detail = queryInfo(session, username)
        if detail is not None:
            user_detail_columns = {c.key for c in inspect(UserDetail).mapper.column_attrs}

            # 仅更新表单中存在且在UserDetail模型中的字段
            for key, value in request.form.model_dump().items():
                if key in user_detail_columns:
                    setattr(detail, key, value)

        else:
            detail = UserDetail(id=username, **form)
            addInfo(session, detail)
        session.commit()
        return Response()


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


# @router.post("/api/uploadAvatar")
# async def uploadAvatar(request: Request):
#     token = request.headers.get("token", None)
#     if token is None:
#         return Response(code=34, message="用户未登录")
#     username = resolveAccountJwt(token)["account"]
#     form = await request.form()
#     file = form.get("file")
#     format = file.filename.split(".")[-1]
#     if os.path.exists(f"./avatar/{username}"):
#         os.removedirs(f"./avatar/{username}")
#     os.mkdir(f"./avatar/{username}")
#     with open(f"./avatar/{username}/{username}.{format}", "wb") as f:
#         f.write(file.file.read())
#     return Response(code=0, message="")


@router.post("/api/avatar")
async def avatar(request: TokenRequest):
    username = resolveAccountJwt(request.token)["account"]
    session = sessionmaker(bind=engine)()
    with session:
        detail = session.query(UserDetail).filter(UserDetail.id == username).first()
        if detail is None or detail.image is None:
            return StreamingResponse(open("default.png", "rb"))
    return StreamingResponse([detail.image.data])
'''
