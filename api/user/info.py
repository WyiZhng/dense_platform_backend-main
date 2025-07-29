from typing import Any, Optional
import os
from datetime import date
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import inspect

from dense_platform_backend_main.database.table import User, UserDetail, UserSex, UserType, Image
from dense_platform_backend_main.utils.response import Response
from dense_platform_backend_main.utils.request import TokenRequest
from dense_platform_backend_main.api.auth.session import get_db
from dense_platform_backend_main.api.auth.middleware import AuthMiddleware
from dense_platform_backend_main.utils.auth_compat import AuthCompat
from dense_platform_backend_main.services.rbac_middleware import RequireAuthWithContext, RequireSelfOrPermission
from dense_platform_backend_main.services.database_storage_service import DatabaseStorageService

router = APIRouter()


class Form(BaseModel):
    """用户信息表单"""
    class Config:
        from_attributes = True
        arbitrary_types_allowed = True
    name: Optional[str] = None
    sex: Optional[UserSex] = None
    birth: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class InfoResponse(Response):
    """用户信息响应"""
    form: Optional[Form] = None


class UserData(BaseModel):
    """用户数据"""
    class Config:
        from_attributes = True
    username: str
    type: UserType


class UserResponse(Response):
    """用户响应"""
    user: Optional[UserData] = None


class SubmitInfoRequest(BaseModel):
    """提交用户信息请求"""
    form: Form


class AvatarRequest(TokenRequest):
    """头像请求"""
    id: int


class ImageResponse(Response):
    """图片响应"""
    image: Optional[str] = None


@router.post("/api/user")
async def user(
    db: Session = Depends(get_db),
    current_user = RequireAuthWithContext
):
    """
    获取用户基本信息 - 需要认证
    
    注意：此API确保注销后用户数据仍然保留在数据库中
    """
    try:
        username = current_user["user_id"]
        
        # 从数据库获取用户信息
        user_record = db.query(User).filter(User.id == username).first()
        if not user_record:
            return UserResponse(code=31, message="用户不存在")
        
        user_data = UserData(username=username, type=user_record.type)
        return UserResponse(code=0, message="获取用户信息成功", user=user_data)
        
    except Exception as e:
        return UserResponse(code=500, message=f"获取用户信息失败: {str(e)}")


@router.post("/api/info")
async def info(
    db: Session = Depends(get_db),
    current_user = RequireAuthWithContext
):
    """
    获取用户详细信息 - 需要认证
    
    注意：此API确保注销后用户详细信息仍然保留在数据库中
    """
    try:
        username = current_user["user_id"]
        
        # 从数据库获取用户详细信息
        user_detail = db.query(UserDetail).filter(UserDetail.id == username).first()
        
        if user_detail is None:
            # 如果没有详细信息，返回基本表单
            return InfoResponse(
                code=33, 
                message="用户没有设置信息", 
                form=Form(name=username)
            )
        
        # 构建表单数据
        form_data = Form(
            name=user_detail.name,
            sex=user_detail.sex,
            birth=user_detail.birth,
            phone=user_detail.phone,
            email=user_detail.email,
            address=user_detail.address
        )
        
        return InfoResponse(code=0, message="获取用户信息成功", form=form_data)
        
    except Exception as e:
        return InfoResponse(code=500, message=f"获取用户信息失败: {str(e)}")


@router.post("/api/submitInfo")
async def submit_info(
    request: SubmitInfoRequest,
    db: Session = Depends(get_db),
    current_user = RequireAuthWithContext
):
    """
    提交用户详细信息 - 需要认证
    
    注意：此API将数据保存到数据库，确保注销后数据不会丢失
    """
    try:
        username = current_user["user_id"]
        print(f"DEBUG: 用户 {username} 提交信息")
        # 获取表单数据，兼容不同版本的Pydantic
        try:
            form_data = request.form.model_dump()
        except AttributeError:
            # 如果model_dump不存在，尝试使用dict()
            try:
                form_data = request.form.dict()
            except AttributeError:
                # 如果都不存在，手动构建字典
                form_data = {
                    'name': request.form.name,
                    'sex': request.form.sex,
                    'birth': request.form.birth,
                    'phone': request.form.phone,
                    'email': request.form.email,
                    'address': request.form.address
                }
        
        print(f"DEBUG: 接收到的表单数据: {form_data}")
        
        # 查找现有的用户详细信息
        user_detail = db.query(UserDetail).filter(UserDetail.id == username).first()
        
        if user_detail:
            print(f"DEBUG: 找到现有用户详细信息，正在更新")
            # 更新现有记录
            user_detail_columns = {c.key for c in inspect(UserDetail).mapper.column_attrs}
            print(f"DEBUG: UserDetail表字段: {user_detail_columns}")
            
            for key, value in form_data.items():
                if key in user_detail_columns and value is not None:
                    print(f"DEBUG: 更新字段 {key} = {value}")
                    setattr(user_detail, key, value)
                else:
                    print(f"DEBUG: 跳过字段 {key} (不在表中或值为None)")
        else:
            print(f"DEBUG: 未找到现有记录，创建新记录")
            # 创建新记录
            # 过滤掉None值
            form_data = {k: v for k, v in form_data.items() if v is not None}
            print(f"DEBUG: 创建新记录的数据: {form_data}")
            user_detail = UserDetail(id=username, **form_data)
            db.add(user_detail)
        
        # 在提交前检查数据
        print(f"DEBUG: 提交前的用户详细信息:")
        print(f"  - id: {user_detail.id}")
        print(f"  - name: {user_detail.name}")
        print(f"  - sex: {user_detail.sex}")
        print(f"  - birth: {user_detail.birth}")
        print(f"  - phone: {user_detail.phone}")
        print(f"  - email: {user_detail.email}")
        print(f"  - address: {user_detail.address}")
        
        db.commit()
        print(f"DEBUG: 数据已提交到数据库")
        
        # 验证数据是否真的保存了
        saved_detail = db.query(UserDetail).filter(UserDetail.id == username).first()
        if saved_detail:
            print(f"DEBUG: 验证保存成功:")
            print(f"  - id: {saved_detail.id}")
            print(f"  - name: {saved_detail.name}")
            print(f"  - sex: {saved_detail.sex}")
            print(f"  - birth: {saved_detail.birth}")
            print(f"  - phone: {saved_detail.phone}")
            print(f"  - email: {saved_detail.email}")
            print(f"  - address: {saved_detail.address}")
        else:
            print(f"DEBUG: 警告 - 验证时未找到保存的数据!")
        
        return Response(code=0, message="用户信息保存成功")
        
    except Exception as e:
        print(f"DEBUG: 保存用户信息时发生错误: {str(e)}")
        import traceback
        print(f"DEBUG: 错误堆栈: {traceback.format_exc()}")
        db.rollback()
        return Response(code=500, message=f"保存用户信息失败: {str(e)}")


class SubmitAvatarRequest(BaseModel):
    """提交头像请求"""
    id: int

@router.post("/api/submitAvatar")
async def submit_avatar(
    request: SubmitAvatarRequest,
    db: Session = Depends(get_db),
    current_user = RequireAuthWithContext
):
    """
    提交用户头像 - 需要认证 (使用数据库存储)
    
    注意：此API将头像信息保存到avatars表中
    """
    try:
        username = current_user["user_id"]
        
        # 查找图片是否存在
        image_data = DatabaseStorageService.load_image(db, str(request.id))
        if not image_data:
            return Response(code=404, message="图片不存在")
        
        # 将图片保存为用户头像到avatars表，使用用户ID作为文件名
        success = DatabaseStorageService.save_avatar(db, username, image_data, f"{username}.jpg")
        
        if success:
            return Response(code=0, message="头像设置成功")
        else:
            return Response(code=500, message="头像设置失败")
        
    except Exception as e:
        db.rollback()
        return Response(code=500, message=f"设置头像失败: {str(e)}")


@router.post("/api/avatar")
async def avatar(
    db: Session = Depends(get_db),
    current_user = RequireAuthWithContext
):
    """
    获取用户头像 - 需要认证 (使用数据库存储)
    
    注意：此API从avatars表获取头像，如果用户没有头像则返回默认头像
    """
    try:
        username = current_user["user_id"]
        
        # 从avatars表获取用户头像
        avatar_data = DatabaseStorageService.load_avatar(db, username)
        
        if avatar_data:
            import io
            return StreamingResponse(
                io.BytesIO(avatar_data), 
                media_type="image/jpeg",
                headers={"Content-Disposition": "inline"}
            )
        
        # 如果用户没有头像，返回默认头像
        default_avatar_data = DatabaseStorageService.load_avatar(db, "default")
        
        if default_avatar_data:
            import io
            return StreamingResponse(
                io.BytesIO(default_avatar_data), 
                media_type="image/png",
                headers={"Content-Disposition": "inline"}
            )
        
        # 如果连默认头像都没有，尝试从文件系统加载并保存到数据库
        default_avatar_path = "default.png"
        if os.path.exists(default_avatar_path):
            print(f"Loading default avatar from: {default_avatar_path}")
            with open(default_avatar_path, "rb") as f:
                default_data = f.read()
            
            print(f"Default avatar size: {len(default_data)} bytes")
            
            # 保存默认头像到数据库
            success = DatabaseStorageService.save_avatar(db, "default", default_data, "default.png")
            print(f"Save default avatar to database: {success}")
            
            import io
            return StreamingResponse(
                io.BytesIO(default_data), 
                media_type="image/png",
                headers={"Content-Disposition": "inline"}
            )
        
        # 如果默认头像文件也不存在，返回404
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No avatar found")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error loading avatar: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to load avatar")


