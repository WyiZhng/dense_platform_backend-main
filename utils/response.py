from pydantic import BaseModel
from typing import TypeVar, Generic

T = TypeVar('T')


class Response(BaseModel, Generic[T]):
    code: int = 0
    message: str = ""

