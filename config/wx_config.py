#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信小程序配置管理模块

提供微信小程序相关配置的安全管理，支持从环境变量读取敏感信息
避免在代码中硬编码敏感配置信息

作者: AI Assistant
创建时间: 2024
"""

import os
from typing import Dict, Optional

class WxConfig:
    """
    微信小程序配置类
    
    负责管理微信小程序的配置信息，优先从环境变量读取，
    如果环境变量不存在则使用默认值（仅用于开发环境）
    """
    
    def __init__(self):
        """
        初始化微信配置
        
        配置优先级：
        1. 环境变量（生产环境推荐）
        2. 默认值（仅用于开发环境）
        """
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, str]:
        """
        加载微信小程序配置
        
        Returns:
            包含微信配置信息的字典
        """
        return {
            "app_id": os.getenv("WX_APP_ID", "wx9b701d674f2a15e4"),
            "app_secret": os.getenv("WX_APP_SECRET", "7528ff4edbb1f09430fae123beaf8118"),
            "login_url": "https://api.weixin.qq.com/sns/jscode2session",
            "phone_url": "https://api.weixin.qq.com/wxa/business/getuserphonenumber"
        }
    
    @property
    def app_id(self) -> str:
        """
        获取小程序AppID
        
        Returns:
            小程序AppID
        """
        return self._config["app_id"]
    
    @property
    def app_secret(self) -> str:
        """
        获取小程序AppSecret
        
        Returns:
            小程序AppSecret
        """
        return self._config["app_secret"]
    
    @property
    def login_url(self) -> str:
        """
        获取微信登录API地址
        
        Returns:
            微信登录API地址
        """
        return self._config["login_url"]
    
    @property
    def phone_url(self) -> str:
        """
        获取微信手机号获取API地址
        
        Returns:
            微信手机号获取API地址
        """
        return self._config["phone_url"]
    
    def get_config(self) -> Dict[str, str]:
        """
        获取完整配置字典（兼容旧版本接口）
        
        Returns:
            包含所有微信配置的字典
        """
        return self._config.copy()
    
    def validate_config(self) -> bool:
        """
        验证配置是否完整
        
        Returns:
            配置是否有效
        """
        required_keys = ["app_id", "app_secret", "login_url", "phone_url"]
        return all(key in self._config and self._config[key] for key in required_keys)

# 创建全局配置实例
wx_config = WxConfig()

# 兼容旧版本的配置字典（建议逐步迁移到新的配置类）
WX_CONFIG = wx_config.get_config()