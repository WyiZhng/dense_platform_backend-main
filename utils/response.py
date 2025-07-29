from pydantic import BaseModel
from typing import TypeVar, Generic, Optional, Any

T = TypeVar('T')


class Response(BaseModel):
    code: int = 0
    message: str = ""
    data: Optional[Any] = None


def success_response(data: Any = None, message: str = "Success") -> dict:
    """
    Create a success response
    
    Args:
        data: Response data
        message: Success message
        
    Returns:
        Success response dictionary
    """
    response = {
        "code": 0,
        "message": message
    }
    if data is not None:
        response["data"] = data
    return response


def error_response(message: str = "Error", code: int = 1) -> dict:
    """
    Create an error response
    
    Args:
        message: Error message
        code: Error code (default: 1)
        
    Returns:
        Error response dictionary
    """
    return {
        "code": code,
        "message": message
    }

