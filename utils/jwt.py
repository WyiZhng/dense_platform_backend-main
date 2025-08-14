from jwt import encode, decode
import datetime
from typing import Optional, Dict, Any

def makeAccountJwt(account: str) -> str:
    secret = "this_is_the_secret"
    payload = {
        "account": account,
        "exp": datetime.datetime.now() + datetime.timedelta(days=30),
    }
    return encode(payload, secret, algorithm='HS256')


def resolveAccountJwt(token: str) -> dict:
    secret = "this_is_the_secret"
    return decode(token, secret, algorithms='HS256')


def create_access_token(data: Dict[Any, Any], expires_delta: Optional[datetime.timedelta] = None) -> str:
    """
    创建访问令牌
    
    Args:
        data: 要编码到令牌中的数据字典
        expires_delta: 令牌过期时间间隔，默认为7天
    
    Returns:
        str: 生成的JWT访问令牌
    """
    secret = "this_is_the_secret"
    to_encode = data.copy()
    
    # 设置过期时间
    if expires_delta:
        expire = datetime.datetime.now() + expires_delta
    else:
        expire = datetime.datetime.now() + datetime.timedelta(days=7)
    
    to_encode.update({"exp": expire})
    
    # 生成并返回JWT令牌
    return encode(to_encode, secret, algorithm='HS256')


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    验证并解析JWT令牌
    
    Args:
        token: 要验证的JWT令牌
    
    Returns:
        Dict[str, Any]: 解析后的令牌数据，如果验证失败则返回None
    """
    try:
        secret = "this_is_the_secret"
        payload = decode(token, secret, algorithms=['HS256'])
        return payload
    except Exception:
        return None


if __name__ == '__main__':
    token = makeAccountJwt("gsycl2004")
    print(token)
