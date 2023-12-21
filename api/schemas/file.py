from pydantic import BaseModel

from api.core.filesystem import FileTypes


class FileBase(BaseModel):
    path: str


class FileUpdate(FileBase):
    pass


class File(FileBase):
    type: FileTypes
    size: str

    class Config:
        orm_mode = True


class FileHTTPRequest(BaseModel):
    method: str
    url: str
    headers: dict = {}  # thank you pydantic, for handling mutable defaults
    data: dict = {}
