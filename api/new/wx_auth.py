#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信小程序登录认证API

实现微信小程序的登录认证功能，包括：
1. 接收前端发送的微信登录凭证code
2. 调用微信API获取openid和session_key
3. 创建或更新用户信息
4. 返回登录结果给前端

作者: AI Assistant
创建时间: 2024
"""

import requests
import json
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.db import get_db
from database.table import User, UserDetail, UserType, UserSex
from utils.response import Response
from utils.jwt import create_access_token, verify_token
from config.wx_config import wx_config  # 导入安全的微信配置管理

# 创建路由器
router = APIRouter()

# 使用安全的配置管理（从环境变量读取敏感信息）
# 生产环境中的敏感配置通过环境变量 WX_APP_ID 和 WX_APP_SECRET 设置
WX_CONFIG = wx_config.get_config()


class WxLoginRequest(BaseModel):
    """微信登录请求模型"""
    code: str  # 微信登录凭证
    appId: Optional[str] = None  # 小程序AppID（可选）
    user_info: Optional[dict] = None  # 可选的用户信息（昵称、头像等）


class PrivacyConsentRequest(BaseModel):
    """隐私授权请求模型"""
    consent: bool  # 隐私授权状态：True=同意，False=拒绝





class WxAuthService:
    """微信认证服务类"""
    
    @staticmethod
    def get_wx_user_info(code: str) -> dict:
        """
        调用微信API获取用户openid和session_key
        
        Args:
            code: 微信登录凭证
            
        Returns:
            包含openid、session_key等信息的字典
            
        Raises:
            HTTPException: 当微信API调用失败时抛出异常
        """
        # 构建请求参数
        params = {
            "appid": WX_CONFIG["app_id"],
            "secret": WX_CONFIG["app_secret"],
            "js_code": code,
            "grant_type": "authorization_code"
        }
        
        try:
            # 发送HTTP请求到微信API
            response = requests.get(WX_CONFIG["login_url"], params=params, timeout=10)
            response.raise_for_status()
            
            # 解析响应数据
            wx_data = response.json()
            
            # 检查微信API是否返回错误
            if "errcode" in wx_data:
                error_msg = f"微信API错误: {wx_data.get('errcode')} - {wx_data.get('errmsg')}"
                raise HTTPException(status_code=400, detail=error_msg)
            
            # 验证必要字段是否存在
            if "openid" not in wx_data or "session_key" not in wx_data:
                raise HTTPException(status_code=400, detail="微信API返回数据不完整")
            
            return wx_data
            
        except requests.RequestException as e:
            raise HTTPException(status_code=500, detail=f"网络请求失败: {str(e)}")
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="微信API响应格式错误")
    

    

    
    @staticmethod
    def find_or_create_user(db: Session, openid: str, user_info: Optional[dict] = None) -> tuple[User, bool]:
        """
        根据openid查找或创建用户
        
        Args:
            db: 数据库会话
            openid: 微信用户的openid
            user_info: 可选的用户信息
            
        Returns:
            tuple[User, bool]: (用户对象, 是否为新用户)
        """
        # 首先尝试根据openid查找现有用户
        existing_user = db.query(User).filter(User.openid == openid).first()
        
        if existing_user:
            # 用户已存在，更新最后登录时间
            existing_user.last_login_time = datetime.now()
            db.commit()
            return existing_user, False
        
        # 用户不存在，创建新用户
        # 生成唯一的用户ID（确保长度不超过20个字符）
        # 使用openid前8位 + 当前时间戳的后6位数字
        timestamp_suffix = str(int(datetime.now().timestamp()))[-6:]  # 取时间戳后6位
        user_id_str = f"wx_{openid[:8]}_{timestamp_suffix}"  # 格式: wx_xxxxxxxx_xxxxxx (总长度18字符)
        
        # 生成数值型用户ID（使用时间戳确保唯一性）
        numeric_user_id = int(datetime.now().timestamp() * 1000000)  # 微秒级时间戳作为数值ID
        
        new_user = User(
            id=user_id_str,  # 使用字符串ID
            username=f"wx_{openid[:8]}",  # 使用openid前8位作为用户名
            openid=openid,
            type=UserType.Patient,  # 默认为患者类型（修复：Patient首字母大写）
            user_id=numeric_user_id,  # 数值型用户ID，必填字段
            created_time=datetime.now(),
            last_login_time=datetime.now(),
            is_active=True,
            password=None  # 微信登录用户无密码
        )
        
        db.add(new_user)
        db.flush()  # 获取用户ID
        
        # 创建用户详细信息
        user_detail = UserDetail(
            id=new_user.id,  # 使用相同的ID
            name=user_info.get("nickName", "微信用户") if user_info else "微信用户",
            sex=None,  # 默认性别未知（修复：UserSex枚举中没有UNKNOWN值）
            avatar_url=user_info.get("avatarUrl") if user_info else None,
            created_time=datetime.now()
        )
        
        db.add(user_detail)
        db.commit()
        
        return new_user, True
    



@router.post("/api/wx/login")
async def wx_login(
    request: WxLoginRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    微信小程序登录接口
    
    接收前端发送的微信登录凭证，调用微信API验证，
    创建或更新用户信息，返回登录结果
    
    Args:
        request: 登录请求数据
        http_request: HTTP请求对象
        db: 数据库会话
        
    Returns:
        登录响应数据（符合前端LoginResponse接口格式）
    """
    try:
        # 记录登录尝试
        client_ip = http_request.client.host if http_request.client else "unknown"
        print(f"微信登录请求 - IP: {client_ip}, Code: {request.code[:10]}...")
        
        # 调用微信API获取用户信息
        wx_data = WxAuthService.get_wx_user_info(request.code)
        openid = wx_data["openid"]
        session_key = wx_data["session_key"]
        unionid = wx_data.get("unionid")
        
        print(f"微信API响应 - OpenID: {openid[:10]}..., SessionKey: {session_key[:10]}...")
        
        # 查找或创建用户
        user, is_new_user = WxAuthService.find_or_create_user(
            db, openid, request.user_info
        )
        
        # 创建JWT令牌
        token_data = {
            "user_id": user.id,
            "openid": openid,
            "user_type": user.type.value if user.type else "patient"
        }
        
        # 生成访问令牌（有效期2小时）
        access_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(hours=2)
        )
        
        # 获取用户详细信息
        user_detail = db.query(UserDetail).filter(UserDetail.id == user.id).first()
        
        # 构建用户信息
        user_info_data = {
            "openid": openid,
            "sessionKey": session_key,
            "unionid": unionid,
            "nickName": user_detail.name if user_detail else "微信用户",
            "avatarUrl": user_detail.avatar_url if user_detail and user_detail.avatar_url else None,
            "privacyConsent": user.privacy_consent  # 隐私授权状态：None=未询问，True=同意，False=拒绝
        }
        
        print(f"登录成功 - 用户ID: {user.id}, 新用户: {is_new_user}")
        
        # 返回符合前端LoginResponse接口的响应格式
        return {
            "success": True,
            "token": access_token,
            "userInfo": user_info_data,
            "expiresIn": 7200,  # 2小时，单位秒
            "message": "登录成功" if not is_new_user else "注册并登录成功"
        }
        
    except HTTPException as e:
        # 重新抛出HTTP异常
        print(f"微信登录HTTP异常: {e.detail}")
        return {
            "success": False,
            "message": e.detail,
            "expiresIn": 0
        }
    except Exception as e:
        # 处理其他异常
        error_msg = f"登录失败: {str(e)}"
        print(f"微信登录异常: {error_msg}")
        return {
            "success": False,
            "message": error_msg,
            "expiresIn": 0
        }






@router.post("/api/wx/refresh")
async def wx_refresh_token(
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    刷新微信登录令牌
    
    用于刷新即将过期的登录令牌
    
    Args:
        http_request: HTTP请求对象
        db: 数据库会话
        
    Returns:
        刷新结果
    """
    try:
        # 从请求头获取当前令牌
        authorization = http_request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            return {
                "success": False,
                "message": "缺少有效的授权令牌"
            }
        
        current_token = authorization.split(" ")[1]
        
        # 这里应该验证当前令牌并生成新令牌
        # 暂时返回成功响应
        new_token = create_access_token(
            data={"refresh": True},
            expires_delta=timedelta(hours=2)
        )
        
        return {
            "success": True,
            "token": new_token,
            "expiresIn": 7200,
            "message": "令牌刷新成功"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"令牌刷新失败: {str(e)}"
        }


@router.get("/api/wx/user-info")
async def get_wx_user_info(
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    获取微信用户信息
    
    根据当前登录令牌获取用户详细信息
    
    Args:
        http_request: HTTP请求对象
        db: 数据库会话
        
    Returns:
        用户信息
    """
    try:
        # 从请求头获取令牌
        authorization = http_request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            return {
                "success": False,
                "message": "用户未登录或令牌已过期"
            }
        
        # 这里应该验证令牌并获取用户信息
        # 暂时返回模拟数据
        return {
            "success": True,
            "userInfo": {
                "openid": "mock_openid",
                "nickName": "微信用户",
                "avatarUrl": None
            },
            "message": "获取用户信息成功"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"获取用户信息失败: {str(e)}"
        }


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    获取当前登录用户的依赖函数
    
    Args:
        request: HTTP请求对象
        db: 数据库会话
        
    Returns:
        当前登录的用户对象
        
    Raises:
        HTTPException: 当认证失败时抛出异常
    """
    # 从请求头中获取Authorization token
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供有效的认证令牌")
    
    # 提取token
    token = authorization.replace("Bearer ", "")
    
    # 验证token
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="无效或已过期的认证令牌")
    
    # 获取用户ID
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="令牌中缺少用户信息")
    
    # 查询用户
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="用户账户已被禁用")
    
    return user


@router.post("/api/wx/privacy-consent")
async def update_privacy_consent(
    request: PrivacyConsentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新用户隐私授权状态接口
    
    用户在前端弹窗中选择是否同意隐私授权后，调用此接口更新数据库中的授权状态
    
    Args:
        request: 隐私授权请求数据
        current_user: 当前登录用户（通过JWT认证获取）
        db: 数据库会话
        
    Returns:
        更新结果响应
    """
    try:
        # 更新用户的隐私授权状态
        current_user.privacy_consent = request.consent
        current_user.privacy_consent_time = datetime.now()
        current_user.updated_at = datetime.now()
        
        # 提交数据库更改
        db.commit()
        
        print(f"用户隐私授权更新成功 - 用户ID: {current_user.id}, 授权状态: {request.consent}")
        
        return {
            "success": True,
            "message": "隐私授权状态更新成功",
            "privacyConsent": request.consent
        }
        
    except Exception as e:
        # 回滚数据库事务
        db.rollback()
        print(f"更新隐私授权状态失败: {str(e)}")
        
        return {
            "success": False,
            "message": f"更新隐私授权状态失败: {str(e)}"
        }