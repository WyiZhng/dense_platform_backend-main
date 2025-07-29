"""
算法服务配置
"""

import os
from typing import Optional

class AlgorithmConfig:
    """算法服务配置类"""
    
    # 默认配置
    DEFAULT_ALGORITHM_SERVICE_URL = "http://localhost:8890"
    DEFAULT_TIMEOUT = 60  # 60秒超时
    DEFAULT_MAX_RETRIES = 3  # 最大重试次数
    
    @classmethod
    def get_service_url(cls) -> str:
        """获取算法服务URL"""
        return os.getenv("ALGORITHM_SERVICE_URL", cls.DEFAULT_ALGORITHM_SERVICE_URL)
    
    @classmethod
    def get_timeout(cls) -> int:
        """获取请求超时时间"""
        return int(os.getenv("ALGORITHM_TIMEOUT", cls.DEFAULT_TIMEOUT))
    
    @classmethod
    def get_max_retries(cls) -> int:
        """获取最大重试次数"""
        return int(os.getenv("ALGORITHM_MAX_RETRIES", cls.DEFAULT_MAX_RETRIES))
    
    @classmethod
    def is_enabled(cls) -> bool:
        """检查算法服务是否启用"""
        return os.getenv("ALGORITHM_SERVICE_ENABLED", "true").lower() == "true"
    
    @classmethod
    def get_health_check_url(cls) -> str:
        """获取健康检查URL"""
        return f"{cls.get_service_url()}/health"
    
    @classmethod
    def get_predict_url(cls) -> str:
        """获取预测接口URL"""
        return f"{cls.get_service_url()}/predict"

# 全局配置实例
algorithm_config = AlgorithmConfig()