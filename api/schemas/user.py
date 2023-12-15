import enum
from pydantic import BaseModel


class UserGroups(enum.Enum):
    users = "users"
    workers = "workers"


class UserBase(BaseModel):
    email: str
    groups: list[UserGroups] | None


class UserCreate(UserBase):
    password: str


class User(UserBase):
    class Config:
        orm_mode = True
