from enum import Enum
from typing import Any

from pydantic import BaseModel


class FileBase(BaseModel):
    path: str


class FileUpdate(FileBase):
    pass


class FileTypes(Enum):
    file = "file"
    directory = "directory"


class File(FileBase):
    type: FileTypes
    size: str

    class Config:
        orm_mode = True


class FileHTTPRequest(BaseModel):
    method: str
    url: str
    headers: dict[str, Any] = {}  # thank you pydantic, for handling mutable defaults
    data: dict[str, Any] = {}


class FileInfo(BaseModel):
    path: str
    type: FileTypes
    size: str
