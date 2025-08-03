from typing import Optional

class DeepseekConfig:
    """Deepseek API配置"""
    
    # Deepseek API配置 - 直接配置，不依赖环境变量
    DEEPSEEK_API_KEY: str = "sk-d05b6296c35140d49ac99cbccee1d6ce"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_TIMEOUT: int = 30
    DEEPSEEK_MAX_RETRIES: int = 3
    DEEPSEEK_MAX_TOKENS: int = 200
    DEEPSEEK_TEMPERATURE: float = 0.7
    
    @classmethod
    def get_api_key(cls) -> str:
        """获取API密钥"""
        return cls.DEEPSEEK_API_KEY
    
    @classmethod
    def get_base_url(cls) -> str:
        """获取基础URL"""
        return cls.DEEPSEEK_BASE_URL
    
    @classmethod
    def get_api_url(cls) -> str:
        """获取完整的API URL"""
        return f"{cls.DEEPSEEK_BASE_URL}/v1/chat/completions"
    
    @classmethod
    def get_model(cls) -> str:
        """获取模型名称"""
        return cls.DEEPSEEK_MODEL
    
    @classmethod
    def get_timeout(cls) -> int:
        """获取超时时间"""
        return cls.DEEPSEEK_TIMEOUT
    
    @classmethod
    def get_max_retries(cls) -> int:
        """获取最大重试次数"""
        return cls.DEEPSEEK_MAX_RETRIES
    
    @classmethod
    def get_max_tokens(cls) -> int:
        """获取最大token数"""
        return cls.DEEPSEEK_MAX_TOKENS
    
    @classmethod
    def get_temperature(cls) -> float:
        """获取温度参数"""
        return cls.DEEPSEEK_TEMPERATURE

# 创建配置实例
deepseek_config = DeepseekConfig()