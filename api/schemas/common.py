from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str

    class Config:
        schema_extra = {
            "example": {
                "detail": "Resource not found"
            }
        }


class MessageResponse(BaseModel):
    message: str

    class Config:
        schema_extra = {
            "example": {
                "message": "Operation completed successfully"
            }
        }