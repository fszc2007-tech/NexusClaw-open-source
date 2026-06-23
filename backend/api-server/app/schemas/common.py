from typing import Generic, TypeVar

from pydantic import BaseModel
from pydantic.generics import GenericModel

T = TypeVar("T")


class ApiResponse(GenericModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T | None = None


class SimpleMessage(BaseModel):
    success: bool = True
    detail: str = "ok"
